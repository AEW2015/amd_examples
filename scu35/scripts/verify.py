"""Read-only source, artifact, capture and public-signature audit. Never accesses hardware."""
from pathlib import Path
import hashlib,json,sys,re
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    paths=json.loads((ROOT/'manifest.json').read_text())['files']
    for name,expected in paths.items():
        p=ROOT/name
        assert p.is_file(),name
        assert sha(p)==expected,'Hash mismatch: '+name
    handoff=json.loads((ROOT/'handoff.json').read_text())
    assert handoff['overall']=='PASS'
    for item in handoff['artifacts']:assert sha(ROOT/item['path'])==item['sha256'],item['path']
    sys.path.insert(0,str(ROOT/'host'))
    from compare import parse_capture
    parsed=parse_capture(ROOT/'evidence/timer/uart.txt','7d1bf77bc454dd1f')
    assert len(parsed['rows'])==31 and len(parsed['hashes'])==10 and len(parsed['aes'])==5
    uart=(ROOT/'evidence/timer/uart.txt').read_text(encoding='utf-8-sig')
    assert 'TMR_META,axi_timer,64,100000000,40000000' in uart
    carry=re.search(r'TMR_TEST,carry,1,(\d+)',uart);assert carry and int(carry[1])>=4096
    monotonic=re.search(r'TMR_TEST,monotonic,1000,(\d+),(\d+)',uart)
    assert monotonic and 0<int(monotonic[1])<=int(monotonic[2])
    sys.path.insert(0,str(ROOT/'native'))
    import analyze
    native=analyze.validate(ROOT/'evidence/native/results.txt')
    assert len(native['rows'])==66 and len(native['pq_rows'])==24
    sys.path.insert(0,str(ROOT/'scripts'))
    from pdi import verify_signed,header,parts,decrypt_chain
    s,_=verify_signed((ROOT/'reference/boot/signed.pdi').read_bytes(),ROOT/'evidence/boot/bundle')
    assert all(s[k] for k in ['spk_signature_valid','hash_block_signature_valid','boot_header_hash_valid'])
    bad,_=verify_signed((ROOT/'reference/boot/badsig.pdi').read_bytes(),ROOT/'evidence/boot/bundle')
    assert not bad['hash_block_signature_valid'],'Tampered HSS signature accepted'
    plain=(ROOT/'reference/boot/plain.pdi').read_bytes();ph=header(plain)
    plain_a,plain_b,_,_=parts(plain,ph,plain[0x340:0x3d0])
    parameters=json.loads((ROOT/'reference/boot/public_demo_parameters.json').read_text())
    key=bytes.fromhex(parameters['root_key_hex']);assert key==bytes(32)
    combo=(ROOT/'reference/boot/combo.pdi').read_bytes()
    cs,(_,_,_,_,a,b)=verify_signed(combo,ROOT/'evidence/boot/bundle')
    assert all(cs[k] for k in ['spk_signature_valid','hash_block_signature_valid','boot_header_hash_valid'])
    iv=bytes.fromhex(parameters['ivs']['combo_plm'])
    clear_a,roll_a=decrypt_chain(a,key,iv)
    clear_b,roll_b=decrypt_chain(b,key,iv[:-1]+bytes([(iv[-1]+1)&255]))
    assert clear_a==plain_a and clear_b==plain_b
    # Public distribution must not contain private signing state or tool/venv caches.
    forbidden=[p for p in ROOT.rglob('*') if p.is_file() and not any(x in p.parts for x in ['out','.venv']) and p.suffix in ['.prv','.aux','.nky','.pem']]
    assert not forbidden,forbidden
    print(json.dumps({'overall':'PASS','sha256_files':len(paths),'runtime_rows':31,'hash_vectors':10,'aes_vectors':5,'native_bulk_batches':66,'native_pq_batches':24,'public_hss_signatures':'PASS','tampered_hss_rejected':True,'combo_rolling_blocks':len(roll_a)+len(roll_b),'decrypted_payloads_match':True,'hardware_operations':'NONE'},indent=2))
if __name__=='__main__':main()
