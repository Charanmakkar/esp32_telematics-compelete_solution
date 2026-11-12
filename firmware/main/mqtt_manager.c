#include "mqtt_manager.h"
#include "adc_manager.h"
#include "command_handler.h"
#include "wifi_manager.h"
#include <inttypes.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "esp_check.h"
#include "esp_crt_bundle.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_random.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"
#include "mqtt_client.h"

typedef struct {
    esp_mqtt_client_handle_t client;
    const app_config_t *config;
    EventGroupHandle_t events;
    StaticEventGroup_t event_storage;
    char telemetry_topic[NAV_TOPIC_CAPACITY];
    char command_topic[NAV_TOPIC_CAPACITY];
    char ack_topic[NAV_TOPIC_CAPACITY];
    char status_topic[NAV_TOPIC_CAPACITY];
    char boot_id[37];
    char will[160];
    char incoming[NAV_COMMAND_CAPACITY];
    size_t incoming_total;
    size_t incoming_received;
    bool incoming_retained;
    portMUX_TYPE counter_lock;
    uint32_t dropped;
} mqtt_context_t;
static mqtt_context_t context = { .counter_lock = portMUX_INITIALIZER_UNLOCKED };

static void count_dropped(mqtt_context_t *state, uint32_t count)
{
    portENTER_CRITICAL(&state->counter_lock);
    if (count > (UINT32_MAX - state->dropped)) { state->dropped = UINT32_MAX; }
    else { state->dropped += count; }
    portEXIT_CRITICAL(&state->counter_lock);
}

static uint32_t read_dropped(mqtt_context_t *state)
{
    portENTER_CRITICAL(&state->counter_lock);
    const uint32_t count = state->dropped;
    portEXIT_CRITICAL(&state->counter_lock);
    return count;
}

static bool append_json(char *buffer, size_t size, size_t *used, const char *format, ...)
{
    if ((buffer == NULL) || (used == NULL) || (*used >= size)) { return false; }
    va_list arguments;
    va_start(arguments, format);
    const int count = vsnprintf(buffer + *used, size - *used, format, arguments);
    va_end(arguments);
    if ((count < 0) || ((size_t)count >= (size - *used))) { return false; }
    *used += (size_t)count;
    return true;
}

static bool connected(const mqtt_context_t *state)
{
    return (xEventGroupGetBits(state->events) & NAV_MQTT_CONNECTED_BIT) != 0U;
}

static bool enqueue(mqtt_context_t *state, const char *topic, const char *json, int retain)
{
    if (!connected(state)) { return false; }
    /* The IDF outbox owns a bounded copy. This API does not perform socket I/O. */
    const int message_id = esp_mqtt_client_enqueue(state->client, topic, json, 0, MQTT_QOS, retain, true);
    return message_id >= 0;
}

static void acknowledge(const nav_command_t *command, const char *status, const char *reason)
{
    if ((command == NULL) || (status == NULL) || (reason == NULL)) { return; }
    char json[384];
    const char key = ((command->key == 'A') || (command->key == 'B')) ? command->key : '?';
    const int count = snprintf(json, sizeof(json),
        "{\"command_id\":\"%s\",\"key\":\"%c\",\"value\":%u,\"status\":\"%s\",\"reason\":\"%s\",\"boot_id\":\"%s\"}",
        command->command_id, key, (unsigned int)command->value, status, reason, context.boot_id);
    if ((count > 0) && ((size_t)count < sizeof(json))) { (void)enqueue(&context, context.ack_topic, json, 0); }
}

