"""Independently verify saved UDP protocol bytes and public crypto vectors offline."""
import argparse,hashlib,json,struct
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
def verify(path):
 report=json.loads(Path(path).read_text());assert report['overall']=='PASS'
 aes=AESGCM(bytes(range(32)));nonces=set();valid=negative=0
 for vector in report['vectors']:
  req=bytes.fromhex(vector['request_hex']);resp=bytes.fromhex(vector['response_hex'])
  magic,version,op,n,seq,session=struct.unpack('!4sBBHII',req[:16]);assert magic==b'E35Q' and version==1
  rm,rv,ro,rn,rs,rss,status,*_=struct.unpack('!4sBBHIIIIII',resp[:32])
  assert (rm,rv,ro,rs,rss)==(b'E35R',1,op,seq,session) and len(resp)==60+rn
  if vector['label']=='bad_tag_rejected':
   assert status==2 and rn==0
   try:aes.decrypt(req[16:28],req[28:],req[:16])
   except InvalidTag:negative+=1;continue
   raise AssertionError('Modified request unexpectedly has a valid GCM tag')
  data=aes.decrypt(req[16:28],req[28:],req[:16]) if op==2 else req[16:]
  assert len(data)==n
  if vector['label']=='replay_rejected':
   assert status==3 and rn==0
   accepted=bytes.fromhex(vector['accepted_response_hex'])
   am,av,ao,an,aseq,asession,astatus,*_=struct.unpack('!4sBBHIIIIII',accepted[:32])
   assert (am,av,ao,an,aseq,asession,astatus)==(b'E35R',1,op,n,seq,session,0)
   assert aes.decrypt(accepted[32:44],accepted[44:],accepted[:32])==data
   negative+=1;continue
  assert status==0
  assert data==bytes((i*17+n)%256 for i in range(n))
  if op not in (3,4):
   nonce=resp[32:44];assert nonce not in nonces;nonces.add(nonce)
   result=aes.decrypt(nonce,resp[44:],resp[:32])
  else:result=resp[44:44+rn]
  expected=hashlib.sha3_256(data).digest() if op==5 else hashlib.shake_256(data).digest(32) if op==6 else data
  assert result==expected==bytes.fromhex(vector['result_hex'])
  valid+=1
 assert valid==20 and negative==2
 print(f'OFFLINE_ETHERNET_CAPTURE_PASS: {valid} exact payload/hash cases; bad-tag and replay response records; unique response nonces')
 return {'valid_vectors':valid,'negative_vectors':negative,'scope':'Cryptographic consistency of captured protocol bytes; capture hashes do not independently attest its physical origin.'}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('capture',type=Path);a=p.parse_args();verify(a.capture)
