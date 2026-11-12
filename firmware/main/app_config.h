#ifndef NAV_APP_CONFIG_H
#define NAV_APP_CONFIG_H

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "sdkconfig.h"

#define NAV_CHANNEL_COUNT (6U)
#define MQTT_BROKER_IP "192.168.9.59"
#define MQTT_BROKER_PORT (1883U)
#define MQTT_PUBLISH_MS (100U)
#define MQTT_QOS (1U)
#define MQTT_KEEPALIVE_SEC (60U)
#define NAV_JSON_CAPACITY (2048U)
#define NAV_COMMAND_CAPACITY (512U)
#define NAV_TOPIC_CAPACITY (160U)
#define NAV_TELEMETRY_QUEUE_LENGTH (4U)
#define NAV_MQTT_OUTBOX_BYTES (16384U)
#define NAV_WIFI_CONNECTED_BIT BIT0
#define NAV_MQTT_CONNECTED_BIT BIT0

typedef struct {
    char wifi_ssid[33];
    char wifi_password[65];
    char mqtt_uri[160];
    char mqtt_username[65];
    char mqtt_password[129];
    char device_id[65];
} app_config_t;

esp_err_t app_config_load(app_config_t *config);
uint64_t app_uptime_ms(void);
bool app_epoch_ms(uint64_t *timestamp_ms);
#endif
