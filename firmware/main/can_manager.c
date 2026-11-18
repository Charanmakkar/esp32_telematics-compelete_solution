#include "can_manager.h"
#include "app_config.h"
#include "mqtt_manager.h"
#include "diagnostic_manager.h"
#include "diagnostic_policy.h"
#include "driver/twai.h"
#include "driver/gpio.h"
#include "esp_app_desc.h"
#include "sw_version.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

/* Classic CAN capture remains independent of UART/MQTT and diagnostic delivery. */
typedef struct {
    twai_message_t frame;
    uint32_t sequence;
    uint64_t uptime_ms;
    uint64_t timestamp_ms;
} captured_frame_t;
static QueueHandle_t frames;
static QueueHandle_t serial_frames;
static uint32_t sequence, queue_drops, serial_drops;
static portMUX_TYPE counters_lock = portMUX_INITIALIZER_UNLOCKED;
static SemaphoreHandle_t driver_lock;
static bool normal_mode, driver_ready;
static uint64_t rx_total, rx_bytes, standard_frames, extended_frames, rtr_frames, bits_min, bits_max;
static uint32_t mode_changes, mode_switch_drops, tx_frames;
static twai_status_info_t accumulated;

static esp_err_t install_driver(bool normal)
{
    twai_general_config_t general = TWAI_GENERAL_CONFIG_DEFAULT(GPIO_NUM_25, GPIO_NUM_26,
        normal ? TWAI_MODE_NORMAL : TWAI_MODE_LISTEN_ONLY);
    general.tx_queue_len = normal ? 8 : 0;
    general.rx_queue_len = 256;
    general.alerts_enabled = TWAI_ALERT_TX_SUCCESS | TWAI_ALERT_TX_FAILED | TWAI_ALERT_BUS_OFF;
    const twai_timing_config_t timing = TWAI_TIMING_CONFIG_500KBITS();
    const twai_filter_config_t filter = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    esp_err_t result = twai_driver_install(&general, &timing, &filter);
    if (result == ESP_OK) {
        result = twai_start();
        if (result != ESP_OK) { (void)twai_driver_uninstall(); }
    }
    driver_ready = result == ESP_OK;
    return result;
}

esp_err_t can_manager_diagnostic_mode(bool enabled)
{
    if (!driver_lock) { return ESP_ERR_INVALID_STATE; }
    xSemaphoreTake(driver_lock, portMAX_DELAY);
    esp_err_t result = ESP_OK;
    if (normal_mode != enabled || !driver_ready) {
        twai_status_info_t old = {0};
        if (driver_ready) {
            (void)twai_get_status_info(&old);
            accumulated.rx_missed_count += old.rx_missed_count;
            accumulated.rx_overrun_count += old.rx_overrun_count;
            accumulated.bus_error_count += old.bus_error_count;
            accumulated.arb_lost_count += old.arb_lost_count;
            accumulated.tx_failed_count += old.tx_failed_count;
            mode_switch_drops += old.msgs_to_rx;
            (void)twai_stop();
            (void)twai_driver_uninstall();
        }
        result = install_driver(enabled);
        normal_mode = enabled && result == ESP_OK;
        ++mode_changes;
        if (result != ESP_OK && enabled) { (void)install_driver(false); }
    }
    xSemaphoreGive(driver_lock);
    return result;
}

bool can_manager_send(uint32_t id, const uint8_t data[8])
{
    if (!driver_lock || !nav_diag_tx_allowed(id)) { return false; }
    xSemaphoreTake(driver_lock, portMAX_DELAY);
    twai_status_info_t status = {0};
    /* Normal CAN arbitration/retransmission, bounded by the diagnostic deadline.
       A failed transfer is stopped when the manager restores listen-only. */
    twai_message_t frame = {.identifier=id, .data_length_code=8};
    memcpy(frame.data, data, 8);
    uint32_t alerts = 0;
    if (driver_ready) { (void)twai_read_alerts(&alerts, 0); }
    bool ok = driver_ready && normal_mode && twai_get_status_info(&status) == ESP_OK &&
        status.state == TWAI_STATE_RUNNING && twai_transmit(&frame, pdMS_TO_TICKS(20)) == ESP_OK;
    if (ok) {
        ok = twai_read_alerts(&alerts, pdMS_TO_TICKS(100)) == ESP_OK &&
            (alerts & TWAI_ALERT_TX_SUCCESS) && !(alerts & (TWAI_ALERT_TX_FAILED | TWAI_ALERT_BUS_OFF));
    }
    if (ok) { ++tx_frames; }
    xSemaphoreGive(driver_lock);
    return ok;
}

