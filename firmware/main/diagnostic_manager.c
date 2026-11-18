#include "diagnostic_manager.h"
#include "diagnostic_isotp.h"
#include "diagnostic_policy.h"
#include "can_manager.h"
#include "mqtt_manager.h"
#include "app_config.h"
#include "cJSON.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>

typedef struct {
    char id[37], lease[37];
    uint32_t tx_id, rx_id, timeout;
    uint64_t expires;
    size_t length;
    bool close;
    bool expect_response;
    unsigned repeat;
    uint8_t data[NAV_ISOTP_MAX];
} request_t;
static QueueHandle_t requests, incoming_frames;
static volatile uint32_t response_id, frame_overflows;
static uint64_t last_issued;
static char fragment[9000];
static size_t expected, received;
static bool fragment_retained;

static const char *string(cJSON *root, const char *key)
{
    cJSON *v = cJSON_GetObjectItemCaseSensitive(root, key);
    return cJSON_IsString(v) ? v->valuestring : "";
}
static double number(cJSON *root, const char *key)
{
    cJSON *v = cJSON_GetObjectItemCaseSensitive(root, key);
    return cJSON_IsNumber(v) ? v->valuedouble : 0;
}
static bool uuid(const char *value)
{
    if (strlen(value) != 36) { return false; }
    for (unsigned i=0; i<36; ++i) {
        if (i==8 || i==13 || i==18 || i==23) { if(value[i]!='-') return false; }
        else if (!((value[i]>='0' && value[i]<='9') || (value[i]>='a' && value[i]<='f'))) return false;
    }
    return true;
}
static int nibble(char c)
{
    if (c>='0' && c<='9') return c-'0';
    if (c>='A' && c<='F') return c-'A'+10;
    if (c>='a' && c<='f') return c-'a'+10;
    return -1;
}
static void accept_request(void)
{
    if (fragment_retained || strlen(fragment)!=expected) { return; }
    cJSON *root = cJSON_Parse(fragment);
    if (!root) return;
    uint64_t now = 0;
    const double issued_value = number(root, "issued_ms");
    const double expires_value = number(root, "expires_ms");
    if (!app_epoch_ms(&now) || issued_value < 1 || expires_value < 1 ||
        issued_value > (double)(now+1000) || expires_value > (double)(now+6000) ||
        expires_value <= (double)now || issued_value <= (double)last_issued ||
        expires_value-issued_value > 5000 ||
        strcmp(string(root,"boot_id"), mqtt_manager_boot_id()) ||
        !uuid(string(root,"id")) || !uuid(string(root,"lease"))) { cJSON_Delete(root); return; }
    request_t *r = calloc(1,sizeof(*r));
    if (!r) { cJSON_Delete(root); return; }
    strcpy(r->id,string(root,"id")); strcpy(r->lease,string(root,"lease"));
    r->expires = (uint64_t)expires_value;
    r->close = !strcmp(string(root,"op"),"close");
    cJSON *expect = cJSON_GetObjectItemCaseSensitive(root,"expect_response");
    r->expect_response = !cJSON_IsFalse(expect);
    r->repeat = cJSON_HasObjectItem(root,"repeat") ? (unsigned)number(root,"repeat") : 1;
    r->tx_id = (uint32_t)number(root,"tx_id");
    r->rx_id = cJSON_HasObjectItem(root,"rx_id") ? (uint32_t)number(root,"rx_id") : r->tx_id+0x10;
    r->timeout = (uint32_t)number(root,"timeout_ms");
    const char *hex = string(root,"data");
    r->length = strlen(hex)/2;
    bool valid = r->close || (!strcmp(string(root,"op"),"request") &&
        nav_diag_pair_allowed(r->tx_id,r->rx_id) && r->timeout>=100 && r->timeout<=60000 &&
        strlen(hex)%2==0 && r->length>0 && r->length<=NAV_ISOTP_MAX);
    for (size_t i=0; valid && !r->close && i<r->length; ++i) {
        int a=nibble(hex[i*2]), b=nibble(hex[i*2+1]);
        if(a<0 || b<0) valid=false; else r->data[i]=(uint8_t)((a<<4)|b);
    }
    /* Repetition is exclusively a bounded TesterPresent burst, never a write retry. */
    if (!r->close && (!r->repeat || r->repeat>20 ||
        (r->repeat>1 && (r->expect_response || r->length!=2 || r->data[0]!=0x3E || r->data[1]!=0x80)) ||
        (!r->expect_response && (r->length!=2 ||
         !((r->data[0]==0x3E && r->data[1]==0x80) ||
           (r->data[0]==0x28 && (r->data[1]==0x80 || r->data[1]==0x81)) ||
           (r->data[0]==0x11 && r->data[1]==0x01)))))) valid=false;
    if (valid && xQueueSend(requests,&r,0)==pdTRUE) { last_issued=(uint64_t)issued_value; }
    else { free(r); }
    cJSON_Delete(root);
}

void diagnostic_manager_fragment(const esp_mqtt_event_t *event, bool matches)
{
    if (!requests || event->current_data_offset<0 || event->data_len<0) return;
    if (event->current_data_offset==0) {
        expected=received=0;
        if(!matches || event->total_data_len<=0 || event->total_data_len>=(int)sizeof(fragment)) return;
        expected=event->total_data_len; fragment_retained=event->retain;
    }
    if (!expected || (size_t)event->current_data_offset!=received ||
        (size_t)event->total_data_len!=expected || (size_t)event->data_len>expected-received ||
        (event->data_len && !event->data)) { expected=0; return; }
    memcpy(fragment+received,event->data,event->data_len); received+=event->data_len;
    if(received==expected) { fragment[received]=0; accept_request(); memset(fragment,0,received); expected=0; }
}

