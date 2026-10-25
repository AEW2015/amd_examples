/* SCU35 encrypted UDP laboratory endpoint. Public diagnostic AES key only.
 * AMD IP/driver path: MicroBlaze V -> PMC Bridge -> PMC DMA / AES-GCM.
 * No flash, eFUSE, persistent keys, OS, TCP stack, or custom PL RTL.
 */
#include <string.h>
#include "xparameters.h"
#include "xil_printf.h"
#include "xil_io.h"
#include "xemaclite.h"
#include "xsecure_aes.h"
#include "xsecure_sha.h"
#include "xsecure_error.h"
#include "xpmcdma.h"
#include "xtrngpsx.h"

#define ETH_BASE 0x40e00000U
#define TIMER 0x40000000U
#define MAX_PAYLOAD 1024U
#define SHARED __attribute__((aligned(64),section(".shared")))
static XSecure_Aes aes SHARED;
static XSecure_Sha sha SHARED;
static XPmcDma dma SHARED;
static u8 plain[1024] SHARED, cipher[1024] SHARED;
static u8 key[32] SHARED, iv[16] SHARED, tag[16] SHARED, aad[64] SHARED;
static u8 digest[32] SHARED;
extern u8 __shared_start[],__shared_end[];
static XEmacLite mac;
static u8 rx[1600] __attribute__((aligned(64))),tx[1600] __attribute__((aligned(64)));
static const u8 ownmac[6]={2,0x35,0,0,0,2},ownip[4]={192,168,10,2};
static u8 boot_nonce[8];
static u32 rx_count,tx_count,auth_reject,replay_reject,tx_timeout,crypto_count;
static u32 response_seq,last_crypto_ticks,peer_session,peer_seq;
static unsigned peer_active;

