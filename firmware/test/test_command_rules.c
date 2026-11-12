#include "command_rules.h"
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

int main(void)
{
    nav_command_t command = { .command_id = "12345678-abcd-1234-abcd-123456789abc",
        .key = 'A', .value = 1U, .issued_at_ms = 10000U, .expires_at_ms = 20000U };
    assert(command_rules_validate(&command, false, true, 11000U, 30000U) == NULL);
    assert(strcmp(command_rules_validate(&command, true, true, 11000U, 30000U), "retained_command_forbidden") == 0);
    assert(strcmp(command_rules_validate(&command, false, false, 11000U, 30000U), "clock_unsynchronized") == 0);
    assert(strcmp(command_rules_validate(&command, false, true, 20000U, 30000U), "expired") == 0);
    assert(strcmp(command_rules_validate(&command, false, true, 11000U, 1000U), "ttl_exceeded") == 0);
    assert(strcmp(command_rules_validate(&command, false, true, 5000U, 30000U), "future_command") == 0);
    command.key = 'C';
    assert(strcmp(command_rules_validate(&command, false, true, 11000U, 30000U), "invalid_key") == 0);
    command.key = 'B'; command.value = 2U;
    assert(strcmp(command_rules_validate(&command, false, true, 11000U, 30000U), "invalid_value") == 0);
    assert(!command_id_valid(NULL));
    assert(!command_id_valid(""));
    assert(!command_id_valid("12345678-abcd-1234-abcd-123456789abg"));
    assert(!command_id_valid("12345678xabcd-1234-abcd-123456789abc"));
    assert(command_rules_validate(NULL, false, false, 0U, 0U) != NULL);
    puts("13 command rule assertions passed");
    return 0;
}