static void receive_fragment(mqtt_context_t *state, const esp_mqtt_event_t *event)
{
    if ((event->current_data_offset < 0) || (event->total_data_len <= 0) ||
        (event->data_len < 0) || ((size_t)event->total_data_len >= sizeof(state->incoming))) {
        state->incoming_total = 0U;
        return;
    }
    const size_t offset = (size_t)event->current_data_offset;
    const size_t length = (size_t)event->data_len;
    if (offset == 0U) {
        state->incoming_total = 0U;
        state->incoming_received = 0U;
        if ((event->topic == NULL) || (event->topic_len < 0) ||
            ((size_t)event->topic_len != strlen(state->command_topic)) ||
            (memcmp(event->topic, state->command_topic, (size_t)event->topic_len) != 0)) { return; }
        state->incoming_total = (size_t)event->total_data_len;
        state->incoming_retained = event->retain;
    }
    if ((state->incoming_total == 0U) || (offset != state->incoming_received) ||
        ((size_t)event->total_data_len != state->incoming_total) ||
        (length > (state->incoming_total - state->incoming_received))) {
        state->incoming_total = 0U;
        return;
    }
    if (length > 0U) {
        if (event->data == NULL) { state->incoming_total = 0U; return; }
        memcpy(state->incoming + offset, event->data, length);
    }
    state->incoming_received += length;
    if (state->incoming_received == state->incoming_total) {
        state->incoming[state->incoming_total] = '\0';
        /* Reject embedded NULs: schema parser must see the entire MQTT message. */
        if (strlen(state->incoming) == state->incoming_total) {
            command_handler_receive(state->incoming, state->incoming_total, state->incoming_retained);
        }
        state->incoming_total = 0U;
    }
}

static void mqtt_event(void *argument, esp_event_base_t base, int32_t id, void *event_data)
{
    (void)base;
    mqtt_context_t *state = (mqtt_context_t *)argument;
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t)event_data;
    switch (id) {
    case MQTT_EVENT_CONNECTED:
        (void)xEventGroupSetBits(state->events, NAV_MQTT_CONNECTED_BIT);
        if (esp_mqtt_client_subscribe(state->client, state->command_topic, MQTT_QOS) < 0) {
            ESP_LOGE("mqtt", "Command subscription enqueue failed");
        }
        ESP_LOGI("mqtt", "Connected and command subscription requested");
        break;
    case MQTT_EVENT_DISCONNECTED:
        (void)xEventGroupClearBits(state->events, NAV_MQTT_CONNECTED_BIT);
        state->incoming_total = 0U;
        ESP_LOGW("mqtt", "Disconnected");
        break;
    case MQTT_EVENT_DATA:
        if (event != NULL) { receive_fragment(state, event); }
        break;
    case MQTT_EVENT_ERROR:
        ESP_LOGW("mqtt", "Transport or broker error (credentials never logged)");
        break;
    case MQTT_EVENT_DELETED:
        /* This includes lost status/ack messages as well as telemetry, so the
         * counter is a conservative aggregate rather than a pure ADC loss count. */
        count_dropped(state, 1U);
        break;
    default:
        break;
    }
}

static bool serialize_sample(const mqtt_context_t *state, const adc_telemetry_t *sample,
    bool stale, char *json, size_t capacity, uint32_t dropped)
{
    size_t used = 0U;
    bool ok = append_json(json, capacity, &used,
        "{\"schema_version\":1,\"device_id\":\"%s\",\"boot_id\":\"%s\",\"sequence\":%" PRIu32 ",\"timestamp_ms\":",
        state->config->device_id, state->boot_id, sample->sample_sequence);
    if (sample->time_valid) { ok = ok && append_json(json, capacity, &used, "%" PRIu64, sample->timestamp_ms); }
    else { ok = ok && append_json(json, capacity, &used, "null"); }
    ok = ok && append_json(json, capacity, &used,
        ",\"time_valid\":%s,\"uptime_ms\":%" PRIu64 ",\"channels\":{", sample->time_valid ? "true" : "false", sample->uptime_ms);
    for (size_t index = 0U; index < NAV_CHANNEL_COUNT; ++index) {
        ok = ok && append_json(json, capacity, &used, "%s\"analog_%u\":%" PRIu32,
            (index == 0U) ? "" : ",", (unsigned int)index + 1U, sample->adc_mv[index]);
    }
    ok = ok && append_json(json, capacity, &used, "},\"raw\":[");
    for (size_t index = 0U; index < NAV_CHANNEL_COUNT; ++index) {
        ok = ok && append_json(json, capacity, &used, "%s%" PRIu32, (index == 0U) ? "" : ",", sample->adc_raw[index]);
    }
    return ok && append_json(json, capacity, &used,
        "],\"valid_mask\":%u,\"mqtt_connected\":true,\"dropped_samples\":%" PRIu32 ",\"source\":\"hardware\",\"stale\":%s}",
        (unsigned int)sample->valid_mask, dropped, stale ? "true" : "false");
}