static u16 be16(const u8*p){return ((u16)p[0]<<8)|p[1];}
static u32 be32(const u8*p){return ((u32)p[0]<<24)|((u32)p[1]<<16)|((u32)p[2]<<8)|p[3];}
static void put16(u8*p,u16 n){p[0]=n>>8;p[1]=n;}
static void put32(u8*p,u32 n){p[0]=n>>24;p[1]=n>>16;p[2]=n>>8;p[3]=n;}
static u32 ticks(void){return Xil_In32(TIMER+8);}
static void delay_ms(u32 n){u32 t=ticks();while((u32)(ticks()-t)<n*100000U){}}
static void timer_init(void){
 Xil_Out32(TIMER,0);Xil_Out32(TIMER+0x10,0);
 Xil_Out32(TIMER+4,0);Xil_Out32(TIMER+0x14,0);
 Xil_Out32(TIMER+0x10,0x20);Xil_Out32(TIMER,0x820);
 Xil_Out32(TIMER+0x10,0);Xil_Out32(TIMER,0x890);
}
static u16 checksum(const u8*p,unsigned n){
 u32 sum=0;while(n>1){sum+=be16(p);p+=2;n-=2;}if(n)sum+=(u32)*p<<8;
 while(sum>>16)sum=(sum&65535)+(sum>>16);return (u16)~sum;
}
static int send_frame(unsigned n){
 u32 t=ticks();while(!XEmacLite_TxBufferAvailable(&mac)){
  if((u32)(ticks()-t)>10000000U){++tx_timeout;return 1;}
 }
 if(n<60){memset(tx+n,0,60-n);n=60;}
 int rc=XEmacLite_Send(&mac,tx,n);if(!rc)++tx_count;return rc;
}
static int readphy(unsigned phy,unsigned reg,u16 *v){return XEmacLite_PhyRead(&mac,phy,reg,v);}
static int writephy(unsigned phy,unsigned reg,u16 v){return XEmacLite_PhyWrite(&mac,phy,reg,v);}
static int phy_init(void){
 unsigned p;u16 id=0,id2=0,value=0;
 delay_ms(100);
 for(p=0;p<32;++p)if(!readphy(p,2,&id)&&id==0x2000)break;
 if(p==32)return 1;
 if(readphy(p,3,&id2))return 2;
 xil_printf("E35_PHY,%u,%04x,%04x\r\n",p,id,id2);
 if((id2&0xfff0)!=0xa230)return 3;
 /* TI DP83867 CFG4.PORT_MIRROR_EN: clear the volatile mirror bit, as in
  * the previously tested SCU35 MII fixture. No persistent PHY writes. */
 if(writephy(p,13,0x001f)||writephy(p,14,0x0031)||writephy(p,13,0x401f)||readphy(p,14,&value))return 4;
 if(writephy(p,14,value&~1U))return 5;
 /* Advertise only 100BASE-TX full duplex; no unsupported gigabit MII. */
 if(writephy(p,4,0x0101)||writephy(p,9,0)||writephy(p,0,0x1200))return 6;
 u32 start=ticks();
 do {
  if(readphy(p,1,&value)||readphy(p,1,&value))return 7;
  if(value&4){readphy(p,0x11,&value);xil_printf("E35_LINK,%04x\r\n",value);return 0;}
 }while((u32)(ticks()-start)<1500000000U);
 return 8;
}
static int crypto_init(void){
 for(volatile u8*p=__shared_start;p<__shared_end;++p)*p=0;
 XPmcDma_Config*cfg=XPmcDma_LookupConfig(0U);if(!cfg)return 1;
 int rc=XPmcDma_CfgInitialize(&dma,cfg,cfg->BaseAddress);
 if(!rc)rc=XSecure_AesInitialize(&aes,&dma);
 if(!rc)rc=XSecure_ShaInitialize(&sha,&dma);
 for(unsigned i=0;i<32;++i)key[i]=(u8)i;
 if(!rc)rc=XSecure_AesWriteKey(&aes,XSECURE_AES_USER_KEY_0,XSECURE_AES_KEY_SIZE_256,(UINTPTR)key);
 if(rc)return rc;
 XTrngpsx_Instance rng;u8 seed[32];
 XTrngpsx_Config*rngcfg=XTrngpsx_LookupConfig(0U);
 XTrngpsx_UserConfig user={.Mode=XTRNGPSX_HRNG_MODE,
  .SeedLife=XTRNGPSX_USER_CFG_SEED_LIFE,.DFLength=XTRNGPSX_USER_CFG_DF_LENGTH,
  .AdaptPropTestCutoff=XTRNGPSX_USER_CFG_ADAPT_TEST_CUTOFF,
  .RepCountTestCutoff=XTRNGPSX_USER_CFG_REP_TEST_CUTOFF,.IsBlocking=FALSE};
 if(!rngcfg)return 2;
 rc=XTrngpsx_CfgInitialize(&rng,rngcfg,rngcfg->BaseAddress);
 if(!rc)rc=XTrngpsx_PreOperationalSelfTests(&rng);
 if(!rc)rc=XTrngpsx_Instantiate(&rng,0,0,0,&user);
 if(!rc)rc=XTrngpsx_Generate(&rng,seed,sizeof(seed),FALSE);
 if(!rc){memcpy(boot_nonce,seed,8);rc=XTrngpsx_Uninstantiate(&rng);}
 return rc;
}
static int decrypt_request(const u8*request,unsigned n){
 memcpy(aad,request,16);memcpy(iv,request+16,12);
 memcpy(cipher,request+28,n);memcpy(tag,request+28+n,16);
 int rc=XSecure_AesDecryptInit(&aes,XSECURE_AES_USER_KEY_0,XSECURE_AES_KEY_SIZE_256,(UINTPTR)iv);
 if(!rc)rc=XSecure_AesUpdateAad(&aes,(UINTPTR)aad,16);
 if(!rc)rc=XSecure_AesDecryptData(&aes,(UINTPTR)cipher,(UINTPTR)plain,n,(UINTPTR)tag);
 if(rc)memset(plain,0,sizeof(plain));
 return rc;
}
/* Wire response: 32-byte authenticated header, 12-byte nonce, n bytes data,
 * 16-byte tag. Header fields are network-endian; see host.py.
 * last_crypto_ticks reports the PREVIOUS operation (current encryption has
 * not finished when its authenticated header must be committed).
 */
