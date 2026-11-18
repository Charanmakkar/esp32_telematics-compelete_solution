#ifndef NAV_MQTT_MANAGER_H
#define NAV_MQTT_MANAGER_H
#include "app_config.h"
esp_err_t mqtt_manager_start(const app_config_t *config);
void vMqttPublishTask(void *argument);
bool mqtt_manager_publish_can(const char *frames, uint32_t queue_drops, uint32_t serial_drops,
    uint32_t publish_drops, uint32_t missed, uint32_t overruns, uint32_t bus_errors);
#endif
