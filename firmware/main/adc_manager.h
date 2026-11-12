#ifndef NAV_ADC_MANAGER_H
#define NAV_ADC_MANAGER_H
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "telemetry_types.h"

esp_err_t adc_manager_start(void);
bool adc_manager_take(adc_telemetry_t *sample);
uint32_t adc_manager_dropped(void);
void vAnalogAcquisitionTask(void *argument);
#endif
