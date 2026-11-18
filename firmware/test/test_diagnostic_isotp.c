#include "diagnostic_isotp.h"
#include "diagnostic_policy.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint8_t output[1024][8];
static unsigned count;
static bool send(void *user,const uint8_t frame[8])
{
    (void)user; assert(count<1024); memcpy(output[count++],frame,8); return true;
}
static nav_isotp_t s;
static void start(const uint8_t *data,size_t n) {count=0;assert(nav_isotp_start(&s,data,n,0,5000,send,NULL));}
int main(void)
{
    const uint8_t read[]={0x22,0xF1,0x86};
    start(read,sizeof(read)); assert(count==1 && output[0][0]==3);
    for(unsigned i=4;i<8;++i)assert(output[0][i]==0x55);
    uint8_t sf[]={4,0x62,0xF1,0x86,1,0,0,0};
    nav_isotp_frame(&s,sf,8,100); assert(s.done && s.rx_len==4 && s.rx[3]==1);
    start(read,sizeof(read)); sf[0]=7; nav_isotp_frame(&s,sf,4,100);assert(s.error);sf[0]=4;
    start(read,sizeof(read)); nav_isotp_poll(&s,5000000);assert(s.error);
    /* Receive maximum classic ISO-TP payload, including sequence rollover and FC blocks. */
    start(read,sizeof(read));
    uint8_t ff[]={0x1F,0xFF,0,1,2,3,4,5};
    nav_isotp_frame(&s,ff,8,100);assert(count==2 && output[1][0]==0x30);
    size_t position=6;unsigned seq=1;
    while(position<4095) {
        uint8_t cf[8]={0};cf[0]=0x20|(seq++&15);
        size_t n=4095-position;if(n>7)n=7;
        for(size_t i=0;i<n;++i)cf[i+1]=(uint8_t)(position+i);
        nav_isotp_frame(&s,cf,n+1,200+position);position+=n;
    }
    assert(s.done && !s.error && s.rx_len==4095);
    for(size_t i=0;i<4095;++i)assert(s.rx[i]==(uint8_t)i);
    start(read,sizeof(read));nav_isotp_frame(&s,ff,8,100);
    uint8_t bad[]={0x22,1,2,3,4,5,6,7};nav_isotp_frame(&s,bad,8,200);assert(s.error);
    start(read,sizeof(read));nav_isotp_frame(&s,ff,8,100);bad[0]=0x21;nav_isotp_frame(&s,bad,3,200);assert(s.error);
    /* Transmit with STmin, block sizes and sequence rollover. */
    uint8_t payload[200];for(unsigned i=0;i<sizeof(payload);++i)payload[i]=(uint8_t)i;
    start(payload,sizeof(payload));assert(output[0][0]==0x10 && output[0][1]==200);
    uint8_t fc[]={0x30,2,5,0,0,0,0,0};nav_isotp_frame(&s,fc,8,100);
    nav_isotp_poll(&s,5099);assert(count==1);nav_isotp_poll(&s,5100);assert(count==2 && output[1][0]==0x21);
    nav_isotp_poll(&s,10100);assert(s.waiting_fc);
    fc[1]=0;fc[2]=0;nav_isotp_frame(&s,fc,8,10200);
    while(s.tx_pos<s.tx_len)nav_isotp_poll(&s,11000);
    assert(!s.error && output[16][0]==0x20 && s.tx_pos==200);
    start(payload,sizeof(payload));fc[0]=0x32;nav_isotp_frame(&s,fc,8,100);assert(s.error);
    start(payload,sizeof(payload));nav_isotp_frame(&s,sf,8,100);assert(s.error);
    start(payload,sizeof(payload));fc[0]=0x31;
    for(unsigned i=0;i<4;++i) { nav_isotp_frame(&s,fc,8,100+i); }
    assert(s.error);
    start(payload,sizeof(payload));fc[0]=0x30;fc[2]=0x80;nav_isotp_frame(&s,fc,8,100);assert(s.error);
    start(read,sizeof(read));uint8_t pending[]={3,0x7F,0x22,0x78,0,0,0,0};
    nav_isotp_frame(&s,pending,8,4000000);assert(s.done);nav_isotp_wait_response(&s,4000000);
    nav_isotp_poll(&s,5000000);assert(s.error);
    assert(!nav_isotp_start(&s,read,0,0,5000,send,NULL));
    assert(nav_diag_tx_allowed(0x7E4) && nav_diag_pair_allowed(0x7E4,0x7EC));
    assert(nav_diag_pair_allowed(0x640,0x650) && nav_diag_pair_allowed(0x7DF,0x7EC));
    assert(!nav_diag_pair_allowed(0x7E4,0x7F4) && !nav_diag_pair_allowed(0x640,0x7EC));
    assert(!nav_diag_tx_allowed(0x100) && !nav_diag_tx_allowed(0x7EC));
    puts("ISO-TP: single/multi-frame, 4095-byte receive, sequence rollover, STmin, block control, malformed frames, timeout and NRC-pending bounds passed.");
    return 0;
}
