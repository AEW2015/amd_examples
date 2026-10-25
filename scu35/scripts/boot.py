"""Fresh HSS signing state and offline AES rolling-key packaging; no device access."""
from pathlib import Path
import json,secrets,shutil,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lab import ROOT,run,tool,sha,manifest

def build_boot(c,build,height=15):
    for name in ['plm.elf','design.rcdo','demo.pdi']:
        if not (build/name).is_file():raise FileNotFoundError('Build the runtime image first: '+name)
    out=build/('boot_'+time.strftime('%Y%m%dT%H%M%S'))
    out.mkdir() # Never overwrite or resume previously used signing state.
    for name in ['plm.elf','design.rcdo']:shutil.copy2(build/name,out/name)
    shutil.copy2(build/'demo.pdi',out/'plain.pdi')
    ref=(ROOT/'host/hss_ref.py').read_text().replace('_LMS = {15: 5, 16: 10}','_LMS = {15: 5, 16: 10, 17: 15}')
    (out/'hss_ref.py').write_text(ref)
    def bif(partitions,attrs=''):
        return 'new_bif:\n{\n id_code=0x04e80093\n'+attrs+'\n image {name=pmcl_subsys id=0x0\n'+partitions+'\n}\n}\n'
    def bootgen(args,where,label):run([tool(c,'bootgen'),'-arch','spartanup',*args],cwd=where,log=where/(label+'.log'),timeout=3600)
    params=f'lms_key_params {{primary {{lms_shake256_h{height}_w2, lms_shake256_h{height}_w2}} secondary {{lms_shake256_h{height}_w2, lms_shake256_h{height}_w2}}}}\n'
    chosen=None
    for n in range(1,17):
        keys=out/f'keys{n:02}';keys.mkdir()
        (keys/'keys.bif').write_text(bif('',params+'pskfile=primary.key\nsskfile=secondary.key\nppkfile=primary.key.pub\nspkfile=secondary.key.pub'))
        bootgen(['-image','keys.bif','-generate_keys','lms'],keys,'generate')
        files=[keys/f'{key}.key.{ext}' for key in ['primary','secondary'] for ext in ['prv','pub']]
        if all(p.exists() and (os_name!='nt' or b'\x1a' not in p.read_bytes()) for p in files):chosen=keys;break
    if chosen is None:raise RuntimeError('No Windows-readable fresh signing state; failed attempts retained.')
    prefix=chosen.name+'/'
    params+=f'ppkfile={prefix}primary.key.pub\nspkfile={prefix}secondary.key.pub\npskfile={prefix}primary.key.prv\nsskfile={prefix}secondary.key.prv\n'
    plain='partition {id=0x01,type=bootloader,file=plm.elf}\npartition {id=0x02,type=pldata,file=design.rcdo}'
    signed=plain.replace('type=bootloader,','type=bootloader,authentication=hss-shake256,')
    (out/'signed.bif').write_text(bif(signed,params))
    bootgen(['-image','signed.bif','-o','signed.pdi','-w'],out,'signed')
    # Keys are fresh local diagnostic files, excluded from publication.
    ivs={}
    for name in ['plm','pl']:
        ivs[name]=secrets.token_bytes(12)
        (out/(name+'.nky')).write_text(f'Device xcsu35p;\nKey 0 {bytes(32).hex()};\nIV 0 {ivs[name].hex()};\n')
    encrypted=plain.replace('file=plm.elf','encryption=aes,keysrc=efuse_red_key,dpacm_enable,aeskeyfile=plm.nky,blocks=4096(*),file=plm.elf').replace('file=design.rcdo','encryption=aes,dpacm_enable,aeskeyfile=pl.nky,blocks=4096(*),file=design.rcdo')
    (out/'rolling.bif').write_text(bif(encrypted))
    bootgen(['-image','rolling.bif','-o','rolling.pdi','-w'],out,'rolling')
    combo=encrypted.replace('type=bootloader,','type=bootloader,authentication=hss-shake256,')
    (out/'combo.bif').write_text(bif(combo,params))
    bootgen(['-image','combo.bif','-o','combo.pdi','-w'],out,'combo')
    # Functional independent verification. Do not call Bootgen -verify for HSS.
    sys.path.insert(0,str(ROOT/'scripts'))
    from pdi import verify_signed,header,parts,decrypt_chain
    s,_=verify_signed((out/'signed.pdi').read_bytes(),out)
    assert all(s[k] for k in ['spk_signature_valid','hash_block_signature_valid','boot_header_hash_valid'])
    bad=bytearray((out/'signed.pdi').read_bytes());bad[s['signature_offset']+32]^=1
    (out/'badsig.pdi').write_bytes(bad)
    negative,_=verify_signed(bytes(bad),out)
    assert not negative['hash_block_signature_valid']
    p=(out/'rolling.pdi').read_bytes();h=header(p);hb=p[0x340:0x3d0]
    a,b,_,_=parts(p,h,hb)
    # Bootgen derives the next partition's initial IV by incrementing the last
    # byte of the first partition IV, as verified in the retained image flow.
    pa,ra=decrypt_chain(a,bytes(32),ivs['plm'])
    pl_iv=ivs['plm'][:-1]+bytes([(ivs['plm'][-1]+1)&255])
    pb,rb=decrypt_chain(b,bytes(32),pl_iv)
    pp=(out/'plain.pdi').read_bytes();ph=header(pp);plain_a,plain_b,_,_=parts(pp,ph,pp[0x340:0x3d0])
    assert pa==plain_a and pb==plain_b
    cs,(_,_,_,_,ca,cb)=verify_signed((out/'combo.pdi').read_bytes(),out)
    assert all(cs[k] for k in ['spk_signature_valid','hash_block_signature_valid','boot_header_hash_valid'])
    combo_a,_=decrypt_chain(ca,bytes(32),ivs['plm'])
    combo_b,_=decrypt_chain(cb,bytes(32),pl_iv)
    assert combo_a==plain_a and combo_b==plain_b
    report={'signed':s,'combo':cs,'tampered_signature_rejected':True,'rolling_plm_blocks':len(ra),'rolling_pl_blocks':len(rb),'plaintext_matches':True,'hardware_tested':False,'scope':'Public-zero diagnostic root; no device writes, no secrecy or production trust-policy claim. Never roll back signing state.'}
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    manifest(out,'Fresh offline signed and encrypted PDIs; private state remains local and must never be rolled back.')
    print('BOOT_PACKAGING_PASS',out)

import os
os_name=os.name
