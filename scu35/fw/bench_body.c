/* Application benchmark, not an isolated hard-engine throughput test. */
#define FAST_REPEATS 20U
#define PQ_REPEATS 10U
#define SHARED __attribute__((aligned(64),section(".shared")))
static u8 Work[6144] SHARED;
static XSecure_Aes Aes SHARED;
static u8 Key[32] SHARED;
static u8 Iv[16] SHARED;
static u8 Tag[16] SHARED;
static u8 Digest[32] SHARED;
static u8 LocalData[2048];
extern u8 __shared_start[], __shared_end[];
/* AMD AXI Timer v2.0 register layout (PG079 / xtmrctr_l.h).
 * Both 32-bit channels form one free-running 64-bit counter at 100 MHz.
 * No interrupt, external capture or PWM is enabled.
 */
#define TMR_BASE 0x40000000U
#define TMR_CASC 0x800U
#define TMR_ENT  0x080U
#define TMR_LOAD 0x020U
#define TMR_ARHT 0x010U
static u64 timer_ticks64(void) {
    u32 hi,lo,again;
    do {
        hi=Xil_In32(TMR_BASE+0x18U);
        lo=Xil_In32(TMR_BASE+0x08U);
        again=Xil_In32(TMR_BASE+0x18U);
    } while(hi!=again);
    return ((u64)hi<<32)|lo;
}
/* Existing CMP v2 rows contain 32-bit elapsed ticks. Each individual interval
 * is below 2^32 ticks (42.95 s); subtraction remains modulo 2^32. The hardware
 * timer and coherent reader are 64-bit. Read overhead is retained, not removed.
 */
static u32 ticks(void) { return (u32)timer_ticks64(); }
static void timer_load(u32 hi,u32 lo) {
    Xil_Out32(TMR_BASE,0U);
    Xil_Out32(TMR_BASE+0x10U,0U);
    Xil_Out32(TMR_BASE+4U,lo);
    Xil_Out32(TMR_BASE+0x14U,hi);
    Xil_Out32(TMR_BASE+0x10U,TMR_LOAD);
    Xil_Out32(TMR_BASE,TMR_CASC|TMR_LOAD);
    Xil_Out32(TMR_BASE+0x10U,0U);
    Xil_Out32(TMR_BASE,TMR_CASC|TMR_ARHT);
}
static int timer_selftest(void) {
    /* Force a lower-half carry without waiting 42.95 seconds. */
    timer_load(0x12345678U,0xfffff000U);
    u64 stopped=timer_ticks64();
    if(stopped!=0x12345678fffff000ULL)return 1;
    if(timer_ticks64()!=stopped)return 2;
    Xil_Out32(TMR_BASE,TMR_CASC|TMR_ARHT|TMR_ENT);
    u64 now=stopped;
    for(u32 n=0;n<100000U;++n){now=timer_ticks64();if((u32)(now>>32)!=0x12345678U)break;}
    if((u32)(now>>32)!=0x12345679U || now<=stopped)return 3;
    xil_printf("TMR_TEST,carry,1,%u\r\n",(u32)(now-stopped));
    timer_load(0,0);
    if(timer_ticks64()!=0)return 4;
    Xil_Out32(TMR_BASE,TMR_CASC|TMR_ARHT|TMR_ENT);
    u64 last=timer_ticks64();
    u32 lo=~0U,hi=0;
    for(u32 n=0;n<1000;++n){
        now=timer_ticks64();
        if(now<=last)return 5;
        u32 delta=(u32)(now-last);if(delta<lo)lo=delta;if(delta>hi)hi=delta;
        last=now;
    }
    if((Xil_In32(TMR_BASE)&(TMR_CASC|TMR_ENT|0x40U))!=(TMR_CASC|TMR_ENT))return 6;
    xil_printf("TMR_TEST,monotonic,1000,%u,%u\r\n",lo,hi);
    xil_printf("TMR_META,axi_timer,64,100000000,40000000\r\n");
    return 0;
}

