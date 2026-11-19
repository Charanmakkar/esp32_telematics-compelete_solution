#pragma once
#include "esp_err.h"
#include <stdbool.h>
#include <stddef.h>

esp_err_t can_tx_start(void);
void can_tx_receive(const char *json, size_t length, bool retained);
void can_tx_disconnect(void);
void can_tx_stats(char *json, size_t capacity);
