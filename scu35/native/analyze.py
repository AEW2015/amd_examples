"""Validate native PMC captures and measure matching resident Python operations."""
from pathlib import Path
import argparse,collections,csv,hashlib,html,json,os,re,statistics,struct,sys,time
from datetime import datetime,timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
HERE=Path(__file__).resolve().parent
ALGORITHMS={1:'SHA3-256',2:'SHAKE-256',3:'AES-GCM-ENC',4:'AES-GCM-DEC',5:'AES-GCM-ENC-STREAM'}
SIZES={1:(16,256,2048,8192,65536,1048576),2:(16,256,2048,8192,65536,1048576),3:(16,256,2048,8192),4:(16,256,2048,8192),5:(65536,1048576)}
KEY=bytes(range(32))
PQ_CASES=('valid','bad_signature','bad_message','bad_key')
def pq_vectors():
 sys.path.insert(0,str(HERE.parent/'host'))
 import hss_ref
 vectors=hss_ref.load_vectors(HERE/'inputs/hss.c')
 frozen=json.loads((HERE/'inputs/pq_vectors.json').read_text())
 for name,v in vectors.items():
  for field in ('message','signature','public_key'):
   if bytes.fromhex(frozen[name][field])!=v[field]:raise ValueError('Frozen public vectors differ from pinned vendor source')
 return vectors,hss_ref
def pq_input(kind,case):
 vectors,ref=pq_vectors();v=vectors['Lms' if kind==6 else 'Hss']
 message,signature,key=v['message'],v['signature'],v['public_key']
 def flip(data,i):return data[:i]+bytes([data[i]^1])+data[i+1:]
 if case==1:signature=flip(signature,32)
 if case==2:message=flip(message,0)
 if case==3:key=flip(key,len(key)-1)
 return ref,(ref.verify_lms if kind==6 else ref.verify_hss),message,signature,key
def reference_pq(kind,case):
 ref,verify,msg,sig,key=pq_input(kind,case);original=ref._h;calls=0
 def counted(data):
  nonlocal calls
  calls+=1;return original(data)
 ref._h=counted
 try:accepted=verify(msg,sig,key)
 finally:ref._h=original
 if accepted!=(case==0):raise ValueError('Python PQ decision disagrees')
 return calls
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def words(data):
 if not re.fullmatch('[a-fA-F0-9]+',data) or len(data)%8:raise ValueError('Malformed AXI words')
 return [int(data[i:i+8],16) for i in range(len(data)-8,-1,-8)]
