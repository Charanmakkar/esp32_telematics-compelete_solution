#include "can_tx_rules.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static const char *boot="12345678-1234-1234-1234-123456789abc";
static bool parse(const char *json, bool retained, uint64_t now)
{
    nav_can_tx_command_t command={0};
    return nav_can_tx_parse(json,strlen(json),retained,boot,now,&command);
}
int main(void)
{
    nav_can_tx_bus_state_t before={10,2,0}, after={11,2,0};
    assert(nav_can_tx_retry_arbitration(&before,&after,4999,15));
    assert(!nav_can_tx_retry_arbitration(&before,&after,5000,15));
    assert(!nav_can_tx_retry_arbitration(&before,&after,100,16));
    assert(!nav_can_tx_retry_arbitration(&before,&before,100,1));
    after.bus_errors=3;
    assert(!nav_can_tx_retry_arbitration(&before,&after,100,1));
    after.bus_errors=2; after.tx_errors=8;
    assert(!nav_can_tx_retry_arbitration(&before,&after,100,1));
    assert(!nav_can_tx_retry_arbitration(NULL,&after,100,1));
    const char *valid="{\"command_id\":\"abcdefab-1234-1234-1234-123456789abc\","
        "\"boot_id\":\"12345678-1234-1234-1234-123456789abc\",\"enabled\":true,"
        "\"issued_at_ms\":10000,\"expires_at_ms\":14000}";
    assert(parse(valid,false,10000));
    assert(!parse(valid,true,10000));
    assert(!parse(valid,false,14000));
    assert(!parse(valid,false,8999));
    assert(!parse(valid,false,0));
    nav_can_tx_command_t command={0};
    assert(!nav_can_tx_parse(valid,strlen(valid),false,"different-boot",10000,&command));
    char changed[384];
    snprintf(changed,sizeof(changed),"%s{}",valid);
    assert(!parse(changed,false,10000));
    snprintf(changed,sizeof(changed),"%s",valid);
    char *value=strstr(changed,"true"); memcpy(value,"null",4);
    assert(!parse(changed,false,10000));
    snprintf(changed,sizeof(changed),"%s",valid);
    value=strstr(changed,"14000"); memcpy(value,"19000",5);
    assert(!parse(changed,false,10000));
    snprintf(changed,sizeof(changed),"%s",valid);
    value=strstr(changed,"14000"); memcpy(value,"10000",5);
    assert(!parse(changed,false,10000));
    snprintf(changed,sizeof(changed),"%.*s,\"enabled\":false}",(int)strlen(valid)-1,valid);
    assert(!parse(changed,false,10000));
    snprintf(changed,sizeof(changed),"%s",valid); changed[25]='\0';
    assert(!nav_can_tx_parse(changed,strlen(valid),false,boot,10000,&command));
    assert(nav_can_tx_frames[0].id==0x014 && nav_can_tx_frames[0].dlc==3 && nav_can_tx_frames[0].period_ms==100);
    assert(memcmp(nav_can_tx_frames[0].data,"\x00\x60\x00",3)==0);
    assert(nav_can_tx_frames[1].id==0x548 && nav_can_tx_frames[1].dlc==8 && nav_can_tx_frames[1].period_ms==10);
    assert(memcmp(nav_can_tx_frames[1].data,"\0\0\0\0\0\0\0\x08",8)==0);
    puts("CAN TX payload and freshness rules passed");
    return 0;
}