static unsigned process(const u8*request,unsigned request_len,u8*response){
 if(request_len<16||memcmp(request,"E35Q",4)||request[4]!=1)return 0;
 unsigned op=request[5],n=be16(request+6),status=0;
 u32 seq=be32(request+8),session=be32(request+12),begin=ticks();
 if(op<1||op>6||n>MAX_PAYLOAD||(n&15)||n<16||request_len!=(16+n+(op==2?28:0)))return 0;
 if(op==2){
  int rc=decrypt_request(request,n);
  if(rc==XSECURE_AES_GCM_TAG_MISMATCH){status=2;++auth_reject;}
  else if(rc){status=4;xil_printf("E35_CRYPTO_FAIL,dec,%u\r\n",rc);}
  else if(peer_active&&(session!=peer_session||seq<=peer_seq)){status=3;++replay_reject;}
  else {peer_active=1;peer_session=session;peer_seq=seq;}
 }else memcpy(plain,request+16,n);
 if(!status&&(op==5||op==6)){
  int rc=XSecure_ShaDigest(&sha,op==5?XSECURE_SHA3_256:XSECURE_SHAKE_256,
    (UINTPTR)plain,n,(UINTPTR)digest,32);
  if(rc){status=4;xil_printf("E35_CRYPTO_FAIL,sha,%u\r\n",rc);}
  else {n=32;memcpy(plain,digest,32);}
 }
 if(status)n=0;
 memcpy(response,"E35R",4);response[4]=1;response[5]=op;put16(response+6,n);
 put32(response+8,seq);put32(response+12,session);put32(response+16,status);
 put32(response+20,last_crypto_ticks);put32(response+24,rx_count);put32(response+28,tx_count);
 memset(response+32,0,12+n+16);
 if(!status&&op!=3&&op!=4){
  if(response_seq==0xffffffffU)return 0; /* Never wrap a GCM nonce. */
  memcpy(iv,boot_nonce,8);put32(iv+8,++response_seq);memcpy(response+32,iv,12);
  memcpy(aad,response,32);
  int rc=XSecure_AesEncryptInit(&aes,XSECURE_AES_USER_KEY_0,XSECURE_AES_KEY_SIZE_256,(UINTPTR)iv);
  if(!rc)rc=XSecure_AesUpdateAad(&aes,(UINTPTR)aad,32);
  if(!rc)rc=XSecure_AesEncryptData(&aes,(UINTPTR)plain,(UINTPTR)cipher,n,(UINTPTR)tag);
  if(rc){xil_printf("E35_CRYPTO_FAIL,enc,%u\r\n",rc);return 0;}
  memcpy(response+44,cipher,n);memcpy(response+44+n,tag,16);++crypto_count;
 }else if(!status)memcpy(response+44,plain,n);
 if(op!=4)last_crypto_ticks=ticks()-begin;
 return 60+n;
}
static void packet(unsigned length){
 if(length<42)return;
 u16 type=be16(rx+12);
 if(type==0x0806){
  if(be16(rx+14)!=1||be16(rx+16)!=0x0800||rx[18]!=6||rx[19]!=4||be16(rx+20)!=1||memcmp(rx+38,ownip,4))return;
  memcpy(tx,rx+6,6);memcpy(tx+6,ownmac,6);put16(tx+12,0x0806);
  memcpy(tx+14,rx+14,28);put16(tx+20,2);memcpy(tx+32,rx+22,10);
  memcpy(tx+22,ownmac,6);memcpy(tx+28,ownip,4);send_frame(42);return;
 }
 if(type!=0x0800||rx[14]!=0x45||memcmp(rx+30,ownip,4)||checksum(rx+14,20)|| (be16(rx+20)&0x3fff))return;
 unsigned iplen=be16(rx+16);if(iplen<28||iplen+14>length)return;
 memcpy(tx,rx+6,6);memcpy(tx+6,ownmac,6);put16(tx+12,0x0800);
 memcpy(tx+14,rx+14,20);memcpy(tx+26,ownip,4);memcpy(tx+30,rx+26,4);tx[22]=64;
 if(rx[23]==1&&rx[34]==8&&rx[35]==0){
  if(checksum(rx+34,iplen-20))return;
  memcpy(tx+34,rx+34,iplen-20);tx[34]=0;put16(tx+36,0);put16(tx+36,checksum(tx+34,iplen-20));
  put16(tx+24,0);put16(tx+24,checksum(tx+14,20));send_frame(iplen+14);return;
 }
 if(rx[23]!=17||be16(rx+36)!=6000)return;
 unsigned udplen=be16(rx+38);if(udplen<24||udplen+20!=iplen)return;
 ++rx_count;
 unsigned out=process(rx+42,udplen-8,tx+42);if(!out)return;
 put16(tx+34,6000);memcpy(tx+36,rx+34,2);put16(tx+38,out+8);put16(tx+40,0);
 put16(tx+16,out+28);put16(tx+24,0);put16(tx+24,checksum(tx+14,20));
 send_frame(out+42);
}
int main(void){
 timer_init();xil_printf("E35_START,1,128KiB,100MHz\r\n");
 int rc=crypto_init();xil_printf("E35_CRYPTO_INIT,%u\r\n",rc);if(rc)goto fail;
 rc=XEmacLite_Initialize(&mac,ETH_BASE);if(rc)goto fail;
 XEmacLite_SetMacAddress(&mac,(u8*)ownmac);XEmacLite_FlushReceive(&mac);
 rc=phy_init();if(rc)goto fail;
 xil_printf("E35_READY,192.168.10.2,6000,AES256GCM,1024\r\n");
 for(;;){unsigned n=XEmacLite_Recv(&mac,rx);if(n)packet(n);}
fail:
 xil_printf("E35_FATAL,%u\r\n",rc);
 XSecure_AesKeyZero(&aes,XSECURE_AES_USER_KEY_0);
 for(;;){}
}
