#include "command_handler.h"
#include "freertos/queue.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint64_t now_ms = 11000U;
static uint64_t uptime_ms = 11000U;
static bool clock_valid = true;
static unsigned int accepted;
static unsigned int applied;
static unsigned int rejected;

QueueHandle_t xQueueCreateStatic(size_t capacity, size_t item_size, uint8_t *storage, StaticQueue_t *queue)
{
    *queue = (StaticQueue_t){ .storage = storage, .item_size = item_size, .capacity = capacity };
    return queue;
}
int xQueueSend(QueueHandle_t queue, const void *item, TickType_t timeout)
{
    (void)timeout;
    if (queue->count == queue->capacity) { return 0; }
    memcpy(queue->storage + (queue->tail * queue->item_size), item, queue->item_size);
    queue->tail = (queue->tail + 1U) % queue->capacity;
    ++queue->count;
    return pdPASS;
}
int xQueueReceive(QueueHandle_t queue, void *item, TickType_t timeout)
{
    (void)timeout;
    if (queue->count == 0U) { return 0; }
    memcpy(item, queue->storage + (queue->head * queue->item_size), queue->item_size);
    queue->head = (queue->head + 1U) % queue->capacity;
    --queue->count;
    return pdPASS;
}
bool app_epoch_ms(uint64_t *output) { *output = now_ms; return clock_valid; }
uint64_t app_uptime_ms(void) { return uptime_ms; }

static void acknowledge(const nav_command_t *command, const char *status, const char *reason)
{
    assert(command != NULL); assert(reason != NULL);
    if (strcmp(status, "accepted") == 0) { ++accepted; }
    else if (strcmp(status, "applied") == 0) { ++applied; }
    else if (strcmp(status, "rejected") == 0) { ++rejected; }
    else { assert(false); }
}

static void submit(const char *json, bool retained) { command_handler_receive(json, strlen(json), retained); }

int main(void)
{
    const char *valid = "{\"command_id\":\"12345678-abcd-1234-abcd-123456789abc\",\"key\":\"A\",\"value\":1,\"issued_at_ms\":10000,\"expires_at_ms\":20000}";
    assert(command_handler_safe_start() == ESP_OK);
    assert(command_handler_init(acknowledge) == ESP_OK);
    submit(valid, false); command_handler_tick(true);
    uint8_t a, b;
    command_handler_state(&a, &b);
    assert(a == 1U && b == 0U && accepted == 1U && applied == 1U && rejected == 0U);
    submit(valid, false); command_handler_tick(true);
    assert(applied == 1U && rejected == 1U);
    submit(valid, true); command_handler_tick(true);
    assert(applied == 1U && rejected == 2U);
    submit("{\"command_id\":\"12345678-abcd-1234-abcd-123456789abd\",\"key\":\"A\",\"value\":true,\"issued_at_ms\":10000,\"expires_at_ms\":20000}", false);
    command_handler_tick(true); assert(applied == 1U && rejected == 3U);
    submit("{\"command_id\":\"12345678-abcd-1234-abcd-123456789abd\",\"key\":\"A\",\"key\":\"B\",\"value\":1,\"issued_at_ms\":10000,\"expires_at_ms\":20000}", false);
    command_handler_tick(true); assert(applied == 1U && rejected == 4U);
    submit("{\"command_id\":\"12345678-abcd-1234-abcd-123456789abd\",\"key\":\"A\",\"value\":0.5,\"issued_at_ms\":10000,\"expires_at_ms\":20000}", false);
    command_handler_tick(true); assert(applied == 1U && rejected == 5U);
    submit("{\"command_id\":\"12345678-abcd-1234-abcd-123456789abd\",\"key\":\"C\",\"value\":1,\"issued_at_ms\":10000,\"expires_at_ms\":20000}", false);
    command_handler_tick(true); assert(applied == 1U && rejected == 6U);
    submit("{bad json", false); submit("[[[[[[[[[[1]]]]]]]]]]", false);
    command_handler_tick(true); assert(applied == 1U && rejected == 6U);
    command_handler_tick(false); command_handler_state(&a, &b); assert(a == 0U && b == 0U);
    submit(valid, false); command_handler_tick(true); command_handler_state(&a, &b);
    assert(a == 0U && rejected == 7U); /* no re-execution after safe reset */
    const char *second = "{\"command_id\":\"12345678-abcd-1234-abcd-123456789abd\",\"key\":\"B\",\"value\":1,\"issued_at_ms\":10000,\"expires_at_ms\":20000}";
    submit(second, false); command_handler_tick(true); command_handler_state(&a, &b);
    assert(b == 1U && applied == 2U);
    now_ms = 9000U; uptime_ms = 72000U;
    command_handler_tick(true); command_handler_state(&a, &b);
    assert(a == 0U && b == 0U); /* watchdog survives a backwards epoch correction */
    now_ms = 11000U; uptime_ms = 11000U; clock_valid = false;
    submit(second, false); command_handler_tick(true); assert(applied == 2U && rejected == 8U);
    clock_valid = true;
    for (unsigned int index = 0U; index < 9U; ++index) { submit(second, false); }
    assert(rejected == 9U); /* ninth refused before queued processing */
    command_handler_tick(true); assert(applied == 2U && rejected == 17U);
    puts("Command parser, duplicate, expiry, safe-state, and bounded queue tests passed");
    return 0;
}
