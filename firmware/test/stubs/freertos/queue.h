#ifndef TEST_QUEUE_H
#define TEST_QUEUE_H
#include "FreeRTOS.h"
typedef struct {
    uint8_t *storage;
    size_t item_size;
    size_t capacity;
    size_t head;
    size_t tail;
    size_t count;
} StaticQueue_t;
typedef StaticQueue_t *QueueHandle_t;
QueueHandle_t xQueueCreateStatic(size_t capacity, size_t item_size, uint8_t *storage, StaticQueue_t *queue);
int xQueueSend(QueueHandle_t queue, const void *item, TickType_t timeout);
int xQueueReceive(QueueHandle_t queue, void *item, TickType_t timeout);
#endif
