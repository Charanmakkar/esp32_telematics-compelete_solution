#ifndef NAV_DIAGNOSTIC_ISOTP_H
#define NAV_DIAGNOSTIC_ISOTP_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define NAV_ISOTP_MAX 4095U
typedef bool (*nav_isotp_send_fn)(void *user, const uint8_t data[8]);
typedef struct {
    uint8_t tx[NAV_ISOTP_MAX], rx[NAV_ISOTP_MAX];
    size_t tx_len, tx_pos, rx_len, rx_pos;
    uint8_t tx_sn, rx_sn, block_size, block_sent, rx_block, waits;
    uint32_t stmin_us;
    uint64_t deadline, phase_deadline, next_tx;
    bool waiting_fc, done;
    const char *error;
    nav_isotp_send_fn send;
    void *user;
} nav_isotp_t;
bool nav_isotp_start(nav_isotp_t *s, const uint8_t *data, size_t length,
                     uint64_t now_us, uint32_t timeout_ms, nav_isotp_send_fn send, void *user);
void nav_isotp_frame(nav_isotp_t *s, const uint8_t *data, size_t dlc, uint64_t now_us);
void nav_isotp_poll(nav_isotp_t *s, uint64_t now_us);
void nav_isotp_wait_response(nav_isotp_t *s, uint64_t now_us);
#endif
