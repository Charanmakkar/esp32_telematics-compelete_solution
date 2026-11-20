#ifndef NAV_MQTT_MANAGER_H
#define NAV_MQTT_MANAGER_H
#include "app_config.h"
esp_err_t mqtt_manager_start(const app_config_t *config);
void vMqttPublishTask(void *argument);
bool mqtt_manager_publish_can(const char *frames, uint32_t queue_drops, uint32_t serial_drops,
    uint32_t publish_drops, const char *statistics);
bool mqtt_manager_diagnostic_publish(const char *json);
bool mqtt_manager_is_connected(void);
bool mqtt_manager_ota_publish(const char *suffix, const char *json);
bool mqtt_manager_transport_tls(void);
void mqtt_manager_reserve_ota_reply(bool reserve);
const char *mqtt_manager_boot_id(void);
void mqtt_manager_reserve_diagnostic_reply(bool reserve);
#endif