void can_manager_stats(char *json, size_t capacity)
{
    xSemaphoreTake(driver_lock, portMAX_DELAY);
    twai_status_info_t s = {0};
    if (driver_ready) { (void)twai_get_status_info(&s); }
    snprintf(json, capacity,
        "\"uptime_ms\":%" PRIu64 ",\"rx_total\":%" PRIu64 ",\"rx_bytes\":%" PRIu64
        ",\"standard_frames\":%" PRIu64 ",\"extended_frames\":%" PRIu64 ",\"rtr_frames\":%" PRIu64
        ",\"wire_bits_min\":%" PRIu64 ",\"wire_bits_max\":%" PRIu64
        ",\"rx_missed\":%" PRIu32 ",\"rx_overruns\":%" PRIu32 ",\"bus_errors\":%" PRIu32
        ",\"arb_lost\":%" PRIu32 ",\"tx_failed\":%" PRIu32 ",\"tx_frames\":%" PRIu32
        ",\"rx_error_counter\":%" PRIu32 ",\"tx_error_counter\":%" PRIu32
        ",\"controller_state\":%d,\"mode\":\"%s\",\"mode_changes\":%" PRIu32
        ",\"mode_switch_drops\":%" PRIu32 ",\"diag_supported\":true,\"diag_version\":3"
        ",\"sw_version\":\"%s\",\"sw_build\":\"%s\"",
        app_uptime_ms(), rx_total, rx_bytes, standard_frames, extended_frames, rtr_frames, bits_min, bits_max,
        s.rx_missed_count+accumulated.rx_missed_count, s.rx_overrun_count+accumulated.rx_overrun_count,
        s.bus_error_count+accumulated.bus_error_count, s.arb_lost_count+accumulated.arb_lost_count,
        s.tx_failed_count+accumulated.tx_failed_count, tx_frames, s.rx_error_counter, s.tx_error_counter,
        (int)s.state, !driver_ready ? "unavailable" : normal_mode ? "diagnostic" : "listen_only",
        mode_changes, mode_switch_drops, SW_VERSION, SW_BUILD_ID);
    xSemaphoreGive(driver_lock);
}

static void capture_task(void *argument)
{
    (void)argument;
    for (;;) {
        captured_frame_t item = {0};
        xSemaphoreTake(driver_lock, portMAX_DELAY);
        const esp_err_t received = driver_ready ? twai_receive(&item.frame, pdMS_TO_TICKS(2)) : ESP_FAIL;
        if (received == ESP_OK) {
            unsigned bytes = item.frame.rtr ? 0 : item.frame.data_length_code;
            ++rx_total; rx_bytes += bytes;
            if (item.frame.extd) { ++extended_frames; } else { ++standard_frames; }
            if (item.frame.rtr) { ++rtr_frames; }
            unsigned base = (item.frame.extd ? 67 : 47) + bytes*8;
            bits_min += base;
            bits_max += base + ((item.frame.extd ? 54 : 34) + bytes*8 - 1)/4;
        }
        xSemaphoreGive(driver_lock);
        if (received != ESP_OK) { vTaskDelay(1); continue; }
        diagnostic_manager_frame(&item.frame);
        item.uptime_ms = app_uptime_ms();
        if (!app_epoch_ms(&item.timestamp_ms)) { item.timestamp_ms = 0; }
        item.sequence = sequence++;
        if (xQueueSend(frames, &item, 0) != pdTRUE) {
            portENTER_CRITICAL(&counters_lock); ++queue_drops; portEXIT_CRITICAL(&counters_lock);
        }
        if (xQueueSend(serial_frames, &item, 0) != pdTRUE) {
            portENTER_CRITICAL(&counters_lock); ++serial_drops; portEXIT_CRITICAL(&counters_lock);
        }
    }
}

static void serial_status(void)
{
    /* Snapshot under the driver lock, then print outside it. UART must never
       block CAN reception or diagnostic mode changes. Pin levels are only
       instantaneous samples, not a measurement of signal activity. */
    xSemaphoreTake(driver_lock, portMAX_DELAY);
    twai_status_info_t status = {0};
    const esp_err_t result = driver_ready ? twai_get_status_info(&status) : ESP_ERR_INVALID_STATE;
    const uint64_t received = rx_total;
    const uint32_t transmitted = tx_frames;
    const uint32_t errors = accumulated.bus_error_count + status.bus_error_count;
    const char *mode = !driver_ready ? "unavailable" : normal_mode ? "diagnostic" : "listen_only";
    const int rxd = gpio_get_level(GPIO_NUM_26);
    xSemaphoreGive(driver_lock);
    uint32_t drops;
    portENTER_CRITICAL(&counters_lock); drops = serial_drops; portEXIT_CRITICAL(&counters_lock);
    ESP_LOGI("can", "CAN_STATUS mode=%s state=%d rx=%" PRIu64 " tx=%" PRIu32
             " bus_errors=%" PRIu32 " REC=%" PRIu32 " TEC=%" PRIu32
             " serial_drops=%" PRIu32 " RXD26_now=%d",
             mode, result == ESP_OK ? (int)status.state : -1, received, transmitted,
             errors, status.rx_error_counter, status.tx_error_counter, drops, rxd);
}

