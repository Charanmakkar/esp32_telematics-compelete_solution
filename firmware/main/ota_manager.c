#include "ota_manager.h"
#include "app_config.h"
#include "mqtt_manager.h"
#include "command_handler.h"
#include "can_manager.h"
#include "wifi_manager.h"
#include "sw_version.h"
#include "esp_app_desc.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "cJSON.h"
#include "psa/crypto.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include <math.h>
#include <stdio.h>
#include <string.h>

#define OTA_CHUNK_BYTES 2048
#define PACKET_SIZE 4400
static QueueHandle_t packets;
static char fragment[PACKET_SIZE];
static size_t received, expected;
static bool healthy;
static char running_hash[65];
static esp_ota_handle_t handle;
static const esp_partition_t *target;
static psa_hash_operation_t hash = PSA_HASH_OPERATION_INIT;
static size_t written, total;
static char session[37], expected_hash[65];
static uint64_t last_packet;
static bool active;

static void hex(const uint8_t *data, size_t size, char *out)
{
    for (size_t i=0; i<size; ++i) sprintf(out+i*2, "%02x", data[i]);
    out[size*2]=0;
}
static int nibble(char c) { return c>='0' && c<='9' ? c-'0' : c>='a' && c<='f' ? c-'a'+10 : -1; }
static const char *str(cJSON *root, const char *key)
{
    cJSON *value=cJSON_GetObjectItemCaseSensitive(root,key);
    return cJSON_IsString(value) ? value->valuestring : "";
}
static bool number(cJSON *root, const char *key, uint64_t *out)
{
    cJSON *v=cJSON_GetObjectItemCaseSensitive(root,key);
    if (!cJSON_IsNumber(v) || !isfinite(v->valuedouble) || v->valuedouble<0 ||
        v->valuedouble>9007199254740991.0 || floor(v->valuedouble)!=v->valuedouble) return false;
    *out=(uint64_t)v->valuedouble; return true;
}
static void release(void)
{
    if (handle) { esp_ota_abort(handle); handle=0; }
    psa_hash_abort(&hash);
    active=false;
    mqtt_manager_reserve_ota_reply(false);
    wifi_manager_ota_mode(false);
    (void)can_manager_ota_lock(false);
    command_handler_maintenance(false);
}
static void reply(const char *id, const char *op, unsigned offset, const char *error)
{
    cJSON *root=cJSON_CreateObject();
    if (!root) return;
    cJSON_AddNumberToObject(root,"protocol",1);
    cJSON_AddStringToObject(root,"source","hardware");
    cJSON_AddStringToObject(root,"boot_id",mqtt_manager_boot_id());
    cJSON_AddStringToObject(root,"id",id);
    cJSON_AddStringToObject(root,"op",op);
    cJSON_AddNumberToObject(root,"offset",offset);
    cJSON_AddBoolToObject(root,"ok",error==NULL);
    if (error) cJSON_AddStringToObject(root,"error",error);
    char *json=cJSON_PrintUnformatted(root);
    if (json) { mqtt_manager_ota_publish("response",json); cJSON_free(json); }
    cJSON_Delete(root);
}
static bool confirmed(void)
{
    esp_ota_img_states_t state;
    esp_err_t result=esp_ota_get_state_partition(esp_ota_get_running_partition(),&state);
    return result==ESP_ERR_NOT_FOUND || (result==ESP_OK &&
        (state==ESP_OTA_IMG_VALID || state==ESP_OTA_IMG_UNDEFINED));
}
static void status(void)
{
    /* Embedded marker lets the upload validator reject images that remove OTA. */
    static const char marker[]="NAVSPHERE_OTA_PROTOCOL_1";
    const esp_partition_t *slot=esp_ota_get_next_update_partition(NULL);
    cJSON *root=cJSON_CreateObject();
    if (!root) return;
    cJSON_AddNumberToObject(root,"protocol",1);
    cJSON_AddStringToObject(root,"capability",marker);
    cJSON_AddStringToObject(root,"source","hardware");
    cJSON_AddStringToObject(root,"boot_id",mqtt_manager_boot_id());
    cJSON_AddStringToObject(root,"version",esp_app_get_description()->version);
    cJSON_AddStringToObject(root,"build",SW_BUILD_ID);
    cJSON_AddStringToObject(root,"image_sha256",running_hash);
    cJSON_AddStringToObject(root,"partition",esp_ota_get_running_partition()->label);
    cJSON_AddNumberToObject(root,"uptime_ms",(double)app_uptime_ms());
    cJSON_AddBoolToObject(root,"mqtt_tls",mqtt_manager_transport_tls());
    char ip[16]; int rssi=0;
    if (wifi_manager_info(ip,&rssi)) {
        cJSON_AddStringToObject(root,"ip_address",ip);
        cJSON_AddNumberToObject(root,"wifi_rssi_dbm",rssi);
    }
    cJSON_AddNumberToObject(root,"slot_size",slot ? slot->size : 0);
    cJSON_AddNumberToObject(root,"max_chunk_bytes",OTA_CHUNK_BYTES);
    cJSON_AddBoolToObject(root,"confirmed",healthy && confirmed());
    cJSON_AddStringToObject(root,"state",active ? "transferring" : "idle");
    char *json=cJSON_PrintUnformatted(root);
    if (json) { mqtt_manager_ota_publish("status",json); cJSON_free(json); }
    cJSON_Delete(root);
}

