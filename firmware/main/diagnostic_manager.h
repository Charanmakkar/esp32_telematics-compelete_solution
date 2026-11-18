#pragma once
#include "esp_err.h"
#include "mqtt_client.h"
#include "driver/twai.h"
esp_err_t diagnostic_manager_init(void);
void diagnostic_manager_fragment(const esp_mqtt_event_t *event, bool topic_matches);
void diagnostic_manager_frame(const twai_message_t *frame);
