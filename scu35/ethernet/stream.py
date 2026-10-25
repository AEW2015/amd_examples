"""Bounded two-request UDP pipeline, validating every response with host.Client."""
import hashlib,time
from host import RESPONSE

def batch(client,op,payload,count=100,window=2):
 if window not in (1,2):raise ValueError('Only one or two in-flight packets supported')
 pending={};sent=0;received=0;records=[];latest=None
 expected=hashlib.sha3_256(payload).digest() if op==5 else hashlib.shake_256(payload).digest(32) if op==6 else payload
 start=time.perf_counter()
 while received<count:
  while sent<count and len(pending)<window:
   wire=client.request(op,payload);seq=client.seq
   before=time.perf_counter_ns();client.sock.send(wire);pending[seq]=(wire,before);sent+=1
  raw=client.sock.recv(1600);arrived=time.perf_counter_ns()
  if len(raw)<32:raise AssertionError('Truncated pipelined response')
  seq=RESPONSE.unpack(raw[:32])[4]
  if seq not in pending:raise AssertionError('Unexpected pipelined sequence')
  wire,before=pending.pop(seq)
  data,rec,_=client.decode(wire,raw,(arrived-before)/1000)
  if data!=expected:raise AssertionError('Pipeline payload/digest mismatch')
  records.append(rec);latest=(data,rec,raw);received+=1
 elapsed=time.perf_counter()-start
 return {'records':records,'latest':latest,'elapsed_s':elapsed,'packets':received,'input_bytes':received*len(payload),'payload_Mbps':received*len(payload)*8/elapsed/1e6,'window':window}
