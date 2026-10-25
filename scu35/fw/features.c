/* Hardware-only lifecycle measurements; never exports PUF helper/key material. */
static int random_modes(void) {
    const u32 modes[]={XTRNGPSX_HRNG_MODE,XTRNGPSX_DRNG_MODE,XTRNGPSX_PTRNG_MODE};
    const char *names[]={"TRNG-HRNG","TRNG-DRNG","TRNG-PTRNG"};
    for(u32 m=0;m<3;++m) {
        XTrngpsx_Instance rng;
        u8 output[32],previous[32],entropy[80],personal[48];
        for(u32 i=0;i<80;++i)entropy[i]=(u8)i; /* PUBLIC DRNG test seed, not live entropy. */
        for(u32 i=0;i<48;++i)personal[i]=(u8)(i+80);
        XTrngpsx_Config *cfg=XTrngpsx_LookupConfig(0U);if(!cfg)return XST_FAILURE;
        XTrngpsx_UserConfig user={.Mode=modes[m],.SeedLife=XTRNGPSX_USER_CFG_SEED_LIFE,
            .DFLength=m==1?4U:XTRNGPSX_USER_CFG_DF_LENGTH,
            .AdaptPropTestCutoff=XTRNGPSX_USER_CFG_ADAPT_TEST_CUTOFF,
            .RepCountTestCutoff=XTRNGPSX_USER_CFG_REP_TEST_CUTOFF,.IsBlocking=FALSE};
        u32 t=ticks();
        int status=XTrngpsx_CfgInitialize(&rng,cfg,cfg->BaseAddress);
        if(!status)status=XTrngpsx_PreOperationalSelfTests(&rng);
        if(!status)status=XTrngpsx_Instantiate(&rng,m==1?entropy:NULL,m==1?80:0,m==1?personal:NULL,&user);
        u32 setup=ticks()-t;
        xil_printf("CMP_FEATURE,%s-SETUP,1,%u,%u\r\n",names[m],setup,status);
        if(status)return status;
        u32 cycles=0,lo=~0U,hi=0;
        for(u32 r=0;r<20;++r) {
            t=ticks();status=XTrngpsx_Generate(&rng,output,32,FALSE);u32 e=ticks()-t;
            cycles+=e;if(e<lo)lo=e;if(e>hi)hi=e;if(status)return status;
            u32 any=0,diff=0;
            for(u32 i=0;i<32;++i){any|=output[i];if(r)diff|=output[i]^previous[i];previous[i]=output[i];}
            if(!any || (r && !diff))return XST_FAILURE;
        }
        row(names[m],"generate",32,20,0,0,cycles,0,lo,hi,0);
        xil_printf("CMP_RANDOM,%s,",names[m]);hex(output,32);xil_printf("\r\n");
        status=XTrngpsx_Uninstantiate(&rng);if(status)return status;
    }
    return 0;
}
static int puf_lifecycle(void) {
    XPuf_Data *p=(XPuf_Data *)(void *)Work;
    u8 *plain=Work+4096,*cipher=Work+4160,*decoded=Work+4224;
    if(sizeof(XPuf_Data)>4096)return XST_FAILURE;
    for(u32 i=0;i<sizeof(Work);++i)Work[i]=0;
    p->ShutterValue=XPUF_SHUTTER_VALUE;p->GlobalVarFilter=TRUE;p->RoSwapVal=0;
    p->PufOperation=XPUF_REGEN_ON_DEMAND;
    u32 t=ticks();int status=XPuf_Registration(p);u32 e=ticks()-t;
    xil_printf("CMP_FEATURE,PUF-REGISTER,1,%u,%u\r\n",e,status);if(status)return status;
    status=XSecure_AesInitialize(&Aes,&PmcDma);if(status)return status;
    for(u32 i=0;i<16;++i)plain[i]=(u8)(i+1);
    /* A single known plaintext/IV pair. Regeneration only decrypts this saved ciphertext. */
    for(u32 i=0;i<12;++i)Iv[i]=(u8)(i+32);
    status=XSecure_AesEncryptInit(&Aes,XSECURE_AES_PUF_KEY,XSECURE_AES_KEY_SIZE_256,(UINTPTR)Iv);
    if(status)return status;
    t=ticks();status=XSecure_AesEncryptData(&Aes,(UINTPTR)plain,(UINTPTR)cipher,16,(UINTPTR)Tag);e=ticks()-t;
    xil_printf("CMP_FEATURE,PUF-AES-ENC,1,%u,%u\r\n",e,status);if(status)return status;
    p->Aux>>=XPUF_AUX_SHIFT_VALUE; /* Registration returns packed AUX; regeneration shifts it. */
    p->SyndromeAddr=(u32)(UINTPTR)p->SyndromeData;
    u32 regen_total=0,clear_total=0,dec_total=0;
    for(u32 r=0;r<5;++r) {
        t=ticks();status=XSecure_AesKeyZero(&Aes,XSECURE_AES_PUF_KEY);clear_total+=ticks()-t;
        if(status)return status;
        status=XSecure_AesDecryptInit(&Aes,XSECURE_AES_PUF_KEY,XSECURE_AES_KEY_SIZE_256,(UINTPTR)Iv);
        xil_printf("CMP_PUF_CLEARED,%u,%u\r\n",r,status);
        /* The driver rejects the zeroized PUF source before DMA/decryption. */
        if(status!=XSECURE_AES_ZERO_PUF_KEY_NOT_ALLOWED)return XST_FAILURE;
        t=ticks();status=XPuf_Regeneration(p);e=ticks()-t;regen_total+=e;
        xil_printf("CMP_PUF_REGEN,%u,%u,%u\r\n",r,e,status);if(status)return status;
        status=XSecure_AesDecryptInit(&Aes,XSECURE_AES_PUF_KEY,XSECURE_AES_KEY_SIZE_256,(UINTPTR)Iv);
        if(status)return status;
        t=ticks();status=XSecure_AesDecryptData(&Aes,(UINTPTR)cipher,(UINTPTR)decoded,16,(UINTPTR)Tag);dec_total+=ticks()-t;
        if(status)return status;
        for(u32 i=0;i<16;++i)if(decoded[i]!=plain[i])return XST_FAILURE;
    }
    xil_printf("CMP_FEATURE,PUF-KEY-CLEAR,5,%u,0\r\n",clear_total);
    xil_printf("CMP_FEATURE,PUF-REGENERATE,5,%u,0\r\n",regen_total);
    xil_printf("CMP_FEATURE,PUF-AES-DEC,5,%u,0\r\n",dec_total);
    xil_printf("CMP_PUF_ROUNDTRIP,5,0\r\n");
    status=XSecure_AesKeyZero(&Aes,XSECURE_AES_PUF_KEY);if(status)return status;
    for(volatile u8 *q=Work;q<Work+sizeof(Work);++q)*q=0;
    return status;
}
