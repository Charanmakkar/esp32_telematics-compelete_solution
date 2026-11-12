#ifndef NAV_WIFI_MANAGER_H
#define NAV_WIFI_MANAGER_H
#include <stdbool.h>
#include "app_config.h"
esp_err_t wifi_manager_start(const app_config_t *config);
bool wifi_manager_connected(void);
#endif
