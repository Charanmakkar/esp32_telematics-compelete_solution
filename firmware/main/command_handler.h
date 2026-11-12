#ifndef NAV_COMMAND_HANDLER_H
#define NAV_COMMAND_HANDLER_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
#include "command_rules.h"
typedef void (*command_ack_fn)(const nav_command_t *, const char *, const char *);
esp_err_t command_handler_safe_start(void);
esp_err_t command_handler_init(command_ack_fn acknowledge);
void command_handler_receive(const char *data, size_t length, bool retained);
void command_handler_tick(bool connected);
void command_handler_state(uint8_t *control_a, uint8_t *control_b);
#endif