static void serial_task(void *argument)
{
    (void)argument;
    captured_frame_t item;
    uint64_t last_status = 0;
    for (;;) {
        if (app_uptime_ms() - last_status >= 5000) {
            serial_status();
            last_status = app_uptime_ms();
        }
        if (xQueueReceive(serial_frames, &item, pdMS_TO_TICKS(1000)) != pdTRUE) { continue; }
        char bytes[25] = {0};
        if (!item.frame.rtr) {
            for (unsigned i = 0; i < item.frame.data_length_code && i < 8; ++i) {
                (void)snprintf(bytes + i * 3, sizeof(bytes) - i * 3, "%02X ", item.frame.data[i]);
            }
        }
        printf("CAN seq=%" PRIu32 " ID=0x%08" PRIX32 " %s %s DLC=%u DATA=%s\n",
               item.sequence, item.frame.identifier, item.frame.extd ? "EXT" : "STD",
               item.frame.rtr ? "RTR" : "DATA", item.frame.data_length_code, bytes);
    }
}

static void publish_task(void *argument)
{
    (void)argument;
    uint32_t publish_drops = 0;
    uint64_t last_status = 0;
    for (;;) {
        char json[6144];
        size_t used = 0;
        unsigned count = 0;
        captured_frame_t item;
        while (count < 24 && xQueueReceive(frames, &item, 0) == pdTRUE) {
            char hex[17] = {0};
            if (!item.frame.rtr) {
                for (unsigned i = 0; i < item.frame.data_length_code && i < 8; ++i) {
                    (void)snprintf(hex + i * 2, sizeof(hex) - i * 2, "%02X", item.frame.data[i]);
                }
            }
            const int n = snprintf(json + used, sizeof(json) - used,
                "%s{\"sequence\":%" PRIu32 ",\"uptime_ms\":%" PRIu64 ",\"timestamp_ms\":%" PRIu64
                ",\"can_id\":%" PRIu32 ",\"extended\":%s,\"rtr\":%s,\"dlc\":%u,\"data\":\"%s\"}",
                count ? "," : "", item.sequence, item.uptime_ms, item.timestamp_ms,
                item.frame.identifier, item.frame.extd ? "true" : "false",
                item.frame.rtr ? "true" : "false", item.frame.data_length_code, hex);
            if (n < 0 || (size_t)n >= sizeof(json) - used) { ++publish_drops; break; }
            used += (size_t)n;
            ++count;
        }
        if (count || app_uptime_ms() - last_status >= 1000) {
            char statistics[1024];
            can_manager_stats(statistics, sizeof(statistics));
            uint32_t qd, sd;
            portENTER_CRITICAL(&counters_lock); qd = queue_drops; sd = serial_drops; portEXIT_CRITICAL(&counters_lock);
            json[used] = '\0';
            if (!mqtt_manager_publish_can(json, qd, sd, publish_drops,
                                          statistics)) { publish_drops += count; }
            last_status = app_uptime_ms();
        }
        /* Drain bursts immediately; the idle delay is not a fixed throughput cap. */
        if (uxQueueMessagesWaiting(frames) > 0) { taskYIELD(); }
        else { vTaskDelay(pdMS_TO_TICKS(20)); }
    }
}

esp_err_t can_manager_start(void)
{
    driver_lock = xSemaphoreCreateMutex();
    if (!driver_lock) { return ESP_ERR_NO_MEM; }
    esp_err_t result = install_driver(false);
    if (result != ESP_OK) { return result; }
    frames = xQueueCreate(256, sizeof(captured_frame_t));
    serial_frames = xQueueCreate(64, sizeof(captured_frame_t));
    if (!frames || !serial_frames) { return ESP_ERR_NO_MEM; }
    if (xTaskCreate(capture_task, "can_rx", 3072, NULL, 6, NULL) != pdPASS ||
        xTaskCreate(publish_task, "can_mqtt", 20480, NULL, 3, NULL) != pdPASS ||
        xTaskCreate(serial_task, "can_serial", 3072, NULL, 2, NULL) != pdPASS) { return ESP_ERR_NO_MEM; }
    ESP_LOGI("can", "Listen-only classic CAN 500 kbit/s TX=25 RX=26; accepting all IDs");
    char elf_sha[17];
    esp_app_get_elf_sha256(elf_sha, sizeof(elf_sha));
    ESP_LOGI("can", "CAN_BUILD SW_VERSION=%s BUILD=%s diag_version=3 ELF=%s; serial CAN ID/data enabled",
             SW_VERSION, SW_BUILD_ID, elf_sha);
    return ESP_OK;
}
