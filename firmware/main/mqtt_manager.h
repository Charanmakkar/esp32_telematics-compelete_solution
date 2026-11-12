#ifndef NAV_MQTT_MANAGER_H
#define NAV_MQTT_MANAGER_H
#include "app_config.h"
esp_err_t mqtt_manager_start(const app_config_t *config);
void vMqttPublishTask(void *argument);
#endif