void diagnostic_manager_frame(const twai_message_t *frame)
{
    if (incoming_frames && response_id && frame->identifier==response_id && !frame->extd && !frame->rtr) {
        if(xQueueSend(incoming_frames,frame,0)!=pdTRUE) ++frame_overflows;
    }
}
static bool send_frame(void *user,const uint8_t data[8])
{
    return can_manager_send(((request_t *)user)->tx_id,data);
}
static void respond(request_t *r,const char *error,nav_isotp_t *s,uint64_t started,unsigned pending)
{
    /* Let the bounded shared outbox drain before a maximum-size ISO-TP response.
       CAN publish losses remain counted; ADC and GPIO acknowledgements continue. */
    mqtt_manager_reserve_diagnostic_reply(true);
    char *json=calloc(1,9000);
    if(!json) { mqtt_manager_reserve_diagnostic_reply(false); return; }
    int used=snprintf(json,9000,"{\"id\":\"%s\",\"boot_id\":\"%s\",\"status\":\"%s\",\"error\":\"%s\","
        "\"elapsed_ms\":%" PRIu64 ",\"pending_count\":%u,\"response_hex\":\"",r->id,mqtt_manager_boot_id(),
        error ? "failed" : "completed",error ? error : "",app_uptime_ms()-started,pending);
    if(!error && s) for(size_t i=0;i<s->rx_len;++i) { used+=snprintf(json+used,9000-used,"%02X",s->rx[i]); }
    snprintf(json+used,9000-used,"\"}");
    /* Retries only publish the same response; a CAN request is never repeated. */
    for(unsigned i=0;i<20 && mqtt_manager_is_connected();++i) {
        if(mqtt_manager_diagnostic_publish(json)) break;
        vTaskDelay(pdMS_TO_TICKS(50));
    }
    memset(json,0,9000); free(json);
    mqtt_manager_reserve_diagnostic_reply(false);
}
static void worker(void *unused)
{
    (void)unused;
    char lease[37]={0};
    uint64_t idle=0;
    nav_isotp_t *s=calloc(1,sizeof(*s));
    for(;;) {
        request_t *r=NULL;
        if(xQueueReceive(requests,&r,pdMS_TO_TICKS(100))!=pdTRUE) {
            if(lease[0] && (!mqtt_manager_is_connected() || app_uptime_ms()-idle>15000)) {
                (void)can_manager_diagnostic_mode(false); lease[0]=0;
            }
            continue;
        }
        uint64_t now=0, started=app_uptime_ms();
        const char *error=NULL;
        unsigned pending=0;
        if(!s) error="Insufficient memory";
        else if(!mqtt_manager_is_connected() || !app_epoch_ms(&now) || now>=r->expires) error="Request expired";
        else if(lease[0] && strcmp(lease,r->lease)) error="Diagnostic connection is busy";
        else if(r->close) {
            if(can_manager_diagnostic_mode(false)!=ESP_OK) error="Listen-only restoration failed";
            lease[0]=0;
        }
        else if(can_manager_diagnostic_mode(true)!=ESP_OK) error="CAN controller unavailable";
        else {
            strcpy(lease,r->lease);
            response_id=0; xQueueReset(incoming_frames); frame_overflows=0;
            if (!r->expect_response) {
                for (unsigned index=0; index<r->repeat; ++index) {
                    uint64_t tick=app_uptime_ms();
                    if (!mqtt_manager_is_connected()) { error="MQTT disconnected"; break; }
                    nav_isotp_start(s,r->data,r->length,esp_timer_get_time(),r->timeout,send_frame,r);
                    if (s->error) { error=s->error; break; }
                    if (r->repeat>1 && app_uptime_ms()-tick<100)
                        vTaskDelay(pdMS_TO_TICKS(100-(app_uptime_ms()-tick)));
                }
                s->rx_len=0;
            } else {
            response_id=r->rx_id;
            nav_isotp_start(s,r->data,r->length,esp_timer_get_time(),r->timeout,send_frame,r);
            while(!s->done && !s->error) {
                twai_message_t frame;
                if(!mqtt_manager_is_connected()) { s->error="MQTT disconnected"; break; }
                if(frame_overflows) { s->error="Diagnostic receive queue overflow"; break; }
                if(xQueueReceive(incoming_frames,&frame,1)==pdTRUE)
                    nav_isotp_frame(s,frame.data,frame.data_length_code,esp_timer_get_time());
                if(s->done && s->rx_len==3 && s->rx[0]==0x7F && s->rx[1]==r->data[0] && s->rx[2]==0x78) {
                    ++pending; nav_isotp_wait_response(s,esp_timer_get_time());
                }
                nav_isotp_poll(s,esp_timer_get_time());
            }
            response_id=0; error=s->error;
            }
        }
        if(error) { (void)can_manager_diagnostic_mode(false); lease[0]=0; }
        respond(r,error,r->close ? NULL : s,started,pending);
        idle=app_uptime_ms();
        memset(r,0,sizeof(*r)); free(r);
        if(s) memset(s,0,sizeof(*s));
    }
}
esp_err_t diagnostic_manager_init(void)
{
    requests=xQueueCreate(1,sizeof(request_t *));
    incoming_frames=xQueueCreate(64,sizeof(twai_message_t));
    if(!requests || !incoming_frames) return ESP_ERR_NO_MEM;
    return xTaskCreate(worker,"diagnostics",4096,NULL,5,NULL)==pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}
