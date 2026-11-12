#include "app_config.h"
#include <ctype.h>
#include <stddef.h>
#include <string.h>
#include <sys/time.h>
#include "esp_timer.h"
#include "nvs.h"

static esp_err_t read_string(nvs_handle_t handle, const char *key, char *output, size_t size)
{
    size_t length = size;
    const esp_err_t result = nvs_get_str(handle, key, output, &length);
    if ((result != ESP_OK) || (length < 2U)) {
        output[0] = '\0';
        return ESP_ERR_INVALID_STATE;
    }
    return ESP_OK;
}

esp_err_t app_config_load(app_config_t *config)
{
    if (config == NULL) { return ESP_ERR_INVALID_ARG; }
    const char *prefix = CONFIG_NAV_MQTT_TOPIC_PREFIX;
    const size_t prefix_size = strlen(prefix);
    if ((prefix_size == 0U) || (prefix_size > 64U)) { return ESP_ERR_INVALID_ARG; }
    for (size_t index = 0U; index < prefix_size; ++index) {
        const unsigned char value = (unsigned char)prefix[index];
        if ((!((value >= 'A') && (value <= 'Z'))) && (!((value >= 'a') && (value <= 'z'))) &&
            (!((value >= '0') && (value <= '9'))) && (value != '_') && (value != '-')) { return ESP_ERR_INVALID_ARG; }
    }
    memset(config, 0, sizeof(*config));
    nvs_handle_t handle;
    esp_err_t result = nvs_open("navsphere", NVS_READONLY, &handle);
    if (result != ESP_OK) { return result; }
    result = read_string(handle, "wifi_ssid", config->wifi_ssid, sizeof(config->wifi_ssid));
    size_t size = sizeof(config->wifi_password);
    /* An empty Wi-Fi password is supported only for deliberately open development networks. */
    if (nvs_get_str(handle, "wifi_pass", config->wifi_password, &size) != ESP_OK) { result = ESP_ERR_INVALID_STATE; }
    if (read_string(handle, "mqtt_uri", config->mqtt_uri, sizeof(config->mqtt_uri)) != ESP_OK) { result = ESP_ERR_INVALID_STATE; }
    if (read_string(handle, "mqtt_user", config->mqtt_username, sizeof(config->mqtt_username)) != ESP_OK) { result = ESP_ERR_INVALID_STATE; }
    if (read_string(handle, "mqtt_pass", config->mqtt_password, sizeof(config->mqtt_password)) != ESP_OK) { result = ESP_ERR_INVALID_STATE; }
    if (read_string(handle, "device_id", config->device_id, sizeof(config->device_id)) != ESP_OK) { result = ESP_ERR_INVALID_STATE; }
    nvs_close(handle);
    for (size_t index = 0U; config->device_id[index] != '\0'; ++index) {
        const unsigned char character = (unsigned char)config->device_id[index];
        if ((!isalnum(character)) && (character != '_') && (character != '-')) { result = ESP_ERR_INVALID_ARG; }
    }
    const bool tls = strncmp(config->mqtt_uri, "mqtts://", 8U) == 0;
    if ((!tls) && (strncmp(config->mqtt_uri, "mqtt://", 7U) != 0)) { result = ESP_ERR_INVALID_ARG; }
#if CONFIG_NAV_REQUIRE_TLS
    if (!tls) { result = ESP_ERR_INVALID_ARG; }
#endif
    return result;
}

uint64_t app_uptime_ms(void)
{
    return (uint64_t)esp_timer_get_time() / UINT64_C(1000);
}

bool app_epoch_ms(uint64_t *timestamp_ms)
{
    if (timestamp_ms == NULL) { return false; }
    struct timeval now;
    if ((gettimeofday(&now, NULL) != 0) || (now.tv_sec < 1704067200)) {
        *timestamp_ms = 0U;
        return false;
    }
    *timestamp_ms = ((uint64_t)now.tv_sec * UINT64_C(1000)) + ((uint64_t)now.tv_usec / UINT64_C(1000));
    return true;
}
