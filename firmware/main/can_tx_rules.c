#include "can_tx_rules.h"
#include "cJSON.h"
#include <math.h>
#include <string.h>

/* Fixed frames confirmed by the user; 0x548 supersedes the screenshot's 0x584.
   No rolling counter or checksum: repeat these exact bytes. */
const nav_can_tx_frame_t nav_can_tx_frames[2] = {
    {.id=0x014, .period_ms=100, .dlc=3, .data={0x00,0x60,0x00}},
    {.id=0x548, .period_ms=10, .dlc=8, .data={0,0,0,0,0,0,0,0x08}},
};

bool nav_can_tx_retry_arbitration(const nav_can_tx_bus_state_t *before,
    const nav_can_tx_bus_state_t *after, uint64_t elapsed_us, unsigned attempts)
{
    /* Losing arbitration is normal CAN contention, not a damaged frame.
       Never retry a bus/ACK error here, nor overrun the cyclic-send budget. */
    return before && after && elapsed_us < NAV_CAN_TX_SEND_BUDGET_US &&
        attempts < NAV_CAN_TX_MAX_ATTEMPTS &&
        after->arbitration_lost != before->arbitration_lost &&
        after->bus_errors == before->bus_errors && after->tx_errors == before->tx_errors;
}

static bool uuid(const char *value)
{
    if (!value || strlen(value) != 36) { return false; }
    for (unsigned i=0; i<36; ++i) {
        if (i==8 || i==13 || i==18 || i==23) { if (value[i]!='-') return false; }
        else if (!((value[i]>='0' && value[i]<='9') || (value[i]>='a' && value[i]<='f'))) return false;
    }
    return true;
}

static bool timestamp(const cJSON *item)
{
    return cJSON_IsNumber(item) && isfinite(item->valuedouble) &&
        item->valuedouble >= 1 && item->valuedouble <= 253402300799999.0 &&
        floor(item->valuedouble) == item->valuedouble;
}

bool nav_can_tx_parse(const char *json, size_t length, bool retained,
    const char *boot_id, uint64_t now, nav_can_tx_command_t *command)
{
    if (!json || !command || !boot_id || retained || !now || length==0 || length>=384 ||
        memchr(json, '\0', length)) { return false; }
    const char *end = NULL;
    cJSON *root = cJSON_ParseWithLengthOpts(json, length, &end, false);
    if (!root) { return false; }
    while (end < json+length && (*end==' ' || *end=='\r' || *end=='\n' || *end=='\t')) ++end;
    const cJSON *id=cJSON_GetObjectItemCaseSensitive(root,"command_id");
    const cJSON *boot=cJSON_GetObjectItemCaseSensitive(root,"boot_id");
    const cJSON *enabled=cJSON_GetObjectItemCaseSensitive(root,"enabled");
    const cJSON *issued=cJSON_GetObjectItemCaseSensitive(root,"issued_at_ms");
    const cJSON *expires=cJSON_GetObjectItemCaseSensitive(root,"expires_at_ms");
    bool valid = cJSON_IsObject(root) && cJSON_GetArraySize(root)==5 && end==json+length &&
        cJSON_IsString(id) && uuid(id->valuestring) && cJSON_IsString(boot) &&
        strcmp(boot->valuestring,boot_id)==0 && cJSON_IsBool(enabled) &&
        timestamp(issued) && timestamp(expires);
    if (valid) {
        uint64_t start=(uint64_t)issued->valuedouble, finish=(uint64_t)expires->valuedouble;
        valid = finish>start && finish-start<=5000 && now<finish && start<=now+1000;
        if (valid) {
            memcpy(command->command_id,id->valuestring,37);
            command->enabled=cJSON_IsTrue(enabled);
            command->issued_at_ms=start; command->expires_at_ms=finish;
        }
    }
    cJSON_Delete(root);
    return valid;
}
