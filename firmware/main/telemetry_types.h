#ifndef NAV_TELEMETRY_TYPES_H
#define NAV_TELEMETRY_TYPES_H
#include <stdbool.h>
#include <stdint.h>
#include "app_config.h"

typedef struct {
    uint32_t adc_raw[NAV_CHANNEL_COUNT];
    uint32_t adc_mv[NAV_CHANNEL_COUNT];
    uint64_t timestamp_ms;
    uint64_t uptime_ms;
    uint32_t sample_sequence;
    uint16_t valid_mask;
    bool time_valid;
} adc_telemetry_t;
#endif
