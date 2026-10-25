"""Verify Bootgen's hashed partitions and bind our loader to the actual CDO."""
import hashlib,json,struct,sys
from pathlib import Path

BASE=Path(__file__).resolve().parent
def decode(image,offset,length,total,root):
    result=bytearray();at=offset;remaining=length;chunks=0
    while remaining:
        count=min(0x1fe0,remaining);encoded=count+(32 if remaining>count else 0)
        block=image[at:at+encoded]
        assert len(block)==encoded and hashlib.sha3_256(block).digest()==root
        result.extend(block[:count])
        if remaining>count: root=block[-32:]
        at+=encoded;remaining-=count;chunks+=1
    assert at==offset+total
    return bytes(result),chunks

def inspect(path):
    p=path.read_bytes()
    offset,_,length,total,plm_length,plm_total=struct.unpack_from('<6I',p,0x1c)
    assert plm_total<=0xa200
    plm,plm_chunks=decode(p,offset,plm_length,plm_total,p[0x368:0x388])
    cdo,chunks=decode(p,offset+plm_total,length,total,p[0x38c:0x3ac])
    words=struct.unpack('<%dI'%(len(cdo)//4),cdo)
    assert words[0]==4 and words[1]==0x004f4443 and words[2]==0x200
    assert words[3]+5==len(words) and sum(words[:5])&0xffffffff==0xffffffff
    at=5;ops={};writes=set();stream_words=0
    while at<len(words):
        command=words[at];at+=1;op=command&65535;n=(command>>16)&255
        assert not command>>24
        if n==255: n=words[at];at+=1
        assert at+n<=len(words)
        ops[hex(op)]=ops.get(hex(op),0)+1
        if op==0x103:
            assert n==2
            writes.add(words[at])
        if op==0x10d:
            assert list(words[at:at+3])==[0,0x04070000,0x4000]
            stream_words+=n-3
        assert op in [0x101,0x103,0x10d,0x111,0x119,0x130]
        at+=n
    return dict(pdi_sha256=hashlib.sha256(p).hexdigest(),plm_length=plm_length,plm_encoded_bytes=plm_total,
                cdo_bytes=length,cdo_encoded_bytes=total,cdo_chunks=chunks,plm_chunks=plm_chunks,
                cdo_root=p[0x38c:0x3ac].hex(),commands=sum(ops.values()),stream_words=stream_words,
                operations=ops,write_addresses=sorted(writes)),plm,cdo

if sys.argv[1]=='spec':
    info=json.loads((BASE/'inputs/cdo_spec.json').read_text())
    assert hashlib.sha256((BASE/'inputs/system_wrapper.rcdo').read_bytes()).hexdigest()==info['source_rcdo_sha256']
    text='#ifndef CONFIG_SPEC_H\n#define CONFIG_SPEC_H\n'
    for name,key in [('CDO_BYTES','cdo_bytes'),('CDO_COMMANDS','commands'),('CDO_STREAM_WORDS','stream_words')]:
        text+=f'#define {name} {info[key]}u\n'
    text+='static const uint8_t cdo_root[32]={'+','.join('0x'+info['cdo_root'][i:i+2] for i in range(0,64,2))+'};\n'
    text+='static const uint32_t cdo_write_addresses[]={'+','.join(hex(x) for x in info['write_addresses'])+'};\n#endif\n'
    (BASE/'config_spec.h').write_text(text)
    (BASE/'build/cdo_spec.json').write_text(json.dumps(info,indent=2)+'\n')
elif sys.argv[1]=='derive':
    info,_,_=inspect(BASE/'build/fixture_seed.pdi')
    info['source_rcdo_sha256']=hashlib.sha256((BASE/'inputs/system_wrapper.rcdo').read_bytes()).hexdigest()
    (BASE/'inputs/cdo_spec.json').write_text(json.dumps(info,indent=2)+'\n')
    print('Derived new FPGA CDO specification: '+info['cdo_root'])
elif sys.argv[1]=='verify':
    info,plm,cdo=inspect(BASE/'build/pmc_independent.pdi')
    spec=json.loads((BASE/'build/cdo_spec.json').read_text())
    for key in ['cdo_root','cdo_bytes','commands','stream_words','operations','write_addresses']: assert info[key]==spec[key],key
    # Match all ELF file-backed loads at their native physical addresses.
    elf=(BASE/'build/plm.elf').read_bytes()
    assert elf[:5]==b'\x7fELF\x01'
    entry,phoff=struct.unpack_from('<II',elf,24)
    phsize,phnum=struct.unpack_from('<HH',elf,42)
    assert entry==0x04020000 and struct.unpack_from('<H',elf,18)[0]==243
    for i in range(phnum):
        typ,off,vaddr,paddr,filesz,memsz,flags,align=struct.unpack_from('<8I',elf,phoff+i*phsize)
        if typ!=1: continue
        assert vaddr==paddr and 0x04020000<=vaddr and vaddr+memsz<=0x0402a200
        assert plm[vaddr-entry:vaddr-entry+filesz]==elf[off:off+filesz]
    info.update(status='PASS',elf_sha256=hashlib.sha256(elf).hexdigest(),vendor_plm_code=False,
                sha3_chain_verified=True,elf_loads_match_pdi=True)
    (BASE/'build/pdi_verification.json').write_text(json.dumps(info,indent=2)+'\n')
    (BASE/'build/decoded_cdo.bin').write_bytes(cdo)
    print(json.dumps(info,indent=2))
else: raise ValueError('spec or verify')
