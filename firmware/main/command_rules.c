#include "command_rules.h"
#include <stddef.h>
#include <ctype.h>
#include <string.h>

bool command_id_valid(const char *identifier)
{
    if ((identifier == NULL) || (strlen(identifier) != 36U)) { return false; }
    for (size_t index = 0U; index < 36U; ++index) {
        if ((index == 8U) || (index == 13U) || (index == 18U) || (index == 23U)) {
            if (identifier[index] != '-') { return false; }
        } else if (!isxdigit((unsigned char)identifier[index])) { return false; }
    }
    return true;
}

const char *command_rules_validate(const nav_command_t *command, bool retained,
    bool time_valid, uint64_t now_ms, uint32_t max_ttl_ms)
{
    if (command == NULL) { return "invalid_command"; }
    if (!command_id_valid(command->command_id)) { return "invalid_command_id"; }
    if ((command->key != 'A') && (command->key != 'B')) { return "invalid_key"; }
    if (command->value > 1U) { return "invalid_value"; }
    if (retained) { return "retained_command_forbidden"; }
    if (!time_valid) { return "clock_unsynchronized"; }
    if ((command->issued_at_ms > now_ms) && ((command->issued_at_ms - now_ms) > 2000U)) { return "future_command"; }
    if ((command->expires_at_ms <= now_ms) || (command->expires_at_ms <= command->issued_at_ms)) { return "expired"; }
    if ((command->expires_at_ms - command->issued_at_ms) > max_ttl_ms) { return "ttl_exceeded"; }
    return NULL;
}
