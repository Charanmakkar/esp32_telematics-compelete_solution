#include "diagnostic_isotp.h"
#include <string.h>
#define PHASE_TIMEOUT_US 1000000ULL
static bool emit(nav_isotp_t *s, const uint8_t data[8])
{
    if (!s->send(s->user, data)) { s->error = "can_transmit_failed"; return false; }
    return true;
}
bool nav_isotp_start(nav_isotp_t *s, const uint8_t *data, size_t length,
                     uint64_t now_us, uint32_t timeout_ms, nav_isotp_send_fn send, void *user)
{
    if (!s || !data || !send || !length || length > NAV_ISOTP_MAX || timeout_ms < 100 || timeout_ms > 60000) { return false; }
    memset(s, 0, sizeof(*s));
    memcpy(s->tx, data, length);
    s->tx_len = length; s->send = send; s->user = user;
    s->deadline = now_us + (uint64_t)timeout_ms * 1000;
    s->phase_deadline = s->deadline;
    s->tx_sn = 1; s->rx_sn = 1;
    uint8_t packet[8]; memset(packet, 0x55, sizeof(packet));
    if (length <= 7) {
        packet[0] = (uint8_t)length; memcpy(packet + 1, data, length);
        s->tx_pos = length;
    } else {
        packet[0] = 0x10 | (uint8_t)(length >> 8); packet[1] = (uint8_t)length;
        memcpy(packet + 2, data, 6); s->tx_pos = 6; s->waiting_fc = true;
        s->phase_deadline = now_us + PHASE_TIMEOUT_US;
    }
    return emit(s, packet);
}
void nav_isotp_wait_response(nav_isotp_t *s, uint64_t now_us)
{
    (void)now_us;
    s->done = false; s->rx_pos = 0; s->rx_len = 0; s->rx_sn = 1; s->rx_block = 0;
    s->phase_deadline = s->deadline; /* NRC 0x78 never extends the absolute deadline. */
}
static void flow_control(nav_isotp_t *s)
{
    const uint8_t fc[8] = {0x30, 8, 1, 0x55, 0x55, 0x55, 0x55, 0x55};
    (void)emit(s, fc); /* Blocks of 8, >=1 ms separation; bounded receive queue. */
}
void nav_isotp_frame(nav_isotp_t *s, const uint8_t *data, size_t dlc, uint64_t now_us)
{
    if (!s || s->error || s->done || !data || !dlc || dlc > 8) { return; }
    if (now_us >= s->deadline) { s->error = "response_timeout"; return; }
    unsigned type = data[0] >> 4;
    if (type == 3) {
        if (!s->waiting_fc || dlc < 3) { s->error = "unexpected_flow_control"; return; }
        unsigned status = data[0] & 15;
        if (status == 1) {
            if (++s->waits > 3) { s->error = "flow_control_wait_limit"; }
            else { s->phase_deadline = now_us + PHASE_TIMEOUT_US; }
            return;
        }
        if (status != 0) { s->error = "flow_control_rejected"; return; }
        uint8_t stmin = data[2];
        if (stmin <= 0x7F) { s->stmin_us = stmin * 1000U; }
        else if (stmin >= 0xF1 && stmin <= 0xF9) { s->stmin_us = (stmin - 0xF0) * 100U; }
        else { s->error = "invalid_stmin"; return; }
        s->block_size = data[1]; s->block_sent = 0; s->waiting_fc = false;
        s->next_tx = now_us + s->stmin_us; s->phase_deadline = s->deadline;
    } else if (type == 0) {
        size_t length = data[0] & 15;
        if (!length || length > 7 || dlc < length + 1 || s->rx_pos) { s->error = "invalid_single_frame"; return; }
        if (s->tx_pos < s->tx_len && data[1] != 0x7F) { s->error = "premature_response"; return; }
        memcpy(s->rx, data+1, length); s->rx_len = length; s->rx_pos = length; s->done = true;
    } else if (type == 1) {
        if (dlc != 8 || s->rx_pos || s->tx_pos < s->tx_len) { s->error = "unexpected_first_frame"; return; }
        size_t length = ((size_t)(data[0] & 15) << 8) | data[1];
        if (length < 8 || length > NAV_ISOTP_MAX) { s->error = "unsupported_isotp_length"; return; }
        s->rx_len = length; s->rx_pos = 6; s->rx_sn = 1; s->rx_block = 0;
        memcpy(s->rx, data+2, 6); s->phase_deadline = now_us + PHASE_TIMEOUT_US;
        flow_control(s);
    } else if (type == 2) {
        if (!s->rx_len || s->rx_pos >= s->rx_len || (data[0] & 15) != s->rx_sn) { s->error = "wrong_consecutive_sequence"; return; }
        size_t remaining = s->rx_len - s->rx_pos;
        size_t length = remaining > 7 ? 7 : remaining;
        if (dlc < length + 1) { s->error = "short_consecutive_frame"; return; }
        memcpy(s->rx + s->rx_pos, data+1, length); s->rx_pos += length;
        s->rx_sn = (s->rx_sn + 1) & 15; ++s->rx_block;
        s->phase_deadline = now_us + PHASE_TIMEOUT_US;
        if (s->rx_pos == s->rx_len) { s->done = true; }
        else if (s->rx_block == 8) { s->rx_block = 0; flow_control(s); }
    } else { s->error = "invalid_isotp_frame"; }
}
void nav_isotp_poll(nav_isotp_t *s, uint64_t now_us)
{
    if (!s || s->done || s->error) { return; }
    if (now_us >= s->deadline || now_us >= s->phase_deadline) { s->error = "response_timeout"; return; }
    if (s->waiting_fc || s->tx_pos == s->tx_len || now_us < s->next_tx) { return; }
    uint8_t packet[8]; memset(packet, 0x55, sizeof(packet));
    size_t length = s->tx_len - s->tx_pos;
    if (length > 7) { length = 7; }
    packet[0] = 0x20 | s->tx_sn;
    memcpy(packet+1, s->tx+s->tx_pos, length);
    if (!emit(s, packet)) { return; }
    s->tx_pos += length; s->tx_sn = (s->tx_sn+1) & 15;
    s->next_tx = now_us + s->stmin_us;
    if (s->block_size && ++s->block_sent == s->block_size && s->tx_pos < s->tx_len) {
        s->waiting_fc = true; s->phase_deadline = now_us + PHASE_TIMEOUT_US;
    }
}
