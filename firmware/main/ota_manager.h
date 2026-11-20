#pragma once
#include "esp_err.h"
#include "mqtt_client.h"
esp_err_t ota_manager_start(bool startup_healthy);
void ota_manager_fragment(const esp_mqtt_event_t *event, bool matches);
