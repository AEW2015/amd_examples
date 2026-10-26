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
    executions=ROOT/'evidence/notebooks/executions.json'
    if executions.exists():
        import nbformat
        for item in json.loads(executions.read_text()):
            notebook=ROOT/'notebooks'/item['notebook']
            assert sha(notebook)==item['notebook_sha256'],notebook
            nb=nbformat.read(notebook,as_version=4);nbformat.validate(nb)
            outputs=[o for cell in nb.cells for o in cell.get('outputs',[])]
            assert outputs and not any(o.output_type=='error' for o in outputs),notebook
            if item.get('evidence_directory'):
                folder=ROOT/item['evidence_directory']
                for name,expected in item['files'].items():assert sha(folder/name)==expected,(folder,name)
                session=json.loads((folder/'session.json').read_text())
                assert session['demo_pass'] and session['recovery_pass'],folder
                if session['mode']=='runtime':assert len(parse_capture(folder/'uart.txt','7d1bf77bc454dd1f')['rows'])==31
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
    ethernet=ROOT/'ethernet/evidence/run3'
    if ethernet.exists():
        sys.path.insert(0,str(ROOT/'ethernet'))
        from verify_capture import verify as verify_ethernet
        verify_ethernet(ethernet/'ethernet/results.json')
        session=json.loads((ethernet/'session.json').read_text())
        assert session['hardware_pass'] and session['recovery_pass']
        assert session['pdi_sha256'] in {sha(p) for p in (ROOT/'ethernet/reference').glob('ethernet*.pdi')}
    v2=ROOT/'ethernet/evidence/run4'
    if v2.exists():
        verify_ethernet(v2/'ethernet/results.json')
        session=json.loads((v2/'session.json').read_text())
        assert session['hardware_pass'] and session['pq_pass'] and session['recovery_pass']
        assert sha(ROOT/'ethernet/reference/ethernet.pdi')==session['pdi_sha256']
        pq=json.loads((v2/'pq.json').read_text());assert pq['overall']=='PASS' and len(pq['rows'])==40
        assert len(pq['guards'])==6 and all(g['status']==g['expected_status'] for g in pq['guards'])
        import struct
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        for row in pq['rows']:
            wire=bytes.fromhex(row['response_hex'])
            result=AESGCM(bytes(range(32))).decrypt(wire[32:44],wire[44:],wire[:32])
            magic,ident,accepted,status,ticks,count,received,flags=struct.unpack('!4s7I',result)
            assert magic==b'PQR1' and received==4608 and flags==31 and ticks>0
            assert bool(accepted)==row['accepted']==(row['case']=='valid')
            assert status==row['vendor_status']==(0 if accepted else 0xAB)
            assert ticks/100==row['device_verify_us'] and row['result_matches_python']
        handoff=json.loads((ROOT/'ethernet/handoff.json').read_text());assert handoff['overall']=='PASS'
        for artifact in handoff['artifacts']:assert sha(ROOT/'ethernet'/artifact['path'])==artifact['sha256']
    print(json.dumps({'overall':'PASS','sha256_files':len(paths),'runtime_rows':31,'hash_vectors':10,'aes_vectors':5,'native_bulk_batches':66,'native_pq_batches':24,'public_hss_signatures':'PASS','tampered_hss_rejected':True,'combo_rolling_blocks':len(roll_a)+len(roll_b),'decrypted_payloads_match':True,'hardware_operations':'NONE'},indent=2))
if __name__=='__main__':main()
