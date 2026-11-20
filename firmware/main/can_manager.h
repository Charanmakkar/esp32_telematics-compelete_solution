#pragma once
#include "esp_err.h"
#include "driver/twai.h"
#include <stdbool.h>
#include <stddef.h>
esp_err_t can_manager_start(void);
esp_err_t can_manager_diagnostic_mode(bool enabled);
esp_err_t can_manager_periodic_mode(bool enabled);
bool can_manager_send_periodic(unsigned index);
bool can_manager_send(uint32_t id, const uint8_t data[8]);
void can_manager_stats(char *json, size_t capacity);
esp_err_t can_manager_ota_lock(bool acquire);