static void hex(const u8 *p,u32 n) { for(u32 i=0;i<n;++i) xil_printf("%02x",p[i]); }
static void row(const char *algo,const char *which,u32 size,u32 n,u32 copy,u32 setup,
                u32 api,u32 check,u32 lo,u32 hi,int status) {
    xil_printf("CMP_ROW,%s,%s,%u,%u,%u,%u,%u,%u,%u,%u,%u\r\n",
        algo,which,size,n,copy,setup,api,check,lo,hi,status);
}
static int fresh_iv(void) {
    XTrngpsx_Instance rng;
    u8 seed[32];
    XTrngpsx_Config *cfg=XTrngpsx_LookupConfig(0U);
    XTrngpsx_UserConfig user={.Mode=XTRNGPSX_HRNG_MODE,
        .SeedLife=XTRNGPSX_USER_CFG_SEED_LIFE,.DFLength=XTRNGPSX_USER_CFG_DF_LENGTH,
        .AdaptPropTestCutoff=XTRNGPSX_USER_CFG_ADAPT_TEST_CUTOFF,
        .RepCountTestCutoff=XTRNGPSX_USER_CFG_REP_TEST_CUTOFF,.IsBlocking=FALSE};
    if(!cfg) return XST_FAILURE;
    int status=XTrngpsx_CfgInitialize(&rng,cfg,cfg->BaseAddress);
    if(!status) status=XTrngpsx_PreOperationalSelfTests(&rng);
    if(!status) status=XTrngpsx_Instantiate(&rng,NULL,0U,NULL,&user);
    if(!status) status=XTrngpsx_Generate(&rng,seed,sizeof(seed),FALSE);
    if(status) return status;
    for(u32 i=0;i<8;++i) Iv[i]=seed[i];
    return XTrngpsx_Uninstantiate(&rng);
}
static int hashes(void) {
    const u32 sizes[]={16,64,256,1024,2048};
    for(u32 mode=0;mode<2;++mode) for(u32 s=0;s<5;++s) {
        u32 size=sizes[s],copy=0,setup=0,api=0,lo=~0U,hi=0,t,elapsed;
        const char *name=mode?"SHAKE-256":"SHA3-256";
        for(u32 r=0;r<FAST_REPEATS;++r) {
            t=ticks();
            for(u32 i=0;i<size;++i) ((volatile u8 *)Work)[i]=LocalData[i];
            copy+=ticks()-t;
            t=ticks(); int status=XSecure_ShaInitialize(&SecureSha,&PmcDma); setup+=ticks()-t;
            if(status) return status;
            t=ticks(); status=XSecure_ShaDigest(&SecureSha,mode?XSECURE_SHAKE_256:XSECURE_SHA3_256,
                (UINTPTR)Work,size,(UINTPTR)Digest,32); elapsed=ticks()-t; api+=elapsed;
            if(status) return status;
            if(elapsed<lo) lo=elapsed; if(elapsed>hi) hi=elapsed;
        }
        row(name,"valid",size,FAST_REPEATS,copy,setup,api,0,lo,hi,0);
        xil_printf("CMP_HASH,%s,%u,",name,size); hex(Digest,32); xil_printf("\r\n");
    }
    return 0;
}
static int aes(void) {
    const u32 sizes[]={16,64,256,1024,2048};
    u8 *data=Work,*encrypted=Work+2048,*decrypted=Work+4096;
    int status=XSecure_AesInitialize(&Aes,&PmcDma);
    if(status) return status;
    /* PUBLIC diagnostic key bytes 00..1f. USER_KEY_0 is volatile, never eFUSE. */
    for(u32 i=0;i<32;++i) Key[i]=(u8)i;
    status=XSecure_AesWriteKey(&Aes,XSECURE_AES_USER_KEY_0,XSECURE_AES_KEY_SIZE_256,(UINTPTR)Key);
    if(status) return status;
    status=fresh_iv(); if(status) return status;
    u32 nonce=0;
    for(u32 s=0;s<5;++s) {
        u32 size=sizes[s],copy=0,es=0,ea=0,ds=0,da=0,check=0,t,e,elo=~0U,ehi=0,dlo=~0U,dhi=0;
        for(u32 r=0;r<FAST_REPEATS;++r) {
            t=ticks();
            for(u32 i=0;i<size;++i) ((volatile u8 *)data)[i]=LocalData[i];
            copy+=ticks()-t;
            ++nonce; for(u32 i=0;i<4;++i) Iv[8+i]=(u8)(nonce>>(24-8*i));
            t=ticks(); status=XSecure_AesEncryptInit(&Aes,XSECURE_AES_USER_KEY_0,
                XSECURE_AES_KEY_SIZE_256,(UINTPTR)Iv); es+=ticks()-t; if(status) return status;
            t=ticks(); status=XSecure_AesEncryptData(&Aes,(UINTPTR)data,(UINTPTR)encrypted,size,(UINTPTR)Tag);
            e=ticks()-t; ea+=e; if(status) return status; if(e<elo) elo=e; if(e>ehi) ehi=e;
            t=ticks(); status=XSecure_AesDecryptInit(&Aes,XSECURE_AES_USER_KEY_0,
                XSECURE_AES_KEY_SIZE_256,(UINTPTR)Iv); ds+=ticks()-t; if(status) return status;
            t=ticks(); status=XSecure_AesDecryptData(&Aes,(UINTPTR)encrypted,(UINTPTR)decrypted,size,(UINTPTR)Tag);
            e=ticks()-t; da+=e; if(status) return status; if(e<dlo) dlo=e; if(e>dhi) dhi=e;
            t=ticks(); for(u32 i=0;i<size;++i) if(decrypted[i]!=LocalData[i]) return XST_FAILURE;
            check+=ticks()-t;
        }
        row("AES-GCM-ENC","valid",size,FAST_REPEATS,copy,es,ea,0,elo,ehi,0);
        row("AES-GCM-DEC","valid",size,FAST_REPEATS,0,ds,da,check,dlo,dhi,0);
        xil_printf("CMP_AES,%u,",size); hex(Iv,12); xil_printf(","); hex(encrypted,size);
        xil_printf(","); hex(Tag,16); xil_printf("\r\n");
        Tag[0]^=1;
        status=XSecure_AesDecryptInit(&Aes,XSECURE_AES_USER_KEY_0,XSECURE_AES_KEY_SIZE_256,(UINTPTR)Iv);
        if(status) return status;
        status=XSecure_AesDecryptData(&Aes,(UINTPTR)encrypted,(UINTPTR)decrypted,size,(UINTPTR)Tag);
        Tag[0]^=1;
        xil_printf("CMP_NEG,AES-GCM,%u,%u\r\n",size,status);
        if(status!=XSECURE_AES_GCM_TAG_MISMATCH) return XST_FAILURE;
    }
    return XSecure_AesKeyZero(&Aes,XSECURE_AES_USER_KEY_0);
}
static int verify(int hss) {
    if(hss) {
        XSecure_HssInitParams p;
        p.SignBuff=Work;p.SignatureLen=XSECURE_LMS_HSS_EXAMPLE_HSS_SIG_SIZE;
        p.PublicKey=Work+4544;p.PublicKeyLen=XSECURE_HSS_PUBLIC_KEY_TOTAL_SIZE;
        return XSecure_HssSignatureVerification(&SecureSha,&PmcDma,&p,Work+4480,56);
    }
    XSecure_LmsSignVerifyParams p;
    p.Data=Work+4480;p.DataLen=56;p.PreHashedMsg=FALSE;
    p.LmsSign=Work;p.LmsSignLen=XSECURE_LMS_HSS_EXAMPLE_LMS_SIG_SIZE;
    p.ExpectedPubKey=Work+4544;p.PubKeyLen=XSECURE_LMS_PUB_KEY_TOTAL_SIZE;
    return XSecure_LmsSignatureVerification(&SecureSha,&PmcDma,&p);
}
static int pq(void) {
    const char *cases[]={"valid","bad_signature","bad_message","bad_key"};
    for(u32 hss=0;hss<2;++hss) {
        const char *algo=hss?"HSS-SHAKE256":"LMS-SHAKE256";
        u32 siglen=hss?4464U:4460U,keylen=hss?60U:56U;
        const u8 *sig=hss?HssShake256Signature:LmsShake256Signature;
        const u8 *msg=hss?HssShake256Data:LmsShake256Data;
        const u8 *key=hss?HssShake256PubKey:LmsShake256PubKey;
        for(u32 i=0;i<siglen;++i) Work[i]=sig[i];
        for(u32 i=0;i<56;++i) Work[4480+i]=msg[i];
        for(u32 i=0;i<keylen;++i) Work[4544+i]=key[i];
        int status=XSecure_InitDmaAndSha(&PmcDma,&SecureSha);if(status) return status;
        status=XSecure_ShaDigest(&SecureSha,XSECURE_SHA3_256,(UINTPTR)(Work+4544),keylen,(UINTPTR)Digest,32);
        if(status) return status;
        xil_printf("CMP_VECTOR,%s,56,%u,%u,",algo,siglen,keylen);hex(Digest,32);xil_printf("\r\n");
        for(u32 c=0;c<4;++c) {
            if(c==1) Work[32]^=1;if(c==2) Work[4480]^=1;if(c==3) Work[4544+keylen-1]^=1;
            u32 setup=0,api=0,lo=~0U,hi=0,t,e;
            for(u32 r=0;r<PQ_REPEATS;++r) {
                t=ticks();status=XSecure_InitDmaAndSha(&PmcDma,&SecureSha);setup+=ticks()-t;if(status)return status;
                t=ticks();status=verify(hss);e=ticks()-t;api+=e;if(e<lo)lo=e;if(e>hi)hi=e;
                if((c==0 && status) || (c!=0 && status!=XSECURE_LMS_PUB_KEY_AUTHENTICATION_FAILED_ERROR &&
                    status!=XSECURE_LMS_HSS_L0_PUB_KEY_AUTH_FAILED_ERROR && status!=XSECURE_LMS_HSS_L1_PUB_KEY_AUTH_FAILED_ERROR)) return XST_FAILURE;
            }
            row(algo,cases[c],56,PQ_REPEATS,0,setup,api,0,lo,hi,status);
            if(c==1) Work[32]^=1;if(c==2) Work[4480]^=1;if(c==3) Work[4544+keylen-1]^=1;
        }
    }
    return 0;
}
int main(void) {
    for(volatile u8 *p=__shared_start;p<__shared_end;++p)*p=0;
    for(u32 i=0;i<2048;++i)LocalData[i]=(u8)((i%251)+1);
    int timer_status=timer_selftest();
    if(timer_status){xil_printf("TMR_FAIL,%u\r\n",timer_status);for(;;){}}
    u32 first=ticks(),second=ticks();
    xil_printf("CMP_META,1,100000000,20,10,%s,%u\r\n",CMP_BUILD_ID,second-first);
    int status=XSecure_InitDmaAndSha(&PmcDma,&SecureSha);
    if(!status)status=hashes();
    if(!status)status=aes();
    if(!status)status=pq();
    xil_printf("CMP_DONE,%u\r\n",status);
    for(;;) { }
}
