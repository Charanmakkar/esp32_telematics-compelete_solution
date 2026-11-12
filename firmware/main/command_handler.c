#include "command_handler.h"
#include "app_config.h"
#include <math.h>
#include <string.h>
#include "cJSON.h"
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

#define COMMAND_QUEUE_LENGTH (8U)
#define COMMAND_CACHE_LENGTH (64U)
typedef struct { nav_command_t command; bool retained; bool parsed; } queued_command_t;
typedef struct { nav_command_t command; uint64_t retain_until; bool used; } cached_command_t;
typedef struct {
    command_ack_fn acknowledge;
    QueueHandle_t queue;
    StaticQueue_t queue_control;
    uint8_t queue_storage[COMMAND_QUEUE_LENGTH * sizeof(queued_command_t)];
    cached_command_t cache[COMMAND_CACHE_LENGTH];
    uint8_t controls[2];
    uint64_t lease_end[2];
} command_context_t;
static command_context_t context;

static esp_err_t apply_output(size_t control, uint8_t value)
{
#if CONFIG_NAV_PHYSICAL_CONTROLS
    const gpio_num_t pin = (control == 0U) ? (gpio_num_t)CONFIG_NAV_CONTROL_A_GPIO : (gpio_num_t)CONFIG_NAV_CONTROL_B_GPIO;
    return gpio_set_level(pin, value);
#else
    (void)control;
    (void)value;
    return ESP_OK;
#endif
}

esp_err_t command_handler_safe_start(void)
{
#if CONFIG_NAV_PHYSICAL_CONTROLS
    /* User authorized A/B GPIO actuation. Only non-strapping GPIO25/26 are
     * selectable here; neither conflicts with the native ADC1 six-input map. */
    if (CONFIG_NAV_CONTROL_A_GPIO == CONFIG_NAV_CONTROL_B_GPIO) { return ESP_ERR_INVALID_ARG; }
    const uint64_t mask = (UINT64_C(1) << CONFIG_NAV_CONTROL_A_GPIO) | (UINT64_C(1) << CONFIG_NAV_CONTROL_B_GPIO);
    const gpio_config_t output = { .pin_bit_mask = mask, .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE, .pull_down_en = GPIO_PULLDOWN_DISABLE, .intr_type = GPIO_INTR_DISABLE };
    /* Program LOW latch before changing the pad to output. External pull-downs
     * are still required to guarantee a safe level before firmware starts. */
    if ((gpio_set_level((gpio_num_t)CONFIG_NAV_CONTROL_A_GPIO, 0U) != ESP_OK) ||
        (gpio_set_level((gpio_num_t)CONFIG_NAV_CONTROL_B_GPIO, 0U) != ESP_OK)) { return ESP_FAIL; }
    return gpio_config(&output);
#else
    return ESP_OK;
#endif
}

static bool json_integer(const cJSON *item, uint64_t *number)
{
    if ((!cJSON_IsNumber(item)) || (number == NULL) || (!isfinite(item->valuedouble)) ||
        (item->valuedouble < 0.0) || (item->valuedouble > 9007199254740991.0) ||
        (floor(item->valuedouble) != item->valuedouble)) { return false; }
    *number = (uint64_t)item->valuedouble;
    return true;
}

static bool shallow_json(const char *data, size_t length)
{
    bool quoted = false;
    bool escaped = false;
    unsigned int depth = 0U;
    for (size_t index = 0U; index < length; ++index) {
        const char value = data[index];
        if (quoted) {
            if (escaped) { escaped = false; }
            else if (value == '\\') { escaped = true; }
            else if (value == '"') { quoted = false; }
        } else if (value == '"') { quoted = true; }
        else if ((value == '{') || (value == '[')) { if (++depth > 2U) { return false; } }
        else if ((value == '}') || (value == ']')) { if (depth == 0U) { return false; } --depth; }
    }
    return (!quoted) && (depth == 0U);
}

esp_err_t command_handler_init(command_ack_fn acknowledge)
{
    if ((acknowledge == NULL) || (context.queue != NULL)) { return ESP_ERR_INVALID_ARG; }
    context.acknowledge = acknowledge;
    context.queue = xQueueCreateStatic(COMMAND_QUEUE_LENGTH, sizeof(queued_command_t),
        context.queue_storage, &context.queue_control);
    return (context.queue == NULL) ? ESP_ERR_NO_MEM : ESP_OK;
}