static void process(char *json)
{
    /* Flat primitives only: bound parser depth and reject duplicate properties. */
    bool quoted=false, escape=false;
    unsigned depth=0;
    for (char *p=json; *p; ++p) {
        if (quoted) { if (escape) escape=false; else if (*p=='\\') escape=true; else if (*p=='"') quoted=false; }
        else if (*p=='"') quoted=true;
        else if (*p=='[' || (*p=='{' && ++depth>1)) return;
        else if (*p=='}' && (!depth || --depth)) return;
    }
    if (quoted || depth) return;
    cJSON *root=cJSON_ParseWithOpts(json,NULL,true);
    if (!cJSON_IsObject(root)) { cJSON_Delete(root); return; }
    cJSON *a, *b;
    cJSON_ArrayForEach(a,root) { for (b=a->next; b; b=b->next) if (!strcmp(a->string,b->string)) { cJSON_Delete(root); return; } }
    const char *id=str(root,"id"), *op=str(root,"op");
    if (!command_id_valid(id) || strcmp(str(root,"boot_id"),mqtt_manager_boot_id()) ||
        (strcmp(op,"start") && strcmp(op,"chunk") && strcmp(op,"finish"))) { cJSON_Delete(root); return; }
    uint64_t offset=0;
    const char *error=NULL;
    bool restart=false;
    if (!strcmp(op,"start")) {
        uint64_t size=0, expiry=0, now=0;
        const char *sha=str(root,"sha256");
        bool valid_sha=strlen(sha)==64;
        for (unsigned i=0; valid_sha && i<64; ++i) valid_sha=nibble(sha[i])>=0;
        target=esp_ota_get_next_update_partition(NULL);
        if (active) {
            if (strcmp(session,id)) error="Another update is active";
        } else if (!healthy || !confirmed() || !target || !number(root,"size",&size) || size<288 || size>target->size ||
            !valid_sha || !number(root,"expires_at_ms",&expiry) || !app_epoch_ms(&now) || expiry<=now || expiry-now>30000) {
            error="Invalid image size, clock, deadline or OTA readiness";
        } else {
            command_handler_maintenance(true);
            /* Publisher owns GPIO state; wait for its acknowledgement before writing flash. */
            for (unsigned i=0; i<20 && !command_handler_maintenance_ready(); ++i) vTaskDelay(pdMS_TO_TICKS(10));
            if (!command_handler_maintenance_ready() || can_manager_ota_lock(true)!=ESP_OK) {
                error="Turn GPIO controls and CAN transmission OFF, and close diagnostics before OTA";
            } else {
                /* Large CAN batches can exhaust socket/outbox headroom during flash writes. */
                mqtt_manager_reserve_ota_reply(true);
                wifi_manager_ota_mode(true);
                strcpy(session,id); strcpy(expected_hash,sha); total=(size_t)size; written=0;
                if (psa_hash_setup(&hash,PSA_ALG_SHA_256)!=PSA_SUCCESS ||
                    esp_ota_begin(target,OTA_WITH_SEQUENTIAL_WRITES,&handle)!=ESP_OK) error="Could not open inactive OTA slot";
                else { active=true; last_packet=app_uptime_ms(); }
            }
            if (error) release();
        }
    } else if (!active || strcmp(session,id)) error="No matching active update";
    else if (!strcmp(op,"chunk")) {
        const char *data=str(root,"data"); size_t length=strlen(data)/2;
        uint8_t bytes[OTA_CHUNK_BYTES];
        if (!number(root,"offset",&offset) || offset>total || strlen(data)%2 || !length || length>sizeof(bytes) || length>total-offset) error="Invalid chunk";
        for (size_t i=0; !error && i<length; ++i) {
            int hi=nibble(data[i*2]), lo=nibble(data[i*2+1]);
            if (hi<0 || lo<0) error="Invalid chunk encoding";
            else bytes[i]=(uint8_t)((hi<<4)|lo);
        }
        if (!error && offset==written) {
            if (!written && (bytes[0]!=0xE9 || length<288 || bytes[12] || bytes[13] ||
                memcmp(bytes+32,"\x32\x54\xcd\xab",4) || memcmp(bytes+80,"firmware\0",9))) error="Wrong ESP32 application";
            else if (esp_ota_write(handle,bytes,length)!=ESP_OK || psa_hash_update(&hash,bytes,length)!=PSA_SUCCESS) error="Flash write failed";
            else written+=length;
        } else if (!error && offset+length<=written) {
            uint8_t previous[OTA_CHUNK_BYTES];
            if (esp_partition_read(target,(size_t)offset,previous,length)!=ESP_OK || memcmp(previous,bytes,length)) error="Conflicting duplicate chunk";
        } else if (!error) error="Out-of-order chunk";
        if (!error) last_packet=app_uptime_ms();
        else release();
    } else {
        uint8_t digest[32]; char actual[65]; size_t size=0;
        if (written!=total || psa_hash_finish(&hash,digest,sizeof(digest),&size)!=PSA_SUCCESS) error="Incomplete image";
        else {
            hex(digest,32,actual);
            if (strcmp(actual,expected_hash)) error="Image SHA-256 mismatch";
            else {
                esp_err_t result=esp_ota_end(handle); handle=0;
                if (result!=ESP_OK) error="ESP32 rejected the firmware image";
                else if (esp_ota_set_boot_partition(target)!=ESP_OK) error="Could not select new boot image";
                else restart=true;
            }
        }
        if (error) release();
    }
    reply(id,op,(unsigned)offset,error);
    cJSON_Delete(root);
    if (restart) { vTaskDelay(pdMS_TO_TICKS(1000)); esp_restart(); }
}

