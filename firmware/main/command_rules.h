#ifndef NAV_COMMAND_RULES_H
#define NAV_COMMAND_RULES_H
#include <stdbool.h>
#include <stdint.h>
#define NAV_COMMAND_ID_SIZE (37U)
typedef struct {
    char command_id[NAV_COMMAND_ID_SIZE];
    char key;
    uint8_t value;
    uint64_t issued_at_ms;
    uint64_t expires_at_ms;
} nav_command_t;
bool command_id_valid(const char *identifier);
const char *command_rules_validate(const nav_command_t *command, bool retained,
    bool time_valid, uint64_t now_ms, uint32_t max_ttl_ms);
#endif
