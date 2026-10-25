"""Independent checks of real PDI signatures, payloads and rolling-key chains.

Functional educational verifier, not a production security implementation.
No device access. Demonstration AES keys remain in local .nky files.
"""
from pathlib import Path
import hashlib, importlib.util, json, re, struct
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

HERE=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
h3=lambda b:hashlib.sha3_256(b).digest()
shake=lambda b:hashlib.shake_256(b).digest(32)
u32=lambda b,at:struct.unpack_from('<I',b,at)[0]

def folder():return Path(json.loads((HERE/'latest_build.json').read_text())['folder'])

def header(p):
    assert len(p)>=0x340 and u32(p,0x14)==0x584c4e58
    assert sum(struct.unpack_from('<204I',p,0x10))&0xffffffff==0xffffffff, 'Boot-header checksum'
    return dict(zip(['key_source','plm_offset','pl_load','pl_bytes','pl_encoded','plm_bytes','plm_encoded','attributes'],struct.unpack_from('<8I',p,0x18)))

def strip_chain(p,at,total,root,encrypted=False):
    """Check SHA3-256 chain over 8 KiB encoded chunks, remove successor hashes."""
    result=bytearray();chunks=0;start=at
    while total:
        n=min(8192+(64 if encrypted and chunks==0 else 0),total);block=p[at:at+n]
        assert len(block)==n and h3(block)==root, f'Partition SHA3 chain at {at:#x}'
        if total>n:result.extend(block[:-32]);root=block[-32:]
        else:result.extend(block)
        at+=n;total-=n;chunks+=1
    return bytes(result),chunks

def parts(p,h,hb):
    a,n=strip_chain(p,h['plm_offset'],h['plm_encoded'],hb[40:72],h['key_source']!=0)
    b,m=strip_chain(p,h['plm_offset']+h['plm_encoded'],h['pl_encoded'],hb[76:108],h['key_source']!=0)
    assert h['plm_offset']+h['plm_encoded']+h['pl_encoded']==len(p)
    return a,b,n,m

def load_ref(out):
    spec=importlib.util.spec_from_file_location('boot_hss_ref',out/'hss_ref.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def verify_signed(p,out):
    h=header(p);ref=load_ref(out)
    assert h['key_source'] in [0,0xa5c3c5a3] and h['attributes']>>18&3==3
    ppk_total,ppk_actual,sign_total,sign_actual=struct.unpack_from('<4I',p,0x7c)
    assert ppk_total==64 and ppk_actual==60
    cert=0x340;ppk=p[cert:cert+ppk_actual]
    spk_total,spk_actual,spksig_total,spksig_actual=struct.unpack_from('<4I',p,cert+ppk_total)
    assert spk_total==64 and spk_actual==60
    spk_at=cert+ppk_total+32
    spk=p[spk_at:spk_at+spk_actual]
    spksig_at=spk_at+spk_total
    spksig=p[spksig_at:spksig_at+spksig_actual]
    hb_at=spksig_at+spksig_total;hb=p[hb_at:hb_at+u32(p,0x78)]
    sig_at=hb_at+len(hb);sig=p[sig_at:sig_at+sign_actual]
    assert sig_at+sign_total==h['plm_offset']
    spk_ok=ref.verify_hss(shake(p[cert+ppk_total:spk_at+spk_actual]),spksig,ppk)
    hb_ok=ref.verify_hss(shake(hb),sig,spk)
    bh_ok=h3(p[16:0x340])==hb[4:36]
    a,b,n,m=parts(p,h,hb)
    return {'header':h,'ppk_sha256':sha(ppk),'spk_sha256':sha(spk),
        'spk_signature_valid':spk_ok,'hash_block_signature_valid':hb_ok,'boot_header_hash_valid':bh_ok,
        'signature_bytes':sign_actual,'signature_offset':sig_at,'hash_block_offset':hb_at,
        'plm_sha256':sha(a),'pl_sha256':sha(b),'plm_bytes':len(a),'pl_bytes':len(b),
        'chain_chunks':n+m},(ppk,spk,hb,sig,a,b)

def root_material(path):
    text=path.read_text()
    return bytes.fromhex(re.search(r'Key\s+0\s+([0-9a-fA-F]{64})',text)[1]),bytes.fromhex(re.search(r'IV\s+0\s+([0-9a-fA-F]{24})',text)[1])

def decrypt_chain(data,key,iv):
    pt=AESGCM(key).decrypt(iv,data[:64],None)
    key,iv,n=pt[:32],pt[32:44],u32(pt,44)*4
    at=64;clear=bytearray();rows=[]
    while n:
        assert n<=8192 and at+n+64<=len(data)
        start=at;pt=AESGCM(key).decrypt(iv,data[at:at+n+64],None)
        assert len(pt)==n+48
        clear.extend(pt[:n])
        rows.append({'block':len(rows),'offset':at,'payload_bytes':n,'encoded_bytes':n+64,
                     'key_fingerprint':sha(key)[:16],'tag_verified':True})
        key,iv,n=pt[-48:-16],pt[-16:-4],u32(pt,len(pt)-4)*4
        at+=len(pt)+16
    assert at==len(data) and key==bytes(32) and iv==bytes(12), 'Unaccounted rolling stream'
    assert len(set(x['key_fingerprint'] for x in rows))==len(rows)
    return bytes(clear),rows

if __name__ == '__main__':
    raise SystemExit('Use python lab.py verify or python lab.py boot; this file provides the offline parser API.')