static void worker(void *unused)
{
    (void)unused;
    char packet[PACKET_SIZE];
    uint64_t last_status=0, connected_since=0;
    uint8_t digest[32];
    if (esp_partition_get_sha256(esp_ota_get_running_partition(),digest)==ESP_OK) hex(digest,32,running_hash);
    esp_ota_img_states_t state;
    bool pending=esp_ota_get_state_partition(esp_ota_get_running_partition(),&state)==ESP_OK && state==ESP_OTA_IMG_PENDING_VERIFY;
    uint64_t boot_started=app_uptime_ms();
    for (;;) {
        if (xQueueReceive(packets,packet,pdMS_TO_TICKS(100))==pdTRUE) process(packet);
        uint64_t now=app_uptime_ms();
        if (active && (!mqtt_manager_is_connected() || now-last_packet>30000)) release();
        if (mqtt_manager_is_connected()) {
            if (!connected_since) connected_since=now;
            if (pending && healthy && now-connected_since>=10000 && esp_ota_mark_app_valid_cancel_rollback()==ESP_OK) pending=false;
            if (now-last_status>=2000) { status(); last_status=now; }
        } else connected_since=0;
        if (pending && now-boot_started>120000) {
            esp_ota_mark_app_invalid_rollback_and_reboot();
            esp_restart();
        }
    }
}

void ota_manager_fragment(const esp_mqtt_event_t *event, bool matches)
{
    if (!packets) return;
    if (event->current_data_offset==0) {
        expected=received=0;
        if (!matches || event->retain || event->total_data_len<=0 || event->total_data_len>=PACKET_SIZE) return;
        expected=(size_t)event->total_data_len;
    }
    if (!expected || event->current_data_offset<0 || (size_t)event->current_data_offset!=received ||
        (size_t)event->total_data_len!=expected || event->data_len<0 || (size_t)event->data_len>expected-received) { expected=0; return; }
    memcpy(fragment+received,event->data,(size_t)event->data_len); received+=(size_t)event->data_len;
    if (received==expected) {
        fragment[received]=0;
        if (strlen(fragment)==received) (void)xQueueSend(packets,fragment,0);
        expected=0;
    }
}
esp_err_t ota_manager_start(bool startup_healthy)
{
    if (psa_crypto_init()!=PSA_SUCCESS) return ESP_FAIL;
    healthy=startup_healthy;
    packets=xQueueCreate(2,PACKET_SIZE);
    if (!packets) return ESP_ERR_NO_MEM;
    return xTaskCreate(worker,"nav_ota",16384,NULL,2,NULL)==pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}