def packed(values):return b''.join(struct.pack('<I',v) for v in values)
def payload(n):
 chunk=bytes(i%251+1 for i in range(min(n,8192)))
 return (chunk*((n+len(chunk)-1)//len(chunk)))[:n]
def digest(kind,data):return hashlib.sha3_256(data).digest() if kind==1 else hashlib.shake_256(data).digest(32)
def validate(path):
 path=Path(path).resolve();text=path.read_text();rows={};cipher={};clocks=[];clock_ids=set()
 pq={};guards={};kats={};uploads=set();expected_calls={}
 expected={(kind,n,s) for kind,sizes in SIZES.items() for n in sizes for s in range(3)}
 if 'TEST_ERROR' in text or 'FAILED_RPC' in text:raise ValueError('Firmware/transport failure')
 if not re.search(r'^SUITE_PASS=YES$',text,re.M) or not re.search(r'^RESTORED DONE=1 ERROR=(?:0x)?0+\s*$',text,re.M):raise ValueError('Incomplete suite or recovery')
 if not re.search(r'^PROGRAM DONE=1 ERROR=(?:0x)?0+\s*$',text,re.M):raise ValueError('Missing clean programming status')
 controls={}
 for line in text.splitlines():
  m=re.fullmatch(r'SHAKE_KAT bytes=(\d+) data=([a-fA-F0-9]+)',line)
  if m:
   n=int(m[1]);w=words(m[2])
   if n in kats or len(w)!=32 or w[0]!=0x5153484b or w[2]!=n or not w[1]:raise ValueError('Invalid native SHAKE KAT')
   data=bytes(i%251+1 for i in range(n))
   if packed(w[6:14])!=hashlib.shake_256(data).digest(32):raise ValueError('Native padded SHAKE KAT mismatch')
   kats[n]=True
  m=re.fullmatch(r'PQ_VECTOR kind=([67]) UPLOAD_VERIFIED=YES',line)
  if m:
   k=int(m[1])
   if k in uploads:raise ValueError('Duplicate PQ upload')
   uploads.add(k)
  m=re.fullmatch(r'(PQ|PQ_GUARD) kind=([67]) case=(\d+)(?: sample=(\d+))? data=([a-fA-F0-9]+)',line)
  if m:
   category,k,c,s,data=m.groups();k=int(k);c=int(c);w=words(data)
   if len(w)!=32 or w[0]!=0x50514231 or w[2]!=56 or w[4]!=c or w[8:10]!=[15,10] or w[10]!=(k==7) or w[11:13]!=([4460,56] if k==6 else [4464,60]):raise ValueError('Invalid native PQ metadata')
   if category=='PQ':
    if c not in range(4) or s is None or int(s) not in range(3) or (k,c,int(s)) in pq or w[3]!=20:raise ValueError('Invalid/duplicate PQ batch')
    if (k,c) not in expected_calls:expected_calls[k,c]=reference_pq(k,c)
    if w[5]!=(0 if c==0 else 1) or not w[1] or not 0<w[7]<=w[1] or w[6]!=20*expected_calls[k,c]:raise ValueError('PQ verification/profiling mismatch')
    pq[k,c,int(s)]={'kind':k,'algorithm':'LMS-SHAKE256' if k==6 else 'HSS-SHAKE256','case':PQ_CASES[c],'sample':int(s),'repeats':20,'cycles':w[1],'hash_cycles':w[7],'hash_calls':w[6],'status':w[5]}
   else:
    if c not in (4,5,6) or s is not None or (k,c) in guards or w[3]!=1 or w[5]!=2 or w[6] or w[7]:raise ValueError('Malformed-input guard failed')
    guards[k,c]=True
  m=re.fullmatch(r'(RAM_CONTROL|AES_KAT) data=([a-fA-F0-9]+)',line)
  if m:
   if m[1] in controls:raise ValueError('Duplicate control')
   controls[m[1]]=words(m[2])
  m=re.fullmatch(r'CLOCK sample=(\d+) data=([a-fA-F0-9]+)',line)
  if m:
   w=words(m[2]);s=int(m[1])
   if len(w)!=32 or w[0]!=0x434c4f4b or s in clock_ids:raise ValueError('Invalid clock record')
   cycles=w[1]+(w[2]<<32);reference=w[3]+(w[4]<<32)
   if not reference or w[7]-w[6]!=100 or w[8]<101:raise ValueError('Invalid calibration span')
   hz=cycles/reference*100000000
   if not 100000000<hz<500000000:raise ValueError('Unexpected cycle rate')
   clocks.append(hz);clock_ids.add(s)
  m=re.fullmatch(r'FAST kind=(\d+) bytes=(\d+) repeats=(\d+) sample=(\d+) data=([a-fA-F0-9]+)',line)
  if m:
   k,n,reps,s=map(int,m.group(1,2,3,4));w=words(m[5]);key=(k,n,s)
   if key not in expected or key in rows or len(w)!=32:raise ValueError('Unknown/duplicate timing row')
   if w[0]!=0x46415354 or w[2:4]!=[n,reps] or w[15]!=k or w[4] or w[5] or not w[1]:raise ValueError('Failed native result')
   if reps!=(1000 if n<=8192 else 200):raise ValueError('Unexpected repetitions')
   if k<3:
    if packed(w[6:14])!=digest(k,payload(n)):raise ValueError('Native/Python digest mismatch')
   elif k!=5 and w[14]!=0x40:raise ValueError('AES bad-tag rejection failed')
   rows[key]={'kind':k,'algorithm':ALGORITHMS[k],'size_bytes':n,'sample':s,'repeats':reps,'cycles':w[1],'words':w}
  m=re.fullmatch(r'CIPHER kind=(\d+) bytes=(\d+) sample=(\d+) offset=(\d+) data=([a-fA-F0-9]+)',line)
  if m:
   k,n,s,offset=map(int,m.group(1,2,3,4));key=(k,n,s,offset)
   if (k,n,s) not in expected or k<3 or key in cipher or offset%512 or offset>=min(8192,n):raise ValueError('Invalid cipher fragment')
   data=packed(words(m[5]))
   if len(data)!=min(512,min(8192,n)-offset):raise ValueError('Incorrect cipher fragment size')
   cipher[key]=data
 if clock_ids!=set(range(5)) or set(rows)!=expected:raise ValueError('Incomplete timing/calibration matrix')
 if set(pq)!={(k,c,s) for k in (6,7) for c in range(4) for s in range(3)} or set(guards)!={(k,c) for k in (6,7) for c in (4,5,6)} or uploads!={6,7}:raise ValueError('Incomplete native PQ verification matrix')
 if set(kats)!={0,1,3,4,55,86,110,136,137,4278}:raise ValueError('Incomplete native SHAKE KATs')
 if max(clocks)/min(clocks)>1.02:raise ValueError('Unstable clock calibration')
 if set(controls)!={'RAM_CONTROL','AES_KAT'}:raise ValueError('Missing controls')
 w=controls['RAM_CONTROL']
 if w[0]!=0x42454e43 or w[2:4]!=[8192,10] or w[5]:raise ValueError('RAM DMA control failed')
 w=controls['AES_KAT']
 if w[0]!=0x41455354 or w[3]!=7 or w[4] or w[5]:raise ValueError('AES KAT failed')
 expected_cipher={(k,n,s,offset) for k,n,s in expected if k>=3 for offset in range(0,min(8192,n),512)}
 if set(cipher)!=expected_cipher:raise ValueError('Incomplete ciphertext readback')
 for (k,n,s),r in rows.items():
  if k>=3:
   w=r['words'];iv=packed(w[10:14])[:12];tag=packed(w[6:10])
   actual=b''.join(cipher[(k,n,s,o)] for o in range(0,min(8192,n),512))
   expected=AESGCM(KEY).encrypt(iv,payload(n),None)
   if expected[-16:]!=tag or expected[:-16][-len(actual):]!=actual:raise ValueError('Native/Python ciphertext or tag mismatch')
   if k!=5 and AESGCM(KEY).decrypt(iv,actual+tag,None)!=payload(n):raise ValueError('Python decrypt mismatch')
 hz=statistics.median(clocks)
 for r in rows.values():
  r['mean_us']=r['cycles']/hz/r['repeats']*1e6
  r['MBps']=r['size_bytes']*r['repeats']/r['cycles']*hz/1e6
 for r in pq.values():
  r['mean_us']=r['cycles']/hz/r['repeats']*1e6
  r['hash_path_mean_us']=r['hash_cycles']/hz/r['repeats']*1e6
  r['software_remainder_mean_us']=r['mean_us']-r['hash_path_mean_us']
  r['hash_calls_per_verification']=r['hash_calls']//r['repeats']
 return {'status':'VALIDATED','source':str(path),'capture_sha256':sha(path),'clock_hz':hz,'clock_samples_hz':clocks,'clock_reference':'Nominal 100 MHz PL reference; not frequency-metrology calibration','rows':list(rows.values()),'pq_rows':list(pq.values()),'native_pq_batches':24,'pq_malformed_guards':6,'padded_shake_kats':10,'verified_hash_batches':36,'verified_aes_batches':24,'verified_aes_stream_batches':6,'verified_same_key_negative_tests':24,'stock_restore':'DONE=1 ERROR=0'}
def python_measure(kind,n,reps):
 data=payload(n);aes=AESGCM(KEY);iv=os.urandom(12);ct=aes.encrypt(iv,data,None)
 if kind==1:fn=lambda:hashlib.sha3_256(data).digest()
 elif kind==2:fn=lambda:hashlib.shake_256(data).digest(32)
 elif kind in (3,5):
  prefix=os.urandom(8);nonces=iter(prefix+i.to_bytes(4,'big') for i in range(reps*3+5))
  fn=lambda:aes.encrypt(next(nonces),data,None)
 else:fn=lambda:aes.decrypt(iv,ct,None)
 for _ in range(5):fn()
 elapsed=[]
 for _ in range(3):
  start=time.perf_counter_ns()
  for _ in range(reps):value=fn()
  elapsed.append(time.perf_counter_ns()-start)
 if kind<3:assert value==digest(kind,data)
 elif kind==4:assert value==data
 return [{'mean_us':t/reps/1000,'MBps':n*reps/t*1000,'batch_ns':t,'repeats':reps} for t in elapsed]
def add_metrics(report):
 for r in report['comparisons']:
  for prefix in ('native','python'):
   r[prefix+'_payload_Gbps']=r[prefix+'_median_MBps']*.008
   r[prefix+'_messages_per_second']=1e6/r[prefix+'_median_us']
  # An accounting estimate, not an AXI bus-counter measurement. Excludes IV,
  # tag, register traffic, protocol overhead, caching and input preparation.
  r['native_bulk_DMA_traffic_MBps']=r['native_median_MBps']*(1 if r['kind']<3 else 2)
 report['metric_definitions']={
  'payload_throughput':'Logical input bytes / timed batch duration; decimal MB/s.',
  'payload_bandwidth':'The same payload rate expressed in Gb/s: MB/s * 0.008. Not a separate bus measurement.',
  'latency':'Median of three batch-average per-message times. Warm resident buffers; not individually sampled request/response latency or p95.',
  'bulk_DMA_traffic':'Derived minimum bulk traffic: one input read for hash; input read + output write for AES. IV/tag, register traffic and AXI overhead excluded.',
  'bandwidth_ceiling':'Not measured. No physical-link maximum, bus utilization, host-to-board or HyperRAM bandwidth is claimed.'}
 return report
def pq_python_measure(kind,case,repeats=50):
 _,verify,msg,sig,key=pq_input(kind,case)
 for _ in range(5):
  if verify(msg,sig,key)!=(case==0):raise ValueError('Python PQ warm-up failed')
 batches=[]
 for _ in range(3):
  start=time.perf_counter_ns()
  for _ in range(repeats):accepted=verify(msg,sig,key)
  elapsed=time.perf_counter_ns()-start
  if accepted!=(case==0):raise ValueError('Python PQ verification failed')
  batches.append({'batch_ns':elapsed,'repeats':repeats,'mean_us':elapsed/repeats/1000})
 return batches
def run(capture,out=None):
 native=validate(capture);out=Path(out or HERE/'report.html')
 attempt=Path(capture).resolve().parent
 meta=json.loads((attempt/'build_meta.json').read_text())
 if sha(attempt/'test.pdi')!=meta['pdi_sha256'] or sha(attempt/'plm.elf')!=meta['elf_sha256']:raise ValueError('Captured image identity differs')
 for name in ('pq_vectors.json','pq_upload.tcl'):
  if sha(attempt/name)!=meta['inputs']['inputs/'+name] or sha(HERE/'inputs'/name)!=meta['inputs']['inputs/'+name]:raise ValueError('PQ inputs differ from captured image contract')
 grouped=collections.defaultdict(list)
 for r in native['rows']:grouped[(r['kind'],r['size_bytes'])].append(r)
 summaries=[]
 baseline_path=HERE.parent/'evidence/timer/report.json'
 baseline=json.loads(baseline_path.read_text()) if baseline_path.exists() else {}
 for (k,n),batch in sorted(grouped.items()):
  py=python_measure(k,n,1000 if n<=8192 else 200)
  old=next((r for r in baseline.get('comparisons',[]) if r['algorithm']==ALGORITHMS[k] and r['size_bytes']==n and r['case']=='valid'),None)
  summaries.append({'algorithm':ALGORITHMS[k],'kind':k,'size_bytes':n,'native_median_MBps':statistics.median(r['MBps'] for r in batch),'native_best_MBps':max(r['MBps'] for r in batch),'native_median_us':statistics.median(r['mean_us'] for r in batch),'python_median_MBps':statistics.median(r['MBps'] for r in py),'python_best_MBps':max(r['MBps'] for r in py),'python_median_us':statistics.median(r['mean_us'] for r in py),'python_batches':py,'previous_soft_cpu_us':old['scu35_operation_mean_us'] if old else None,'results_match':True})
 pq_summaries=[]
 for kind in (6,7):
  for case,name in enumerate(PQ_CASES):
   batch=[r for r in native['pq_rows'] if r['kind']==kind and r['case']==name]
   py=pq_python_measure(kind,case)
   median=statistics.median(r['mean_us'] for r in batch)
   python_median=statistics.median(r['mean_us'] for r in py)
   algo='LMS-SHAKE256' if kind==6 else 'HSS-SHAKE256'
   old=next((r for r in baseline.get('comparisons',[]) if r['algorithm']==algo and r['case']==name),None)
   pq_summaries.append({'algorithm':algo,'kind':kind,'case':name,'message_bytes':56,'signature_bytes':4460 if kind==6 else 4464,'native_median_us':median,'native_best_us':min(r['mean_us'] for r in batch),'native_verifications_per_s':1e6/median,'python_median_us':python_median,'python_verifications_per_s':1e6/python_median,'python_batches':py,'hash_calls_per_verification':batch[0]['hash_calls_per_verification'],'native_hash_path_median_us':statistics.median(r['hash_path_mean_us'] for r in batch),'native_software_remainder_median_us':statistics.median(r['software_remainder_mean_us'] for r in batch),'previous_soft_cpu_us':old['scu35_operation_mean_us'] if old else None,'results_match':True,'accepted':case==0})
 report={'measured_utc':datetime.now(timezone.utc).isoformat(),'python_executable':sys.executable,'pdi_sha256':meta['pdi_sha256'],'hardware':native,'comparisons':summaries,'pq_comparisons':pq_summaries,
 'scope':['Fastest observed resident-buffer mode, not a claim of the silicon maximum. Native PMC processor; clock registers are not changed.',
 'Preload, volatile key writes, warm-up, validation and JTAG are outside timing. Per-message engine setup, DMA completion/status/progress checks and nonce updates remain inside. Hash digest readback and validation occur once after each timed batch; Python hash calls return a digest on every call.',
 'Three timed batches per cell; best and median shown. Hashes up to 1 MiB stream repeated 8 KiB resident chunks; Python hashes the identical preallocated logical message.',
 'AES uses public key bytes 00..1f and fresh nonce per encryption. ENC/DEC are 16..8192-byte messages with full ciphertext/tag checks and bad-tag rejection. ENC-STREAM spans 64 KiB/1 MiB with repeated resident 8 KiB chunks; the final 8 KiB ciphertext and full-message GCM tag match Python. Stream decryption is not claimed.',
 'Python hash/AES call optimized native libraries. Previous soft-CPU data use a different setup/API path and a dated capture, not equal CPU or isolated-engine measurements.',
 'LMS/HSS verification now runs on native PMC using an independent port of the fixed SHAKE reference and hardened SHAKE. Only the AMD n=32/h=5/w=2 public vectors and one-level HSS are benchmarked; this is not a qualified production verifier or signed-PDI boot-enforcement test.',
 'PQ primary time includes parsing, byte encoding, software padding, all SHAKE calls/digest reads, tree/control logic and profiling. SHAKE subtotal includes engine setup, DMA completion and digest reads; padding/input copying are in the software remainder. It is not an isolated engine profile.',
 'RNG and PUF remain in the original functional/latency notebook.']}
 add_metrics(report)
 out.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
 columns=[k for k in summaries[0] if k!='python_batches']
 with out.with_suffix('.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(summaries)
 with out.with_name('pq.csv').open('w',newline='') as f:
  columns=[k for k in pq_summaries[0] if k!='python_batches']
  w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(pq_summaries)
 render(report,out);print(out);return report
def render(report,out):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained')
 for ax,algo in zip(axes.flat,list(ALGORITHMS.values())[:4]):
  rows=[r for r in report['comparisons'] if r['algorithm']==algo or (algo=='AES-GCM-ENC' and r['kind']==5)]
  ax.plot([r['size_bytes'] for r in rows],[r['native_median_MBps'] for r in rows],'o-',label='Native PMC median')
  ax.plot([r['size_bytes'] for r in rows],[r['python_median_MBps'] for r in rows],'s-',label='Python median')
  ax.set(title=algo,xlabel='Logical message bytes',ylabel='MB/s (decimal)',xscale='log');ax.grid(alpha=.25);ax.legend()
 fig.savefig(out.with_suffix('.svg'));fig.savefig(out.with_suffix('.png'));plt.close(fig)
 fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained')
 for ax,algo in zip(axes.flat,list(ALGORITHMS.values())[:4]):
  rows=[r for r in report['comparisons'] if r['algorithm']==algo or (algo=='AES-GCM-ENC' and r['kind']==5)]
  ax.plot([r['size_bytes'] for r in rows],[r['native_median_us'] for r in rows],'o-',label='Native PMC')
  ax.plot([r['size_bytes'] for r in rows],[r['python_median_us'] for r in rows],'s-',label='Python')
  ax.set(title=algo,xlabel='Logical message bytes',ylabel='Batch-average message time (us)',xscale='log',yscale='log');ax.grid(alpha=.25);ax.legend()
 fig.savefig(out.with_name('latency.svg'));fig.savefig(out.with_name('latency.png'));plt.close(fig)
 pq=report['pq_comparisons'];fig,axes=plt.subplots(1,2,figsize=(13,6),layout='constrained')
 y=list(range(len(pq)));labels=[r['algorithm']+' / '+r['case'] for r in pq]
 axes[0].barh([i-.2 for i in y],[r['native_median_us']/1000 for r in pq],height=.35,label='Native PMC')
 axes[0].barh([i+.2 for i in y],[r['python_median_us']/1000 for r in pq],height=.35,label='Python')
 axes[0].set_yticks(y,labels);axes[0].set(xlabel='Verification time (ms)',title='Valid and modified signatures');axes[0].invert_yaxis();axes[0].legend()
 axes[1].barh(y,[r['native_hash_path_median_us']/1000 for r in pq],label='SHAKE call path')
 axes[1].barh(y,[r['native_software_remainder_median_us']/1000 for r in pq],left=[r['native_hash_path_median_us']/1000 for r in pq],label='Other software / padding')
 axes[1].set_yticks(y,[r['case'] for r in pq]);axes[1].set(xlabel='Native PMC time (ms)',title='Measured SHAKE subtotal and remainder');axes[1].invert_yaxis();axes[1].legend()
 fig.savefig(out.with_name('pq.svg'));fig.savefig(out.with_name('pq.png'));plt.close(fig)
 heads=['Algorithm','Bytes','PMC median MB/s','PMC best MB/s','Python median MB/s','PMC median us','Previous soft CPU us','Check']
 cells=[]
 for r in report['comparisons']:
  cells.append([r['algorithm'],r['size_bytes'],f"{r['native_median_MBps']:.2f}",f"{r['native_best_MBps']:.2f}",f"{r['python_median_MBps']:.2f}",f"{r['native_median_us']:.3f}",f"{r['previous_soft_cpu_us']:.3f}" if r['previous_soft_cpu_us'] is not None else 'Different size','MATCH'])
 def row(values,tag='td'):return '<tr>'+''.join(f'<{tag}>{html.escape(str(v))}</{tag}>' for v in values)+'</tr>'
 metric_heads=['Algorithm','Bytes','PMC payload MB/s','PMC payload Gb/s','PMC message us','Python message us','Derived bulk DMA MB/s']
 metric_rows=[[r['algorithm'],r['size_bytes'],f"{r['native_median_MBps']:.2f}",f"{r['native_payload_Gbps']:.3f}",f"{r['native_median_us']:.3f}",f"{r['python_median_us']:.3f}",f"{r['native_bulk_DMA_traffic_MBps']:.2f}"] for r in report['comparisons']]
 definitions=''.join('<li><b>'+html.escape(k)+':</b> '+html.escape(v)+'</li>' for k,v in report['metric_definitions'].items())
 content=f'''<!doctype html><html><meta charset="utf-8"><title>SCU35 bandwidth, throughput and latency</title><style>body{{font:16px system-ui;max-width:1200px;margin:40px auto;padding:0 20px;background:#f5f8fa;color:#143137}}table{{border-collapse:collapse;background:white;width:100%}}td,th{{border-bottom:1px solid #ccd;padding:10px;text-align:right}}td:first-child,th:first-child{{text-align:left}}img{{width:100%;background:white}}code{{overflow-wrap:anywhere}}</style><h1>SCU35: bandwidth, throughput and latency</h1><p>Validated resident-buffer DMA/crypto batches. Best is the fastest of three measured batches; median is shown alongside it.</p><p>Measured: {report['measured_utc']}<br>PMC cycle rate: {report['hardware']['clock_hz']/1e6:.3f} MHz against nominal 100 MHz PL reference.<br>Hardware: VALIDATED; stock recovery: {report['hardware']['stock_restore']}</p><h2>Metric definitions</h2><ul>{definitions}</ul><h2>Payload throughput</h2><img src="{out.with_suffix('.svg').name}" alt="Measured throughput by message size"><h2>Message processing time</h2><img src="latency.svg" alt="Batch-average message time by message size"><h2>Bandwidth and latency comparison</h2><table>{row(metric_heads,'th')}{''.join(row(r) for r in metric_rows)}</table><h2>All measured throughput cases</h2><table>{row(heads,'th')}{''.join(row(r) for r in cells)}</table><h2>Timing boundaries</h2><ul>{''.join('<li>'+html.escape(s)+'</li>' for s in report['scope'])}</ul><p>Capture: <code>{html.escape(report['hardware']['source'])}</code><br>Capture SHA256: <code>{report['hardware']['capture_sha256']}</code></p></html>'''
 pq_heads=['Method','Case','Native us','Native verifies/s','Python us','Previous soft CPU us','SHAKE calls','Decision']
 pq_rows=[[r['algorithm'],r['case'],f"{r['native_median_us']:.2f}",f"{r['native_verifications_per_s']:.1f}",f"{r['python_median_us']:.2f}",f"{r['previous_soft_cpu_us']:.2f}" if r['previous_soft_cpu_us'] is not None else 'Unavailable',r['hash_calls_per_verification'],'ACCEPT' if r['accepted'] else 'REJECT'] for r in pq]
 pq_html='<h2>Native post-quantum verification</h2><p>Same pinned AMD SHAKE vectors: n=32, tree height 5, Winternitz 2; one-level HSS. 24 timed batches, six malformed-input guards and ten SHAKE padding known-answer tests. Runtime verification is not secure-boot enforcement.</p><img src="pq.svg" alt="Native LMS and HSS latency and timing breakdown"><table>'+row(pq_heads,'th')+''.join(row(r) for r in pq_rows)+'</table>'
 content=content.replace('<h2>Timing boundaries</h2>',pq_html+'<h2>Timing boundaries</h2>')
 out.write_text(content,encoding='utf-8')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);p.add_argument('--out',type=Path)
 a=p.parse_args();run(a.capture,a.out)
