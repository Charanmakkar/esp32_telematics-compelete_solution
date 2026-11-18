#pragma once
#include <stdbool.h>
#include <stdint.h>

static inline bool nav_diag_tx_allowed(uint32_t tx)
{
    return (tx >= 0x640 && tx <= 0x64F) || tx == 0x7DF || tx == 0x7E4;
}

static inline bool nav_diag_pair_allowed(uint32_t tx, uint32_t rx)
{
    return (tx >= 0x640 && tx <= 0x64F && rx == tx + 0x10) ||
           (tx == 0x7E4 && rx == 0x7EC) ||
           (tx == 0x7DF && ((rx >= 0x650 && rx <= 0x65F) || rx == 0x7EC));
}