void command_handler_receive(const char *data, size_t length, bool retained)
{
    if ((data == NULL) || (length == 0U) || (length >= NAV_COMMAND_CAPACITY) || (context.queue == NULL)) { return; }
    if (!shallow_json(data, length)) { return; }
    const char *end = NULL;
    cJSON *root = cJSON_ParseWithLengthOpts(data, length + 1U, &end, true);
    if (root == NULL) { return; }
    queued_command_t pending = { .retained = retained };
    const cJSON *identifier = cJSON_GetObjectItemCaseSensitive(root, "command_id");
    const cJSON *key = cJSON_GetObjectItemCaseSensitive(root, "key");
    const cJSON *value = cJSON_GetObjectItemCaseSensitive(root, "value");
    uint64_t command_value = 0U;
    /* Count each property so duplicate JSON keys and unknown fields fail closed. */
    const char *expected[] = { "command_id", "key", "value", "issued_at_ms", "expires_at_ms" };
    bool properties = cJSON_IsObject(root) && (cJSON_GetArraySize(root) == 5);
    for (size_t index = 0U; index < 5U; ++index) {
        size_t count = 0U;
        const cJSON *item = NULL;
        cJSON_ArrayForEach(item, root) { if ((item->string != NULL) && (strcmp(item->string, expected[index]) == 0)) { ++count; } }
        if (count != 1U) { properties = false; }
    }
    if (cJSON_IsString(identifier) && command_id_valid(identifier->valuestring)) {
        memcpy(pending.command.command_id, identifier->valuestring, NAV_COMMAND_ID_SIZE);
    }
    if (cJSON_IsString(key) && (strlen(key->valuestring) == 1U)) { pending.command.key = key->valuestring[0]; }
    pending.parsed = properties && (pending.command.command_id[0] != '\0') && json_integer(value, &command_value)
        && (command_value <= 1U)
        && json_integer(cJSON_GetObjectItemCaseSensitive(root, "issued_at_ms"), &pending.command.issued_at_ms)
        && json_integer(cJSON_GetObjectItemCaseSensitive(root, "expires_at_ms"), &pending.command.expires_at_ms);
    pending.command.value = (uint8_t)((command_value <= 1U) ? command_value : 0U);
    cJSON_Delete(root);
    if (xQueueSend(context.queue, &pending, 0U) != pdPASS) {
        /* Ack is nonblocking enqueue; overload cannot grow command memory. */
        if (pending.command.command_id[0] != '\0') { context.acknowledge(&pending.command, "rejected", "command_queue_full"); }
    }
}

void command_handler_tick(bool connected)
{
    uint64_t now = 0U;
    const bool time_valid = app_epoch_ms(&now);
    const uint64_t uptime_now = app_uptime_ms();
    if ((!connected) || (!time_valid)) {
        if (context.controls[0] != 0U) { if (apply_output(0U, 0U) == ESP_OK) { context.controls[0] = 0U; } }
        if (context.controls[1] != 0U) { if (apply_output(1U, 0U) == ESP_OK) { context.controls[1] = 0U; } }
        context.lease_end[0] = 0U; context.lease_end[1] = 0U;
    }
    for (size_t index = 0U; index < 2U; ++index) {
        if ((context.lease_end[index] <= uptime_now) && (context.controls[index] != 0U)) {
            if (apply_output(index, 0U) == ESP_OK) { context.controls[index] = 0U; }
        }
    }
    queued_command_t pending;
    for (size_t processed = 0U; (processed < COMMAND_QUEUE_LENGTH) &&
         (xQueueReceive(context.queue, &pending, 0U) == pdPASS); ++processed) {
        const nav_command_t *command = &pending.command;
        if (command->command_id[0] == '\0') { continue; }
        const char *reason = command_rules_validate(command, pending.retained, time_valid, now, CONFIG_NAV_COMMAND_MAX_TTL_MS);
        if (!pending.parsed) { reason = "invalid_schema"; }
        if (!connected) { reason = "disconnected"; }
        if (reason != NULL) { context.acknowledge(command, "rejected", reason); continue; }
        cached_command_t *available = NULL;
        cached_command_t *duplicate = NULL;
        for (size_t index = 0U; index < COMMAND_CACHE_LENGTH; ++index) {
            cached_command_t *entry = &context.cache[index];
            if (entry->used && (strcmp(entry->command.command_id, command->command_id) == 0)) { duplicate = entry; break; }
            if ((!entry->used) || (entry->retain_until < now)) { available = entry; }
        }
        if (duplicate != NULL) {
            /* Never execute a duplicate, including after disconnect or state expiry. */
            context.acknowledge(command, "rejected", "duplicate_command_no_reexecution");
            continue;
        }
        if (available == NULL) { context.acknowledge(command, "rejected", "dedupe_cache_full"); continue; }
        context.acknowledge(command, "accepted", "validated");
        const size_t control = (command->key == 'A') ? 0U : 1U;
        if (apply_output(control, command->value) != ESP_OK) {
            context.acknowledge(command, "rejected", "gpio_write_failed");
            continue;
        }
        context.controls[control] = command->value;
        /* Output watchdog uses monotonic time; an SNTP clock correction must
         * never extend a physical HIGH state beyond its lease. */
        context.lease_end[control] = uptime_now + CONFIG_NAV_CONTROL_TIMEOUT_MS;
        available->command = *command;
        available->retain_until = command->expires_at_ms + UINT64_C(60000);
        available->used = true;
#if CONFIG_NAV_PHYSICAL_CONTROLS
        context.acknowledge(command, "applied", "gpio_latch_applied");
#else
        context.acknowledge(command, "applied", "logical_state_only");
#endif
    }
}

void command_handler_state(uint8_t *control_a, uint8_t *control_b)
{
    /* Called only from the publisher owner task. */
    if (control_a != NULL) { *control_a = context.controls[0]; }
    if (control_b != NULL) { *control_b = context.controls[1]; }
}
