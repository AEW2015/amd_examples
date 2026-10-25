"""Loopback live dashboard. Explicit hardware arguments; no persistent device writes."""
from pathlib import Path
from datetime import datetime, timezone
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse, hashlib, json, os, re, secrets, signal, statistics, subprocess, threading, time, uuid
import serial
from host import Client
from stream import batch

ROOT = Path(__file__).resolve().parent
MODES = {3: 'Plain UDP echo', 1: 'AES-GCM encrypted response', 2: 'AES-GCM authenticated round trip', 5: 'SHA3-256 + encrypted digest', 6: 'SHAKE-256 + encrypted digest'}

class NonceTracker:
 """Bounded check for this firmware's fixed boot prefix + increasing counter."""
 def __init__(self):self.prefix=None;self.counter=-1
 def __contains__(self, nonce):
  return self.prefix is not None and (nonce[:8]!=self.prefix or int.from_bytes(nonce[8:],'big')<=self.counter)
 def add(self, nonce):self.prefix=nonce[:8];self.counter=int.from_bytes(nonce[8:],'big')

class Dashboard:
 def __init__(self, a):
  self.a=a; self.guard=threading.Lock(); self.stop=threading.Event(); self.uart_stop=threading.Event(); self.ready=threading.Event(); self.recovered=threading.Event()
  self.config={'op':2,'size':1024,'running':True,'pace':'throughput'}; self.events=deque(maxlen=40); self.history=deque(maxlen=120); self.window=deque(maxlen=300);self.rtts=deque(maxlen=2000)
  self.state={'phase':'starting','checks':{},'count':0,'bytes':0,'errors':0,'latest':None,'started':time.time(),'recovery':'Not requested; live demo retains volatile configuration'}
  self.check_pending=True; self.finish_pending=False; self.serial=None; self.lease=None; self.client=None
  a.out.mkdir(parents=True,exist_ok=True)
  self.log=(a.out/'measurements.jsonl').open('a',encoding='utf-8')
 def event(self, message):
  with self.guard:self.events.appendleft({'time':time.strftime('%H:%M:%S'),'message':message})
 def snapshot(self):
  with self.guard:
   s={**self.state,'config':dict(self.config),'events':list(self.events),'history':list(self.history),'modes':MODES}
   rows=list(self.window); times=list(self.rtts)
   s['median_us']=statistics.median(times) if times else 0
   s['p95_us']=sorted(times)[min(len(times)-1,int(.95*len(times)))] if times else 0
   duration=time.monotonic()-rows[0]['at'] if len(rows)>1 else 0
   s['payload_Bps']=sum(x['input_bytes'] for x in rows[1:])/duration if duration else 0
   s['age_s']=time.time()-s.get('last_received',s['started'])
   return s
 def control(self, data):
  with self.guard:
   if 'op' in data:
    op=int(data['op'])
    if op not in MODES:raise ValueError('Unsupported operation')
    self.config['op']=op;self.window.clear();self.history.clear();self.rtts.clear()
   if 'size' in data:
    size=int(data['size'])
    if size not in (16,64,256,512,1024):raise ValueError('Unsupported size')
    self.config['size']=size;self.window.clear();self.history.clear();self.rtts.clear()
   if 'pace' in data:
    if data['pace'] not in ('presentation','throughput'):raise ValueError('Unsupported traffic mode')
    self.config['pace']=data['pace'];self.window.clear();self.history.clear();self.rtts.clear()
   if 'running' in data:self.config['running']=bool(data['running'])
   if data.get('check'):self.check_pending=True
   if data.get('restore'):self.finish_pending=True;self.config['running']=False
  self.event('Controls updated')
 def program(self, image, name):
  cmd=[str(self.a.vivado),'-mode','batch','-nolog','-nojournal','-source',str(ROOT.parent/'hw/program.tcl'),'-tclargs',self.a.server,self.a.cable,str(image.resolve()),'accept']
  path=self.a.out/name
  with path.open('w',encoding='utf-8') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,cwd=self.a.out,timeout=240)
  text=path.read_text(errors='replace')
  if r.returncode or 'PROGRAM_CHECK_PASS' not in text:raise RuntimeError('Programming/status failed: '+str(path))
 def capture_uart(self):
  with (self.a.out/'uart.txt').open('a',encoding='utf-8') as f:
   while not self.uart_stop.is_set():
    line=self.serial.readline().decode('utf-8',errors='replace')
    if line:
     f.write(line);f.flush()
     if 'E35_READY,' in line:self.ready.set()
     if 'CMP_DONE,0' in line:self.recovered.set()
 def acquire(self):
  if hashlib.sha256(self.a.restore.read_bytes()).hexdigest()!=self.a.restore_sha256:raise ValueError('Recovery SHA256 mismatch')
  self.lease=Path.home()/'codex/hardware-coordination'/('scu35-'+self.a.cable+'.lock')
  self.lease.parent.mkdir(parents=True,exist_ok=True); self.lease_id=str(uuid.uuid4())
  fd=os.open(self.lease,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
  with os.fdopen(fd,'w') as f:json.dump({'owner':'ethernet/dashboard','pid':os.getpid(),'lease_id':self.lease_id,'target':self.a.cable,'acquired_utc':datetime.now(timezone.utc).isoformat(),'task':'Live dashboard; retain board until Restore and stop or process shutdown'},f)
  self.owned=True
 def restore(self):
  self.event('Restoring known-good runtime image');self.state['phase']='restoring';self.recovered.clear()
  try:self.program(self.a.restore,'restore.log')
  except Exception:
   text=(self.a.out/'restore.log').read_text(errors='replace');m=re.search(r'^DEVICE_STATUS DONE=1 ERROR=(0x[0-9a-fA-F]+)',text,re.M)
   if not (m and int(m[1],16)==0x200000 and self.recovered.wait(60)):raise
   self.event('Baseline completed after SSS status; retrying identical recovery image')
   self.program(self.a.restore,'restore_retry.log')
  held=json.loads(self.lease.read_text())
  if held.get('lease_id')!=self.lease_id:raise RuntimeError('Lease ownership changed')
  self.lease.unlink();self.owned=False;self.state['recovery']='Verified DONE=1 and ERROR=0; lease released';self.state['phase']='restored';self.event('Recovery verified; hardware released')
 def checks(self):
  self.event('Running real tag-tamper and replay checks')
  payload=secrets.token_bytes(64);wire=self.client.request(2,payload)
  data,_,_=self.client.exchange(wire)
  if data!=payload:raise AssertionError('Round trip mismatch')
  self.client.exchange(wire,expected_status=3)
  bad=bytearray(self.client.request(2,payload));bad[-1]^=1
  self.client.exchange(bytes(bad),expected_status=2)
  with self.guard:self.state['checks']={'valid_roundtrip':'PASS','modified_tag':'REJECTED','replayed_packet':'REJECTED','time':time.strftime('%H:%M:%S')}
  self.event('Valid packet accepted · modified tag rejected · replay rejected')
 def work(self):
  armed=False
  try:
   self.acquire();self.serial=serial.Serial(self.a.serial,115200,timeout=.1)
   threading.Thread(target=self.capture_uart,daemon=True).start()
   self.state['phase']='programming';self.event('Loading volatile Ethernet design over exact SCU35 JTAG target');armed=True
   self.program(self.a.pdi,'program.log')
   if not self.ready.wait(30):raise TimeoutError('No E35_READY UART record')
   self.event('Waiting for host link and ARP reachability')
   reachable=False
   for attempt in range(3):
    cmd=['ping','-n' if os.name=='nt' else '-c','2',self.a.board]
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
    (self.a.out/f'ping_{attempt}.txt').write_text(result.stdout+'\n'+result.stderr)
    if result.returncode==0:reachable=True;break
    self.stop.wait(1)
   if not reachable:raise TimeoutError('Host link/ARP reachability failed before crypto requests')
   self.client=Client(self.a.board,self.a.bind,self.a.out/'peer_state.json');self.client.samples=deque(maxlen=1000);self.client.seen_nonces=NonceTracker()
   self.state['phase']='live';self.event('Board ready · physical Ethernet payload path online')
   last_chart=0
   while not self.stop.is_set() and not self.finish_pending:
    start=time.monotonic()
    if self.client.seq+128>=self.client.limit:
     nonces=self.client.seen_nonces;self.client.close()
     self.client=Client(self.a.board,self.a.bind,self.a.out/'peer_state.json');self.client.samples=deque(maxlen=1000);self.client.seen_nonces=nonces
    if self.check_pending:self.check_pending=False;self.checks()
    with self.guard:config=dict(self.config)
    if config['running']:
     data=secrets.token_bytes(config['size']);op=config['op'];fast=config['pace']=='throughput'
     # Two in flight passed short bursts but later timed out on this Lite path.
     # Continuous operation remains single-flight until a DMA MAC is validated.
     result=batch(self.client,op,data,count=64 if fast else 1,window=1)
     output,rec,raw=result['latest'];times=[r['rtt_us'] for r in result['records']]
     # Stats op does not update last_crypto_ticks: this aligns the device interval
     # to the completed primary request, outside its RTT measurement.
     _,probe,_=self.client.call(4,bytes(16));device_us=probe['previous_operation_ticks']/100
     record={**rec,'rtt_us':statistics.median(times),'device_us':device_us,'timestamp':time.time(),'at':time.monotonic(),'packets':result['packets'],'batch_input_bytes':result['input_bytes'],'batch_payload_Mbps':result['payload_Mbps'],'window':result['window'],'pace':config['pace']}
     self.log.write(json.dumps(record)+'\n');self.log.flush()
     with self.guard:
      self.window.append({**record,'input_bytes':result['input_bytes']});self.rtts.extend(times);self.state['count']+=result['packets'];self.state['bytes']+=result['input_bytes'];self.state['last_received']=time.time()
      self.state['latest']={**record,'mode':MODES[op],'plain_hex':data[:48].hex(),'wire_hex':raw[44:92].hex(),'result_hex':output[:48].hex(),'verified':True,'nonce_hex':raw[32:44].hex() if op!=3 else None}
      if start-last_chart>.5:
       self.history.append({'time':time.time(),'rtt_us':rec['rtt_us'],'device_us':device_us});last_chart=start
    self.stop.wait(0 if config['running'] and config['pace']=='throughput' else max(.005,.05-(time.monotonic()-start)))
  except Exception as exc:
   self.state['errors']+=1;self.state['phase']='error';self.event(str(exc))
  finally:
   if self.client:self.client.close()
   if armed:
    try:self.restore()
    except Exception as exc:self.state['phase']='recovery failed';self.state['recovery']=str(exc);self.event('Recovery failed; reservation retained: '+str(exc))
   elif getattr(self,'owned',False):
    if json.loads(self.lease.read_text()).get('lease_id')==self.lease_id:self.lease.unlink()
   self.stop.set();self.uart_stop.set()
   if self.serial:time.sleep(.2);self.serial.close()
   self.log.close();(self.a.out/'final_status.json').write_text(json.dumps(self.snapshot(),indent=2))

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for key in ('vivado','pdi','restore','out'):p.add_argument('--'+key,type=Path,required=True)
 for key in ('restore-sha256','cable','serial'):p.add_argument('--'+key,required=True)
 p.add_argument('--server',default='localhost:3121');p.add_argument('--board',default='192.168.10.2');p.add_argument('--bind',default='192.168.10.1');p.add_argument('--port',type=int,default=8035)
 a=p.parse_args();d=Dashboard(a);token=secrets.token_urlsafe(24)
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def send(self,code,body,kind):
   self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
  def do_GET(self):
   if self.path=='/api/status':return self.send(200,json.dumps({**d.snapshot(),'token':token}).encode(),'application/json')
   files={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
   if self.path not in files:return self.send(404,b'Not found','text/plain')
   name=files[self.path];kind='text/html' if name.endswith('html') else 'text/javascript' if name.endswith('js') else 'text/css'
   self.send(200,(ROOT/'web'/name).read_bytes(),kind+'; charset=utf-8')
  def do_POST(self):
   if self.path!='/api/control' or self.headers.get('X-Dashboard-Token')!=token:return self.send(403,b'Forbidden','text/plain')
   try:
    n=int(self.headers.get('Content-Length','0'))
    if n>1024:raise ValueError('Request too large')
    d.control(json.loads(self.rfile.read(n)));self.send(200,b'{}','application/json')
   except Exception as exc:self.send(400,json.dumps({'error':str(exc)}).encode(),'application/json')
 server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
 worker=threading.Thread(target=d.work,daemon=False);worker.start()
 signal.signal(signal.SIGINT,lambda *_:threading.Thread(target=server.shutdown,daemon=True).start())
 if hasattr(signal,'SIGTERM'):signal.signal(signal.SIGTERM,lambda *_:threading.Thread(target=server.shutdown,daemon=True).start())
 print(f'DASHBOARD http://127.0.0.1:{a.port}/ PID={os.getpid()}',flush=True)
 try:server.serve_forever()
 finally:d.stop.set();worker.join(timeout=340);server.server_close()
if __name__=='__main__':main()