static void publish_status(mqtt_context_t *state)
{
    uint8_t control_a = 0U;
    uint8_t control_b = 0U;
    command_handler_state(&control_a, &control_b);
    char json[256];
    const int count = snprintf(json, sizeof(json),
        "{\"online\":true,\"boot_id\":\"%s\",\"source\":\"hardware\",\"controls\":{\"A\":%u,\"B\":%u}}",
        state->boot_id, (unsigned int)control_a, (unsigned int)control_b);
    if ((count > 0) && ((size_t)count < sizeof(json))) { (void)enqueue(state, state->status_topic, json, 1); }
}

void vMqttPublishTask(void *argument)
{
    mqtt_context_t *state = (mqtt_context_t *)argument;
    TickType_t wake = xTaskGetTickCount();
    adc_telemetry_t latest = {0};
    bool have_sample = false;
    uint64_t last_status_ms = 0U;
    char json[NAV_JSON_CAPACITY];
    for (;;) {
        bool fresh = false;
        adc_telemetry_t incoming;
        uint32_t drained = 0U;
        while (adc_manager_take(&incoming)) { latest = incoming; have_sample = true; fresh = true; ++drained; }
        if (drained > 1U) { count_dropped(state, drained - 1U); }
        const bool is_connected = connected(state) && wifi_manager_connected();
        command_handler_tick(is_connected);
        if (is_connected) {
            if (have_sample) {
                const uint32_t publish_drops = read_dropped(state);
                const uint32_t adc_drops = adc_manager_dropped();
                const uint32_t total_drops = (adc_drops > (UINT32_MAX - publish_drops)) ? UINT32_MAX : adc_drops + publish_drops;
                const bool serialized = serialize_sample(state, &latest, !fresh, json, sizeof(json), total_drops);
                if ((!serialized) || (!enqueue(state, state->telemetry_topic, json, 0))) { count_dropped(state, 1U); }
            }
            if ((app_uptime_ms() - last_status_ms) >= 1000U) {
                publish_status(state);
                last_status_ms = app_uptime_ms();
                ESP_LOGI("resources", "free_heap=%u adc_queue_drops=%" PRIu32 " publish_drops=%" PRIu32 " mqtt_stack_margin=%u",
                    (unsigned int)esp_get_free_heap_size(), adc_manager_dropped(), read_dropped(state),
                    (unsigned int)uxTaskGetStackHighWaterMark(NULL));
            }
        } else if (fresh) { count_dropped(state, 1U); }
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(MQTT_PUBLISH_MS));
    }
}

static void reconnect_task(void *argument)
{
    mqtt_context_t *state = (mqtt_context_t *)argument;
    uint32_t backoff_ms = 1000U;
    for (;;) {
        if (connected(state)) { backoff_ms = 1000U; vTaskDelay(pdMS_TO_TICKS(1000U)); continue; }
        if (wifi_manager_connected()) {
            const esp_err_t result = esp_mqtt_client_reconnect(state->client);
            if ((result != ESP_OK) && (result != ESP_ERR_INVALID_STATE)) {
                ESP_LOGW("mqtt", "Reconnect request failed: %s", esp_err_to_name(result));
            }
            (void)xEventGroupWaitBits(state->events, NAV_MQTT_CONNECTED_BIT, pdFALSE, pdFALSE, pdMS_TO_TICKS(backoff_ms));
            if (backoff_ms < 30000U) { backoff_ms = ((backoff_ms * 2U) > 30000U) ? 30000U : backoff_ms * 2U; }
        } else { vTaskDelay(pdMS_TO_TICKS(1000U)); }
    }
}

