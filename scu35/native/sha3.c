#include <stdint.h>
#include <stddef.h>

void *memset(void *destination,int value,size_t length)
{
    uint8_t *p=destination;
    for(size_t i=0;i<length;++i) p[i]=(uint8_t)value;
    return destination;
}

/* FIPS 202 SHA3-256, written here. No AMD/BootROM hash routines. */
static uint64_t rol(uint64_t x, unsigned n) { return (x<<n)|(x>>(64-n)); }
static void permutation(uint64_t a[25])
{
    static const uint64_t rc[24]={
        0x0000000000000001ULL,0x0000000000008082ULL,0x800000000000808aULL,
        0x8000000080008000ULL,0x000000000000808bULL,0x0000000080000001ULL,
        0x8000000080008081ULL,0x8000000000008009ULL,0x000000000000008aULL,
        0x0000000000000088ULL,0x0000000080008009ULL,0x000000008000000aULL,
        0x000000008000808bULL,0x800000000000008bULL,0x8000000000008089ULL,
        0x8000000000008003ULL,0x8000000000008002ULL,0x8000000000000080ULL,
        0x000000000000800aULL,0x800000008000000aULL,0x8000000080008081ULL,
        0x8000000000008080ULL,0x0000000080000001ULL,0x8000000080008008ULL};
    static const unsigned rot[24]={1,3,6,10,15,21,28,36,45,55,2,14,27,41,56,8,25,43,62,18,39,61,20,44};
    static const unsigned pos[24]={10,7,11,17,18,3,5,16,8,21,24,4,15,23,19,13,12,2,20,14,22,9,6,1};
    uint64_t c[5],t,u;
    for(unsigned round=0;round<24;++round) {
        for(unsigned x=0;x<5;++x) c[x]=a[x]^a[x+5]^a[x+10]^a[x+15]^a[x+20];
        for(unsigned x=0;x<5;++x) {
            t=c[(x+4)%5]^rol(c[(x+1)%5],1);
            for(unsigned y=0;y<25;y+=5) a[y+x]^=t;
        }
        t=a[1];
        for(unsigned i=0;i<24;++i) { u=a[pos[i]];a[pos[i]]=rol(t,rot[i]);t=u; }
        for(unsigned y=0;y<25;y+=5) {
            for(unsigned x=0;x<5;++x) c[x]=a[y+x];
            for(unsigned x=0;x<5;++x) a[y+x]=c[x]^((~c[(x+1)%5])&c[(x+2)%5]);
        }
        a[0]^=rc[round];
    }
}
void sha3_256(const uint8_t *input,size_t length,uint8_t output[32])
{
    uint64_t a[25]={0};unsigned at=0;
    for(size_t i=0;i<length;++i) {
        a[at/8]^=(uint64_t)input[i]<<((at%8)*8);
        if(++at==136) {permutation(a);at=0;}
    }
    a[at/8]^=(uint64_t)6<<((at%8)*8);
    a[16]^=0x8000000000000000ULL;
    permutation(a);
    for(unsigned i=0;i<32;++i) output[i]=(uint8_t)(a[i/8]>>((i%8)*8));
}
