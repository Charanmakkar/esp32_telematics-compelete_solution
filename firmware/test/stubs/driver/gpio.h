#ifndef TEST_GPIO_H
#define TEST_GPIO_H
#include <stdint.h>
#include "esp_err.h"
typedef int gpio_num_t;
typedef struct {
    uint64_t pin_bit_mask;
    int mode, pull_up_en, pull_down_en, intr_type;
} gpio_config_t;
#define GPIO_MODE_OUTPUT 1
#define GPIO_PULLUP_DISABLE 0
#define GPIO_PULLDOWN_DISABLE 0
#define GPIO_INTR_DISABLE 0
esp_err_t gpio_set_level(gpio_num_t pin, uint32_t value);
esp_err_t gpio_config(const gpio_config_t *config);
#endif