esp_err_t mqtt_manager_start(const app_config_t *config)
{
    if ((config == NULL) || (context.client != NULL)) { return ESP_ERR_INVALID_ARG; }
    context.config = config;
    context.events = xEventGroupCreateStatic(&context.event_storage);
    uint32_t random_words[4];
    esp_fill_random(random_words, sizeof(random_words));
    const int uuid_count = snprintf(context.boot_id, sizeof(context.boot_id),
        "%08" PRIx32 "-%04x-%04x-%04x-%04x%08" PRIx32,
        random_words[0], (unsigned int)(random_words[1] >> 16U), (unsigned int)(random_words[1] & UINT32_C(0xffff)),
        (unsigned int)(random_words[2] >> 16U), (unsigned int)(random_words[2] & UINT32_C(0xffff)), random_words[3]);
    if (uuid_count != 36) { return ESP_FAIL; }
    const char *suffixes[] = { "telemetry", "command", "ack", "status" };
    char *topics[] = { context.telemetry_topic, context.command_topic, context.ack_topic, context.status_topic };
    for (size_t index = 0U; index < 4U; ++index) {
        const int count = snprintf(topics[index], NAV_TOPIC_CAPACITY, "%s/%s/%s", CONFIG_NAV_MQTT_TOPIC_PREFIX, config->device_id, suffixes[index]);
        if ((count < 0) || ((size_t)count >= NAV_TOPIC_CAPACITY)) { return ESP_ERR_INVALID_SIZE; }
    }
    const int will_count = snprintf(context.will, sizeof(context.will),
        "{\"online\":false,\"boot_id\":\"%s\",\"source\":\"hardware\"}", context.boot_id);
    if ((will_count < 0) || ((size_t)will_count >= sizeof(context.will))) { return ESP_ERR_INVALID_SIZE; }
    const bool tls = strncmp(config->mqtt_uri, "mqtts://", 8U) == 0;
    const esp_mqtt_client_config_t mqtt_config = {
        .broker.address.uri = config->mqtt_uri,
        .broker.verification.crt_bundle_attach = tls ? esp_crt_bundle_attach : NULL,
        .credentials.client_id = config->device_id,
        .credentials.username = config->mqtt_username,
        .credentials.authentication.password = config->mqtt_password,
        .session.keepalive = MQTT_KEEPALIVE_SEC,
        .session.last_will.topic = context.status_topic,
        .session.last_will.msg = context.will,
        .session.last_will.qos = MQTT_QOS,
        .session.last_will.retain = 1,
        .network.disable_auto_reconnect = true,
        .network.timeout_ms = 2000,
        .buffer.size = NAV_JSON_CAPACITY,
        .buffer.out_size = NAV_JSON_CAPACITY,
        .outbox.limit = NAV_MQTT_OUTBOX_BYTES,
        .task.stack_size = 6144,
    };
    context.client = esp_mqtt_client_init(&mqtt_config);
    if (context.client == NULL) { return ESP_ERR_NO_MEM; }
    ESP_RETURN_ON_ERROR(command_handler_init(acknowledge), "mqtt", "commands");
    ESP_RETURN_ON_ERROR(esp_mqtt_client_register_event(context.client, ESP_EVENT_ANY_ID, mqtt_event, &context), "mqtt", "events");
    ESP_RETURN_ON_ERROR(esp_mqtt_client_start(context.client), "mqtt", "start");
    if (xTaskCreate(vMqttPublishTask, "nav_publish", 6144U, &context, 4U, NULL) != pdPASS) { return ESP_ERR_NO_MEM; }
    if (xTaskCreate(reconnect_task, "nav_reconnect", 3072U, &context, 3U, NULL) != pdPASS) { return ESP_ERR_NO_MEM; }
    return ESP_OK;
}
