"""Exercise real SCU35 UDP/PMC crypto on the direct Ethernet link.

Public diagnostic key 00..1f; this is not a provisioned secure channel.
No JTAG or UART is used for these payload transfers.
"""
from pathlib import Path
import argparse,hashlib,json,secrets,socket,statistics,struct,time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
KEY=bytes(range(32))
REQUEST=struct.Struct('!4sBBHII')
RESPONSE=struct.Struct('!4sBBHIIIIII')

class Client:
 def __init__(self,board='192.168.10.2',bind='192.168.10.1',state=Path('out/ethernet_peer.json')):
  self.state=Path(state);self.state.parent.mkdir(parents=True,exist_ok=True)
  saved=json.loads(self.state.read_text()) if self.state.exists() else {'session':secrets.randbits(32),'next_seq':1}
  self.session=saved['session'];self.seq=saved['next_seq'];self.limit=self.seq+1000000
  if self.limit>=2**32:raise ValueError('Sequence exhausted; restart the board and create new host state')
  self.state.write_text(json.dumps({'session':self.session,'next_seq':self.limit})+'\n')
  self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.sock.bind((bind,0));self.sock.connect((board,6000));self.sock.settimeout(2)
  self.aes=AESGCM(KEY);self.host_nonce_prefix=secrets.token_bytes(8);self.seen_nonces=set();self.samples=[]
 def close(self):self.sock.close()
 def request(self,op,data):
  self.seq+=1
  if self.seq>=self.limit:raise ValueError('Reserved sequence range exhausted')
  assert 16<=len(data)<=1024 and len(data)%16==0
  header=REQUEST.pack(b'E35Q',1,op,len(data),self.seq,self.session)
  if op==2:
   nonce=self.host_nonce_prefix+self.seq.to_bytes(4,'big')
   wire=header+nonce+self.aes.encrypt(nonce,data,header)
  else:wire=header+data
  return wire
 def exchange(self,wire,expected_status=0):
  start=time.perf_counter_ns();self.sock.send(wire);raw=self.sock.recv(1600);elapsed=(time.perf_counter_ns()-start)/1000
  return self.decode(wire,raw,elapsed,expected_status)
 def decode(self,wire,raw,elapsed,expected_status=0):
  if len(raw)<60:raise AssertionError('Truncated response')
  magic,version,op,n,seq,session,status,previous_ticks,rx,tx=RESPONSE.unpack(raw[:32])
  req=REQUEST.unpack(wire[:16])
  assert magic==b'E35R' and version==1 and (op,seq,session)==(req[2],req[4],req[5])
  assert status==expected_status,(status,expected_status)
  assert len(raw)==60+n
  nonce=raw[32:44];body=raw[44:44+n];tag=raw[44+n:]
  if status:
   assert n==0
   data=b''
  elif op in (3,4):data=body
  else:
   assert nonce not in self.seen_nonces,'Device repeated a response nonce'
   self.seen_nonces.add(nonce)
   data=self.aes.decrypt(nonce,body+tag,raw[:32])
  record={'op':op,'input_bytes':req[3],'output_bytes':n,'sequence':seq,'status':status,'rtt_us':elapsed,'previous_operation_ticks':previous_ticks,'board_rx':rx,'board_tx_before_reply':tx}
  self.samples.append(record)
  return data,record,raw
 def call(self,op,data):return self.exchange(self.request(op,data))

def run(board,bind,out,count):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 client=Client(board,bind,out/'peer_state.json')
 report={'board':board,'host_bind':bind,'public_diagnostic_key':KEY.hex(),'hardware_transport':'UDP over physical Ethernet; no JTAG payload path','timing':'Host send-to-receive RTT; request preparation and host AES verification outside RTT. Sequential benchmark; not line-rate throughput.','checks':{},'benchmarks':[],'vectors':[]}
 try:
  first_wire=None;first_reply=None
  for n in [16,64,256,1024]:
   payload=bytes((i*17+n)%256 for i in range(n))
   for op,label in [(3,'plain'),(1,'encrypt'),(2,'authenticated_echo'),(5,'SHA3-256'),(6,'SHAKE-256')]:
    wire=client.request(op,payload);data,record,raw=client.exchange(wire)
    expected=hashlib.sha3_256(payload).digest() if op==5 else hashlib.shake_256(payload).digest(32) if op==6 else payload
    assert data==expected,(label,n)
    report['checks'][f'{label}_{n}']='PASS'
    report['vectors'].append({'label':label,'request_hex':wire.hex(),'response_hex':raw.hex(),'result_hex':data.hex()})
    if op==1 and n==1024:first_reply=raw
  payload=bytes(range(256))*4
  wire=client.request(2,payload);data,_,accepted=client.exchange(wire);assert data==payload
  _,_,rejected=client.exchange(wire,expected_status=3);report['checks']['board_replay_rejected']='PASS'
  report['vectors'].append({'label':'replay_rejected','request_hex':wire.hex(),'response_hex':rejected.hex(),'accepted_response_hex':accepted.hex(),'result_hex':''})
  wire=bytearray(client.request(2,payload));wire[-1]^=1
  _,_,rejected=client.exchange(bytes(wire),expected_status=2);report['checks']['board_bad_tag_rejected']='PASS'
  report['vectors'].append({'label':'bad_tag_rejected','request_hex':bytes(wire).hex(),'response_hex':rejected.hex(),'result_hex':''})
  # Deterministic peer vectors above and fresh arbitrary host payloads below.
  arbitrary=secrets.token_bytes(1024)
  data,_,_=client.call(2,arbitrary);assert data==arbitrary
  report['checks']['fresh_host_payload_roundtrip']='PASS'
  for op,label in [(3,'UDP plaintext echo'),(1,'PMC encrypt response'),(2,'PMC decrypt + encrypt echo')]:
   for n in [64,256,1024]:
    payload=secrets.token_bytes(n);times=[]
    for i in range(count):
     data,rec,_=client.call(op,payload);assert data==payload;times.append(rec['rtt_us'])
    report['benchmarks'].append({'method':label,'payload_bytes':n,'packets':count,'median_rtt_us':statistics.median(times),'p95_rtt_us':sorted(times)[min(len(times)-1,int(.95*len(times)))],'sequential_payload_MBps':n*count/sum(times)})
  report['checks']['unique_device_response_nonces']='PASS'
  _,stats,_=client.call(4,bytes(16));report['last_operation_stats']=stats
  report['overall']='PASS'
  if first_reply:(out/'sample_encrypted_reply.hex').write_text(first_reply.hex()+'\n')
 except Exception as error:
  report['overall']='FAIL';report['error']=repr(error);raise
 finally:
  report['samples']=client.samples
  (out/'results.json').write_text(json.dumps(report,indent=2)+'\n');client.close()
 print(json.dumps({k:v for k,v in report.items() if k not in ('samples','vectors')},indent=2))
 return report

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',default='192.168.10.2');p.add_argument('--bind',default='192.168.10.1');p.add_argument('--out',type=Path,default=Path('out/ethernet'));p.add_argument('--count',type=int,default=50);args=p.parse_args()
 if args.count<1:raise SystemExit('--count must be positive')
 run(args.board,args.bind,args.out,args.count)
