idf_component_register(SRCS "ota_manager.c" "diagnostic_isotp.c" "diagnostic_manager.c" "main.c" "app_config.c" "adc_manager.c"
    "wifi_manager.c" "mqtt_manager.c" "command_handler.c" "command_rules.c" "can_manager.c" "can_tx.c" "can_tx_rules.c"
    INCLUDE_DIRS "."
    REQUIRES esp_wifi esp_event esp_netif nvs_flash esp_adc esp_driver_gpio
             esp_timer esp_system lwip mqtt cjson mbedtls driver app_update
    PRIV_REQUIRES esp_app_format)
target_compile_features(${COMPONENT_LIB} PRIVATE c_std_11)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra -Wformat=2)
