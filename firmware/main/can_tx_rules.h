#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint32_t id;
    uint32_t period_ms;
    uint8_t dlc;
    uint8_t data[8];
} nav_can_tx_frame_t;

extern const nav_can_tx_frame_t nav_can_tx_frames[2];
#define NAV_CAN_TX_SEND_BUDGET_US 5000U
#define NAV_CAN_TX_MAX_ATTEMPTS 16U
typedef struct {
    uint32_t arbitration_lost;
    uint32_t bus_errors;
    uint32_t tx_errors;
} nav_can_tx_bus_state_t;
bool nav_can_tx_retry_arbitration(const nav_can_tx_bus_state_t *before,
    const nav_can_tx_bus_state_t *after, uint64_t elapsed_us, unsigned attempts);
typedef struct {
    char command_id[37];
    bool enabled;
    uint64_t issued_at_ms;
    uint64_t expires_at_ms;
} nav_can_tx_command_t;

bool nav_can_tx_parse(const char *json, size_t length, bool retained,
    const char *boot_id, uint64_t now, nav_can_tx_command_t *command);
