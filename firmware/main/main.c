#include "app_config.h"
#include "adc_manager.h"
#include "mqtt_manager.h"
#include "command_handler.h"
#include "wifi_manager.h"
#include "can_manager.h"
#include "sw_version.h"
#include "esp_log.h"
#include "nvs_flash.h"

void app_main(void)
{
    ESP_LOGI("navsphere", "SW_VERSION=%s BUILD=%s UTC=%s", SW_VERSION, SW_BUILD_ID, SW_BUILD_UTC);
    /* Do not erase NVS automatically: it contains provisioned credentials. */
    ESP_ERROR_CHECK(nvs_flash_init());
    ESP_ERROR_CHECK(command_handler_safe_start());
    static app_config_t config;
    const esp_err_t result = app_config_load(&config);
    if (result != ESP_OK) {
        ESP_LOGW("navsphere", "Credentials unavailable; provision NVS before network use (%s)",
                 esp_err_to_name(result));
    }
    ESP_ERROR_CHECK(adc_manager_start());
    if (result == ESP_OK) {
        ESP_ERROR_CHECK(wifi_manager_start(&config));
        ESP_ERROR_CHECK(mqtt_manager_start(&config));
    }
    const esp_err_t can_result = can_manager_start();
    if (can_result != ESP_OK) { ESP_LOGE("can", "CAN startup failed: %s", esp_err_to_name(can_result)); }
}
