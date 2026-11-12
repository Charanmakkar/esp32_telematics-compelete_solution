#include "wifi_manager.h"
#include <string.h>
#include "esp_event.h"
#include "esp_check.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_netif_sntp.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "freertos/task.h"

typedef struct { EventGroupHandle_t events; StaticEventGroup_t storage; } wifi_context_t;
static wifi_context_t context;

static void wifi_event(void *argument, esp_event_base_t base, int32_t id, void *data)
{
    (void)data;
    wifi_context_t *state = (wifi_context_t *)argument;
    if ((base == IP_EVENT) && (id == IP_EVENT_STA_GOT_IP)) {
        (void)xEventGroupSetBits(state->events, NAV_WIFI_CONNECTED_BIT);
        ESP_LOGI("wifi", "IP acquired");
    } else if ((base == WIFI_EVENT) && (id == WIFI_EVENT_STA_DISCONNECTED)) {
        (void)xEventGroupClearBits(state->events, NAV_WIFI_CONNECTED_BIT);
        ESP_LOGW("wifi", "Disconnected; bounded reconnect worker will retry");
    }
}

static void reconnect_task(void *argument)
{
    wifi_context_t *state = (wifi_context_t *)argument;
    uint32_t backoff_ms = 1000U;
    for (;;) {
        if ((xEventGroupGetBits(state->events) & NAV_WIFI_CONNECTED_BIT) == 0U) {
            const esp_err_t result = esp_wifi_connect();
            if ((result != ESP_OK) && (result != ESP_ERR_WIFI_CONN)) {
                ESP_LOGW("wifi", "Connect request failed: %s", esp_err_to_name(result));
            }
            const EventBits_t bits = xEventGroupWaitBits(state->events, NAV_WIFI_CONNECTED_BIT,
                pdFALSE, pdFALSE, pdMS_TO_TICKS(backoff_ms));
            if ((bits & NAV_WIFI_CONNECTED_BIT) != 0U) { backoff_ms = 1000U; }
            else if (backoff_ms < 30000U) { backoff_ms = (backoff_ms * 2U > 30000U) ? 30000U : backoff_ms * 2U; }
        } else {
            backoff_ms = 1000U;
            vTaskDelay(pdMS_TO_TICKS(1000U));
        }
    }
}

esp_err_t wifi_manager_start(const app_config_t *config)
{
    if ((config == NULL) || (context.events != NULL)) { return ESP_ERR_INVALID_ARG; }
    context.events = xEventGroupCreateStatic(&context.storage);
    ESP_RETURN_ON_ERROR(esp_netif_init(), "wifi", "netif");
    ESP_RETURN_ON_ERROR(esp_event_loop_create_default(), "wifi", "event loop");
    if (esp_netif_create_default_wifi_sta() == NULL) { return ESP_ERR_NO_MEM; }
    const wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_RETURN_ON_ERROR(esp_wifi_init(&init), "wifi", "init");
    ESP_RETURN_ON_ERROR(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event, &context), "wifi", "event");
    ESP_RETURN_ON_ERROR(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_event, &context), "wifi", "IP event");
    wifi_config_t station = {0};
    memcpy(station.sta.ssid, config->wifi_ssid, strlen(config->wifi_ssid));
    memcpy(station.sta.password, config->wifi_password, strlen(config->wifi_password));
    station.sta.threshold.authmode = (config->wifi_password[0] != '\0') ? WIFI_AUTH_WPA2_PSK : WIFI_AUTH_OPEN;
    station.sta.pmf_cfg.capable = true;
    ESP_RETURN_ON_ERROR(esp_wifi_set_storage(WIFI_STORAGE_RAM), "wifi", "RAM storage");
    ESP_RETURN_ON_ERROR(esp_wifi_set_mode(WIFI_MODE_STA), "wifi", "mode");
    ESP_RETURN_ON_ERROR(esp_wifi_set_config(WIFI_IF_STA, &station), "wifi", "configuration");
    ESP_RETURN_ON_ERROR(esp_wifi_start(), "wifi", "start");
    esp_sntp_config_t time_config = ESP_NETIF_SNTP_DEFAULT_CONFIG(CONFIG_NAV_SNTP_SERVER);
    ESP_RETURN_ON_ERROR(esp_netif_sntp_init(&time_config), "wifi", "SNTP");
    if (xTaskCreate(reconnect_task, "nav_wifi", 3072U, &context, 3U, NULL) != pdPASS) { return ESP_ERR_NO_MEM; }
    return ESP_OK;
}

bool wifi_manager_connected(void)
{
    return (context.events != NULL) && ((xEventGroupGetBits(context.events) & NAV_WIFI_CONNECTED_BIT) != 0U);
}
