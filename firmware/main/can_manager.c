#include "can_manager.h"
#include "app_config.h"
#include "mqtt_manager.h"
#include "driver/twai.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include <inttypes.h>
#include <stdio.h>

/* Classic CAN only. No transmit API is used. Capture never waits for UART/MQTT. */
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

static void capture_task(void *argument)
{
    (void)argument;
    for (;;) {
        captured_frame_t item = {0};
        if (twai_receive(&item.frame, pdMS_TO_TICKS(100)) != ESP_OK) { continue; }
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

static void serial_task(void *argument)
{
    (void)argument;
    captured_frame_t item;
    for (;;) {
        if (xQueueReceive(serial_frames, &item, portMAX_DELAY) != pdTRUE) { continue; }
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
            twai_status_info_t status = {0};
            (void)twai_get_status_info(&status);
            uint32_t qd, sd;
            portENTER_CRITICAL(&counters_lock); qd = queue_drops; sd = serial_drops; portEXIT_CRITICAL(&counters_lock);
            json[used] = '\0';
            if (!mqtt_manager_publish_can(json, qd, sd, publish_drops,
                                          status.rx_missed_count, status.rx_overrun_count,
                                          status.bus_error_count)) { publish_drops += count; }
            last_status = app_uptime_ms();
        }
        /* Drain bursts immediately; the idle delay is not a fixed throughput cap. */
        if (uxQueueMessagesWaiting(frames) > 0) { taskYIELD(); }
        else { vTaskDelay(pdMS_TO_TICKS(20)); }
    }
}

esp_err_t can_manager_start(void)
{
    twai_general_config_t general = TWAI_GENERAL_CONFIG_DEFAULT(GPIO_NUM_25, GPIO_NUM_26, TWAI_MODE_LISTEN_ONLY);
    general.tx_queue_len = 0;
    general.rx_queue_len = 256;
    const twai_timing_config_t timing = TWAI_TIMING_CONFIG_500KBITS();
    const twai_filter_config_t filter = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    esp_err_t result = twai_driver_install(&general, &timing, &filter);
    if (result != ESP_OK) { return result; }
    frames = xQueueCreate(256, sizeof(captured_frame_t));
    serial_frames = xQueueCreate(64, sizeof(captured_frame_t));
    if (!frames || !serial_frames) { return ESP_ERR_NO_MEM; }
    result = twai_start();
    if (result != ESP_OK) { return result; }
    if (xTaskCreate(capture_task, "can_rx", 3072, NULL, 6, NULL) != pdPASS ||
        xTaskCreate(publish_task, "can_mqtt", 20480, NULL, 3, NULL) != pdPASS ||
        xTaskCreate(serial_task, "can_serial", 3072, NULL, 2, NULL) != pdPASS) { return ESP_ERR_NO_MEM; }
    ESP_LOGI("can", "Listen-only classic CAN 500 kbit/s TX=25 RX=26; accepting all IDs");
    return ESP_OK;
}
