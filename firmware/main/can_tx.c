#include "can_tx.h"
#include "can_tx_rules.h"
#include "can_manager.h"
#include "app_config.h"
#include "mqtt_manager.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

typedef struct { nav_can_tx_command_t command; uint32_t generation; } queued_command_t;
static QueueHandle_t commands;
static portMUX_TYPE lock=portMUX_INITIALIZER_UNLOCKED;
static uint32_t generation;
static bool enabled;
static uint32_t sent[2], failures, skipped;
static char command_id[37];
static const char *reason="off";

void can_tx_disconnect(void)
{
    portENTER_CRITICAL(&lock); ++generation; portEXIT_CRITICAL(&lock);
}

void can_tx_receive(const char *json, size_t length, bool retained)
{
    uint64_t now=0;
    queued_command_t item={0};
    if (!commands || !app_epoch_ms(&now) ||
        !nav_can_tx_parse(json,length,retained,mqtt_manager_boot_id(),now,&item.command)) return;
    portENTER_CRITICAL(&lock); item.generation=generation; portEXIT_CRITICAL(&lock);
    (void)xQueueSend(commands,&item,0);
}

void can_tx_stats(char *json, size_t capacity)
{
    portENTER_CRITICAL(&lock);
    snprintf(json,capacity,"\"periodic_tx\":{\"enabled\":%s,\"command_id\":\"%s\","
        "\"reason\":\"%s\",\"sent_014\":%" PRIu32 ",\"sent_548\":%" PRIu32
        ",\"failures\":%" PRIu32 ",\"skipped\":%" PRIu32 "}",
        enabled?"true":"false",command_id,reason,sent[0],sent[1],failures,skipped);
    portEXIT_CRITICAL(&lock);
}

static void stop(const char *why)
{
    (void)can_manager_periodic_mode(false);
    portENTER_CRITICAL(&lock); enabled=false; reason=why; portEXIT_CRITICAL(&lock);
}

static void transmit_task(void *argument)
{
    (void)argument;
    bool active=false;
    uint32_t connection=0, consecutive_failures=0;
    uint64_t last_issued=0, due[2]={0};
    for (;;) {
        uint32_t current;
        portENTER_CRITICAL(&lock); current=generation; portEXIT_CRITICAL(&lock);
        if (active && (current!=connection || !mqtt_manager_is_connected())) {
            stop("connection_lost"); active=false;
        }
        queued_command_t item;
        while (xQueueReceive(commands,&item,0)==pdTRUE) {
            uint64_t epoch=0;
            if (item.generation!=current || !mqtt_manager_is_connected() || !app_epoch_ms(&epoch) ||
                epoch>=item.command.expires_at_ms || item.command.issued_at_ms<=last_issued) continue;
            last_issued=item.command.issued_at_ms;
            const esp_err_t result=can_manager_periodic_mode(item.command.enabled);
            active=item.command.enabled && result==ESP_OK;
            connection=current; consecutive_failures=0;
            due[0]=due[1]=app_uptime_ms();
            portENTER_CRITICAL(&lock);
            memcpy(command_id,item.command.command_id,37);
            enabled=active;
            reason=result==ESP_OK ? active?"on":"off" : "controller_busy_or_unavailable";
            portEXIT_CRITICAL(&lock);
        }
        if (active) {
            for (unsigned i=0; i<2; ++i) {
                uint64_t now=app_uptime_ms();
                if (now<due[i]) continue;
                uint64_t missed=(now-due[i])/nav_can_tx_frames[i].period_ms;
                due[i]+=(missed+1)*nav_can_tx_frames[i].period_ms;
                bool ok=can_manager_send_periodic(i);
                portENTER_CRITICAL(&lock);
                skipped+=(uint32_t)missed;
                if (ok) ++sent[i]; else ++failures;
                portEXIT_CRITICAL(&lock);
                consecutive_failures=ok?0:consecutive_failures+1;
                if (consecutive_failures>=3) { stop("transmit_failed"); active=false; break; }
            }
        }
        vTaskDelay(pdMS_TO_TICKS(active?1:10));
    }
}

esp_err_t can_tx_start(void)
{
    commands=xQueueCreate(8,sizeof(queued_command_t));
    if (!commands) return ESP_ERR_NO_MEM;
    return xTaskCreate(transmit_task,"can_tx",4096,NULL,5,NULL)==pdPASS ? ESP_OK : ESP_ERR_NO_MEM;
}
