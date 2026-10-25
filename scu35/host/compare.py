"""Measure Python reference calls and validate/compare a fresh SCU35 capture."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import ssl
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
import cryptography
from hss_ref import load_vectors,verify_lms,verify_hss
from dashboard import write_report

HERE=Path(__file__).resolve().parent
SEC=HERE.parent
VENDOR=HERE/'inputs/hss.c' if (HERE/'inputs/hss.c').exists() else SEC/'work/online/hss.c'
SIZES=(16,64,256,1024,2048)
FAST=('SHA3-256','SHAKE-256','AES-GCM-ENC','AES-GCM-DEC')
PQ=('LMS-SHAKE256','HSS-SHAKE256')
CASES=('valid','bad_signature','bad_message','bad_key')
KEY=bytes(range(32))  # Public diagnostic key; never obtained from eFUSE/PUF.


def payload(size):return bytes((i%251)+1 for i in range(size))
def digest(algo,data):
    return hashlib.sha3_256(data).digest() if algo=='SHA3-256' else hashlib.shake_256(data).digest(32)
def changed(data,index):
    value=bytearray(data);value[index]^=1;return bytes(value)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_capture(path, build_id=None):
    """Reject incomplete, duplicate, wrong-build or semantically failed captures."""
    result={'rows':[],'hashes':{},'aes':{},'vectors':{},'features':{},'random':{},'source':str(path),
            'capture_sha256':sha(path)}
    meta=None;done=False;seen=set();neg=set();cleared=set();regen=set();roundtrip=False
    for raw in Path(path).read_text(encoding='utf-8-sig',errors='replace').splitlines():
        # UART reset can emit a NUL before the first complete application record.
        match=re.search(r'(?:^|[\s\x00])(CMP_[A-Z_]+),',raw)
        if not match:continue
        if done:raise ValueError('A record occurs after CMP_DONE')
        fields=raw[match.start(1):].strip().split(',');kind=fields[0]
        if meta is None and kind!='CMP_META':raise ValueError('Data record before metadata')
        if kind=='CMP_META':
            if meta or len(fields)!=7:raise ValueError('Duplicate or malformed metadata')
            _,version,hz,fast,pq,ident,overhead=fields
            if (int(version),int(hz),int(fast),int(pq))!=(2,100000000,20,10):raise ValueError('Unknown benchmark contract')
            if build_id is not None and ident!=build_id:raise ValueError('Capture came from a different benchmark build')
            if not re.fullmatch('[0-9a-f]{16}',ident) or int(overhead)<0:raise ValueError('Invalid build/timer metadata')
            meta={'version':2,'counter_hz':int(hz),'build_id':ident,'timer_read_cycles':int(overhead)}
        elif kind=='CMP_ROW':
            if len(fields)!=12:raise ValueError('Malformed timing row')
            _,algo,case,*numbers=fields
            size,n,copy,setup,api,check,lo,hi,status=map(int,numbers)
            key=(algo,case,size)
            if key in seen:raise ValueError('Duplicate timing row')
            seen.add(key)
            if algo in FAST:
                if case!='valid' or size not in SIZES or n!=20 or status:raise ValueError('Invalid fast result')
            elif algo in PQ:
                if case not in CASES or size!=56 or n!=10 or status!=(0 if case=='valid' else 0xAB):raise ValueError('Invalid signature result')
            elif algo in ('TRNG-HRNG','TRNG-DRNG','TRNG-PTRNG'):
                if case!='generate' or size!=32 or n!=20 or status:raise ValueError('Invalid RNG result')
            else:raise ValueError('Unknown algorithm '+algo)
            if min(copy,setup,api,check,lo,hi)<0 or api==0 or not lo*n<=api<=hi*n:raise ValueError('Invalid timing interval')
            result['rows'].append({'algorithm':algo,'case':case,'size_bytes':size,'repeats':n,
                'copy_cycles':copy,'setup_cycles':setup,'api_cycles':api,'check_cycles':check,
                'scu35_api_mean_us':api/n/100,'scu35_full_mean_us':(copy+setup+api+check)/n/100,
                'scu35_operation_mean_us':(api+(setup if algo in FAST else 0))/n/100,
                'scu35_min_us':lo/100,'scu35_max_us':hi/100,'status':status})
        elif kind=='CMP_HASH':
            _,algo,size,value=fields;key=(algo,int(size))
            if algo not in FAST[:2] or int(size) not in SIZES:raise ValueError('Unknown hash vector')
            if key in result['hashes']:raise ValueError('Duplicate hash')
            actual=bytes.fromhex(value)
            if actual!=digest(algo,payload(int(size))):raise ValueError('PMC hash mismatch')
            result['hashes'][key]=value
        elif kind=='CMP_AES':
            _,size,iv,cipher,tag=fields;size=int(size)
            if size in result['aes']:raise ValueError('Duplicate AES vector')
            iv=bytes.fromhex(iv);cipher=bytes.fromhex(cipher);tag=bytes.fromhex(tag)
            if len(iv)!=12 or len(cipher)!=size or len(tag)!=16:raise ValueError('Malformed AES vector')
            aes=AESGCM(KEY)
            if aes.encrypt(iv,payload(size),None)!=cipher+tag:raise ValueError('SCU35/Python AES ciphertext/tag mismatch')
            if aes.decrypt(iv,cipher+tag,None)!=payload(size):raise ValueError('AES decrypt mismatch')
            try:aes.decrypt(iv,cipher+changed(tag,0),None)
            except InvalidTag:pass
            else:raise ValueError('Python accepted a bad GCM tag')
            result['aes'][size]={'iv':iv.hex(),'ciphertext':cipher.hex(),'tag':tag.hex()}
        elif kind=='CMP_NEG':
            _,algo,size,status=fields;size=int(size)
            if algo!='AES-GCM' or int(status)!=0x40 or size in neg:raise ValueError('Bad AES negative test')
            neg.add(size)
        elif kind=='CMP_VECTOR':
            _,algo,msglen,siglen,keylen,fingerprint=fields
            if algo not in PQ:raise ValueError('Unknown signature algorithm')
            if algo in result['vectors']:raise ValueError('Duplicate signature vector')
            vectors=load_vectors(VENDOR);v=vectors['Hss' if algo=='HSS-SHAKE256' else 'Lms']
            if (int(msglen),int(siglen),int(keylen))!=(len(v['message']),len(v['signature']),len(v['public_key'])):raise ValueError('Vector lengths differ')
            if bytes.fromhex(fingerprint)!=hashlib.sha3_256(v['public_key']).digest():raise ValueError('Public-key fingerprint differs')
            result['vectors'][algo]=fingerprint.lower()
        elif kind=='CMP_FEATURE':
            _,name,n,cycles,status=fields
            if name in result['features'] or int(status) or int(n)<=0 or int(cycles)<=0:raise ValueError('Failed/duplicate feature '+name)
            result['features'][name]={'repeats':int(n),'cycles':int(cycles),'mean_us':int(cycles)/int(n)/100,'status':int(status)}
        elif kind=='CMP_RANDOM':
            _,name,value=fields;data=bytes.fromhex(value)
            if name in result['random'] or len(data)!=32 or not any(data):raise ValueError('Invalid random-output smoke test')
            result['random'][name]=value
        elif kind=='CMP_PUF_CLEARED':
            _,r,status=fields;r=int(r)
            if r in cleared or int(status)!=0x46:raise ValueError('PUF key-clear evidence failed')
            cleared.add(r)
        elif kind=='CMP_PUF_REGEN':
            _,r,cycles,status=fields;r=int(r)
            if r in regen or int(status) or int(cycles)<=0:raise ValueError('PUF regeneration failed')
            regen.add(r)
        elif kind=='CMP_PUF_ROUNDTRIP':
            if roundtrip or fields[1:]!=['5','0']:raise ValueError('PUF round-trip failed')
            roundtrip=True
        elif kind=='CMP_DONE':
            if fields!=['CMP_DONE','0']:raise ValueError('Device benchmark failed')
            done=True
        else:raise ValueError('Unknown protocol record '+kind)
    rngs={'TRNG-HRNG','TRNG-DRNG','TRNG-PTRNG'}
    required={(a,'valid',s) for a in FAST for s in SIZES}|{(a,c,56) for a in PQ for c in CASES}|{(a,'generate',32) for a in rngs}
    if meta is None or not done or required!=seen:raise ValueError('Incomplete capture')
    if set(result['hashes'])!={(a,s) for a in FAST[:2] for s in SIZES}:raise ValueError('Incomplete hash outputs')
    if set(result['aes'])!=set(SIZES) or neg!=set(SIZES) or set(result['vectors'])!=set(PQ):raise ValueError('Incomplete output checks')
    required_features={r+'-SETUP' for r in rngs}|{'PUF-REGISTER','PUF-AES-ENC','PUF-KEY-CLEAR','PUF-REGENERATE','PUF-AES-DEC'}
    if set(result['features'])!=required_features or set(result['random'])!=rngs:raise ValueError('Incomplete lifecycle checks')
    if cleared!=set(range(5)) or regen!=set(range(5)) or not roundtrip:raise ValueError('Incomplete same-helper PUF regeneration checks')
    result['metadata']=meta
    result['status']='VALIDATED'
    return result


def measure(fn, samples, expected=None):
    for _ in range(5):fn()
    values=[];last=None
    for _ in range(samples):
        start=time.perf_counter_ns();last=fn();end=time.perf_counter_ns();values.append(end-start)
    if expected is not None and last!=expected:raise ValueError('Python reference returned an unexpected result')
    return {'python_mean_us':statistics.mean(values)/1000,'python_median_us':statistics.median(values)/1000,
            'python_min_us':min(values)/1000,'python_max_us':max(values)/1000,'python_samples':samples}


def python_bench(samples=1000,pq_samples=50):
    aes=AESGCM(KEY);rows=[]
    for algo in FAST:
        for size in SIZES:
            data=payload(size)
            if algo in FAST[:2]:
                fn=lambda a=algo,d=data:digest(a,d);expected=digest(algo,data)
            else:
                nonce=os.urandom(8);ivs=iter(nonce+i.to_bytes(4,'big') for i in range(samples+5))
                if algo=='AES-GCM-ENC':
                    fn=lambda d=data,it=ivs:aes.encrypt(next(it),d,None);expected=None
                else:
                    iv=os.urandom(12);cipher=aes.encrypt(iv,data,None)
                    fn=lambda d=cipher,n=iv:aes.decrypt(n,d,None);expected=data
            timing=measure(fn,samples,expected)
            rows.append({'algorithm':algo,'case':'valid','size_bytes':size,**timing,
                'results_match':True,'scope':'Python C-backed library call; input preparation and object/key setup excluded'})
    for kind,v in load_vectors(VENDOR).items():
        verify=verify_hss if kind=='Hss' else verify_lms
        for case in CASES:
            msg=v['message'];sig=v['signature'];key=v['public_key']
            if case=='bad_signature':sig=changed(sig,32)
            if case=='bad_message':msg=changed(msg,0)
            if case=='bad_key':key=changed(key,-1)
            fn=lambda m=msg,s=sig,k=key,f=verify:f(m,s,k)
            timing=measure(fn,pq_samples,case=='valid')
            rows.append({'algorithm':v['algorithm'],'case':case,'size_bytes':len(msg),**timing,
                'results_match':True,'scope':'Pure Python LMS/HSS control flow with hashlib SHAKE256 calls; fixed public vector'})
    rng=measure(lambda:os.urandom(32),samples)
    return rows,rng


def run(capture=None,out=None,samples=1000,pq_samples=50):
    if (HERE/'build_meta.json').exists():
        built=json.loads((HERE/'build_meta.json').read_text())
        if built.get('vendor_hss_sha256') and sha(VENDOR)!=built['vendor_hss_sha256']:
            raise ValueError('Public vectors changed relative to the compiled image')
    rows,host_rng=python_bench(samples,pq_samples)
    hardware=None
    if capture:
        ident=json.loads((HERE/'build_meta.json').read_text())['build_id']
        hardware=parse_capture(Path(capture),ident)
    lookup={(r['algorithm'],r['case'],r['size_bytes']):r for r in hardware['rows']} if hardware else {}
    for row in rows:
        board=lookup.get((row['algorithm'],row['case'],row['size_bytes']))
        if board:row.update(board)
        else:
            for key in ('scu35_api_mean_us','scu35_operation_mean_us','scu35_full_mean_us','scu35_min_us','scu35_max_us'):row[key]=None
            row['results_match']=None  # No hardware equality claim in a host-only report.
    special=[]
    if hardware:
        for name,info in hardware['features'].items():
            special.append({'feature':name,'hardware_us':round(info['mean_us'],3),'status':'PASS',
                'python_equivalent':'No physical equivalent' if name.startswith('PUF') else 'OS RNG setup is a different service',
                'note':'Volatile helper/key lifecycle; not export or security certification' if name.startswith('PUF') else 'Initialization + self-tests + instantiation'})
        for name,value in hardware['random'].items():
            b=lookup[(name,'generate',32)]
            special.append({'feature':name+' / 32 bytes','hardware_us':round(b['scu35_api_mean_us'],3),
                'status':'20 successful calls; output length/nonzero/change smoke checks',
                'python_equivalent':f"os.urandom(32): {host_rng['python_mean_us']:.3f} us mean",
                'note':'Different randomness service; outputs must not match. DRNG uses public test seed; no entropy qualification.'})
    from cryptography.hazmat.backends.openssl.backend import backend
    processor=platform.processor()
    if os.name=='nt':
        try:
            process=subprocess.run(['powershell','-NoProfile','-Command','(Get-CimInstance Win32_Processor).Name'],capture_output=True,text=True,timeout=8)
            if process.returncode==0 and process.stdout.strip():processor=process.stdout.strip()
        except subprocess.TimeoutExpired:pass
    report={'metadata':{'python_version':platform.python_version(),'python_build':sys.version,'python_executable':sys.executable,'platform':platform.platform(),
        'processor':processor,'backend':'hashlib / '+ssl.OPENSSL_VERSION+'; cryptography '+cryptography.__version__+' / '+backend.openssl_version_text(),
        'clock':vars(time.get_clock_info('perf_counter')),'measured_utc':datetime.now(timezone.utc).isoformat()},
        'hardware':{k:hardware[k] for k in ('source','capture_sha256','status')} if hardware else {'source':None,'status':'NOT CAPTURED'},
        'comparisons':rows,'special_features':special,'host_random':host_rng,
        'scope_notes':[
            'Host x86/ARM Python versus SCU35 MicroBlaze-V + hardened PMC services; these are system/API comparisons, not equal CPUs or isolated engine throughput.',
            'Hash/AES Python calls use optimized native libraries. LMS/HSS uses Python control flow with native hashlib SHAKE; do not interpret their ratios as equal implementation quality.',
            'SCU35 API includes driver/DMA and, for LMS/HSS, software verification. Full adds reported copy/setup/check stages; boot, UART, key loading and host transport are excluded.',
            'Primary operation comparison includes hash/AES initialization plus data API on SCU35 to align with Python per-call setup. LMS/HSS operation is the verification call on both sides. Data-only API and full path are separate secondary metrics.',
            'Python timings include function-call overhead and output allocation. Input construction, key object creation and correctness checks are outside its timed intervals.',
            'Board timer is nominally 100 MHz; overhead is reported without subtraction. Host perf_counter uses a different clock and scheduler.',
            'AES uses public bytes 00..1f in a volatile USER_KEY_0 register, 96-bit nonce, no AAD, 128-bit tag. Captured final ciphertext/tag for each size is independently verified in Python.',
            'PUF has no Python physical equivalent; keys/helpers are never exported. Randomness tests do not compare output bytes or certify entropy.',
            'Secure boot/encrypted boot are separate lifecycle tests. eFUSE programming/revocation/lockdown are excluded on the loaner.',
            'Capture SHA-256 and build ID bind files and help detect accidental mix-ups; they do not authenticate a capture against intentional editing.'
        ]}
    if hardware:
        report['hardware']['build_id']=hardware['metadata']['build_id']
        report['hardware']['capture_file_modified_utc']=datetime.fromtimestamp(Path(capture).stat().st_mtime,timezone.utc).isoformat()
        report['hardware']['timer_read_cycles']=hardware['metadata']['timer_read_cycles']
        report['verification']={
            'hashes':[{'algorithm':a,'size_bytes':s,'scu35_hex':h,'python_hex':digest(a,payload(s)).hex()}
                      for (a,s),h in hardware['hashes'].items()],
            'aes_public_test_vectors':hardware['aes'],
            'signature_public_key_fingerprints':hardware['vectors'],
            'PUF_key_clear_and_same_helper_decrypt_checks':5,
            'random_output_validation':'Length, nonzero and adjacent change; no byte equality or entropy certification'}
    out=Path(out or HERE/('report.html' if hardware else 'host_only.html'))
    out.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    write_report(report,out)
    print(out)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',type=Path)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--samples',type=int,default=1000)
    parser.add_argument('--pq-samples',type=int,default=50)
    args=parser.parse_args()
    if args.samples<10 or args.pq_samples<5:parser.error('Use at least 10 fast samples and 5 signature samples')
    run(args.capture,args.out,args.samples,args.pq_samples)
