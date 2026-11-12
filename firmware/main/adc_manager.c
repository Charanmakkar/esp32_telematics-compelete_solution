#include "adc_manager.h"
#include <stddef.h>
#include <string.h>
#include "driver/gpio.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_adc/adc_cali.h"
#include "esp_adc/adc_cali_scheme.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

/* Six user-confirmed native ADC1 inputs on ESP32-WROOM. No ADC2 is used. */
#define analogPin_GPIO32 GPIO_NUM_32
#define analogPin_GPIO33 GPIO_NUM_33
#define analogPin_GPIO34 GPIO_NUM_34
#define analogPin_GPIO35 GPIO_NUM_35
#define analogPin_GPIO36 GPIO_NUM_36
#define analogPin_GPIO39 GPIO_NUM_39

typedef struct {
    QueueHandle_t queue;
    StaticQueue_t queue_control;
    uint8_t queue_storage[NAV_TELEMETRY_QUEUE_LENGTH * sizeof(adc_telemetry_t)];
    portMUX_TYPE counter_lock;
    uint32_t dropped;
    bool hardware_ready;
    adc_oneshot_unit_handle_t adc;
    adc_cali_handle_t calibration;
    adc_channel_t channels[NAV_CHANNEL_COUNT];
} adc_context_t;

static adc_context_t context = { .counter_lock = portMUX_INITIALIZER_UNLOCKED };

#if CONFIG_NAV_HARDWARE_CONFIRMED
static esp_err_t initialize_hardware(adc_context_t *state)
{
    const int native_pins[6] = { analogPin_GPIO32, analogPin_GPIO33, analogPin_GPIO34,
        analogPin_GPIO35, analogPin_GPIO36, analogPin_GPIO39 };
    const adc_oneshot_unit_init_cfg_t init = { .unit_id = ADC_UNIT_1 };
    esp_err_t result = adc_oneshot_new_unit(&init, &state->adc);
    if (result != ESP_OK) { return result; }
    const adc_oneshot_chan_cfg_t channel_config = { .atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_12 };
    for (size_t index = 0U; index < NAV_CHANNEL_COUNT; ++index) {
        adc_unit_t unit;
        const int pin = native_pins[index];
        result = adc_oneshot_io_to_channel(pin, &unit, &state->channels[index]);
        if ((result != ESP_OK) || (unit != ADC_UNIT_1)) { return ESP_ERR_INVALID_ARG; }
        result = adc_oneshot_config_channel(state->adc, state->channels[index], &channel_config);
        if (result != ESP_OK) { return result; }
    }
    adc_cali_line_fitting_efuse_val_t efuse;
    result = adc_cali_scheme_line_fitting_check_efuse(&efuse);
    if ((result != ESP_OK) || (efuse == ADC_CALI_LINE_FITTING_EFUSE_VAL_DEFAULT_VREF)) {
        /* Do not label an assumed Vref conversion as calibrated millivolts. */
        return ESP_ERR_NOT_SUPPORTED;
    }
    const adc_cali_line_fitting_config_t calibration = {
        .unit_id = ADC_UNIT_1, .atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_12, .default_vref = 0U
    };
    result = adc_cali_create_scheme_line_fitting(&calibration, &state->calibration);
    if (result != ESP_OK) { return result; }
    return ESP_OK;
}

static void acquire_channels(adc_context_t *state, adc_telemetry_t *sample)
{
    for (uint32_t channel = 0U; channel < NAV_CHANNEL_COUNT; ++channel) {
        bool valid = true;
        uint32_t sum = 0U;
        for (uint32_t iteration = 0U; iteration < CONFIG_NAV_ADC_AVERAGES; ++iteration) {
            int raw = 0;
            if ((adc_oneshot_read(state->adc, state->channels[channel], &raw) != ESP_OK) || (raw < 0) || (raw > 4095)) {
                valid = false;
            } else { sum += (uint32_t)raw; }
        }
        sample->adc_raw[channel] = sum / CONFIG_NAV_ADC_AVERAGES;
        int millivolts = 0;
        if (valid && (adc_cali_raw_to_voltage(state->calibration, (int)sample->adc_raw[channel], &millivolts) == ESP_OK)
            && (millivolts >= 0) && (millivolts <= 3300)) {
            sample->adc_mv[channel] = (uint32_t)millivolts;
            sample->valid_mask |= (uint16_t)(1U << channel);
        }
    }
}
#endif

void vAnalogAcquisitionTask(void *argument)
{
    adc_context_t *state = (adc_context_t *)argument;
    TickType_t wake = xTaskGetTickCount();
    uint32_t sequence = 0U;
    for (;;) {
        adc_telemetry_t sample = {0};
        sample.uptime_ms = app_uptime_ms();
        sample.time_valid = app_epoch_ms(&sample.timestamp_ms);
        sample.sample_sequence = sequence++;
        /* Unsigned sequence wrap is defined; boot_id + sequence dedupe remains
         * unique for 13.6 years at 10Hz. Reboot before wrap for longer uptime. */
#if CONFIG_NAV_HARDWARE_CONFIRMED
        if (state->hardware_ready) { acquire_channels(state, &sample); }
#endif
        if (xQueueSend(state->queue, &sample, 0U) != pdPASS) {
            adc_telemetry_t discarded;
            if (xQueueReceive(state->queue, &discarded, 0U) == pdPASS) {
                portENTER_CRITICAL(&state->counter_lock);
                ++state->dropped;
                portEXIT_CRITICAL(&state->counter_lock);
            }
            if (xQueueSend(state->queue, &sample, 0U) != pdPASS) {
                portENTER_CRITICAL(&state->counter_lock);
                ++state->dropped;
                portEXIT_CRITICAL(&state->counter_lock);
            }
        }
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(CONFIG_NAV_ADC_SAMPLE_MS));
    }
}

esp_err_t adc_manager_start(void)
{
    if (context.queue != NULL) { return ESP_ERR_INVALID_STATE; }
    context.queue = xQueueCreateStatic(NAV_TELEMETRY_QUEUE_LENGTH, sizeof(adc_telemetry_t),
        context.queue_storage, &context.queue_control);
    if (context.queue == NULL) { return ESP_ERR_NO_MEM; }
#if CONFIG_NAV_HARDWARE_CONFIRMED
    const esp_err_t result = initialize_hardware(&context);
    context.hardware_ready = result == ESP_OK;
    if (!context.hardware_ready) {
        ESP_LOGE("adc", "Hardware initialization refused (%s); channels unavailable", esp_err_to_name(result));
    }
#else
    ESP_LOGW("adc", "Hardware disabled: no ADC access; all six channels unavailable");
#endif
    if (xTaskCreate(vAnalogAcquisitionTask, "nav_adc", 4096U, &context, 5U, NULL) != pdPASS) { return ESP_ERR_NO_MEM; }
    return ESP_OK;
}

bool adc_manager_take(adc_telemetry_t *sample)
{
    return (sample != NULL) && (context.queue != NULL) && (xQueueReceive(context.queue, sample, 0U) == pdPASS);
}

uint32_t adc_manager_dropped(void)
{
    portENTER_CRITICAL(&context.counter_lock);
    const uint32_t result = context.dropped;
    portEXIT_CRITICAL(&context.counter_lock);
    return result;
}
