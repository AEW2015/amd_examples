"""Actual chunked Ethernet upload and AMD LMS/HSS verification requests.

Only public AMD n=32/h=5/w=2 vectors and one-level HSS are covered. Verification
does not sign, consume stateful signing keys, or establish a production trust root.
"""
from pathlib import Path
import secrets, struct, sys, time

HERE=Path(__file__).resolve().parent
sys.path.append(str(HERE.parent/'host'))
from hss_ref import load_vectors, verify_lms, verify_hss

CASES=('valid','bad_signature','bad_message','bad_key')


def material(op, case='valid'):
    if op not in (7,8) or case not in CASES:
        raise ValueError('Unsupported PQ method/case')
    v=load_vectors(HERE.parent/'host/inputs/hss.c')['Hss' if op==8 else 'Lms']
    msg=bytearray(v['message']);sig=bytearray(v['signature']);key=bytearray(v['public_key'])
    if case=='bad_signature':sig[32]^=1
    if case=='bad_message':msg[0]^=1
    if case=='bad_key':key[-1]^=1
    blob=bytearray(4608)
    blob[:len(sig)]=sig;blob[4480:4536]=msg;blob[4544:4544+len(key)]=key
    return bytes(blob),bytes(msg),bytes(sig),bytes(key)


class Verifier:
    def __init__(self,client):
        self.client=client;self.loaded=None;self.transfer_id=0;self.upload=None

    def prepare(self,op,case):
        if self.loaded==(op,case):return
        blob,self.message,self.signature,self.public_key=material(op,case)
        self.transfer_id=secrets.randbits(32)
        begin=time.perf_counter();packets=[]
        for offset in range(0,len(blob),1008):
            chunk=blob[offset:offset+1008]
            command=struct.pack('!4sIHHHH',b'PQU1',self.transfer_id,offset,len(chunk),len(blob),0)+chunk
            data,record,_=self.client.call(op,command)
            assert struct.unpack('!4sIII',data)==(b'PQA1',self.transfer_id,offset+len(chunk),len(blob))
            packets.append(record)
        self.upload={'bytes':len(blob),'packets':len(packets),
                     'wall_ms':(time.perf_counter()-begin)*1000,'records':packets}
        self.loaded=(op,case)

    def verify(self,op,case='valid'):
        self.prepare(op,case)
        command=struct.pack('!4sIII',b'PQV1',self.transfer_id,0,0)
        data,record,wire=self.client.call(op,command)
        magic,ident,accepted,status,ticks,number,received,flags=struct.unpack('!4s7I',data)
        assert magic==b'PQR1' and ident==self.transfer_id and received==4608
        assert bool(accepted)==(case=='valid'),(op,case,status)
        # A mismatch must be the vendor authentication failure, not an API error.
        if not accepted:assert status==0xAB,(op,case,status)
        fn=verify_hss if op==8 else verify_lms
        started=time.perf_counter_ns();python_ok=fn(self.message,self.signature,self.public_key)
        python_us=(time.perf_counter_ns()-started)/1000
        assert python_ok==bool(accepted)
        return {'algorithm':'HSS-SHAKE256' if op==8 else 'LMS-SHAKE256','case':case,
                'accepted':bool(accepted),'vendor_status':status,'device_verify_us':ticks/100,
                'python_verify_us':python_us,'verification_number':number,'blocks_used':flags,
                'message_bytes':len(self.message),'signature_bytes':len(self.signature),
                'public_key_bytes':len(self.public_key),'upload':self.upload,
                'result_matches_python':True,'rtt_us':record['rtt_us'],
                'record':record,'result_hex':data.hex(),'response_hex':wire.hex()}


def run(client,out,repeats=5):
    import json
    verifier=Verifier(client);rows=[]
    for op in (7,8):
        for case in CASES:
            for _ in range(repeats):rows.append(verifier.verify(op,case))
    guards=[]
    def rejected(label,command):
        _,record,_=client.exchange(client.request(7,command),expected_status=5)
        guards.append({'guard':label,'status':record['status'],'expected_status':5})
    ident=secrets.randbits(32)
    rejected('wrong_transfer_id',struct.pack('!4sIII',b'PQV1',ident,0,0))
    partial=struct.pack('!4sIHHHH',b'PQU1',ident,0,16,4608,0)+bytes(16)
    wire=client.request(7,partial);client.exchange(wire)
    _,rec,_=client.exchange(wire,expected_status=3)
    guards.append({'guard':'pq_replayed_command','status':rec['status'],'expected_status':3})
    bad=bytearray(client.request(7,partial));bad[-1]^=1
    _,rec,_=client.exchange(bytes(bad),expected_status=2)
    guards.append({'guard':'pq_bad_gcm_tag','status':rec['status'],'expected_status':2})
    rejected('incomplete_upload',struct.pack('!4sIII',b'PQV1',ident,0,0))
    rejected('upload_overrun',struct.pack('!4sIHHHH',b'PQU1',ident,4592,32,4608,0)+bytes(32))
    blob=bytearray(material(7)[0]);blob[4544:4548]=(16).to_bytes(4,'big')
    for offset in range(0,len(blob),1008):
        chunk=blob[offset:offset+1008]
        client.call(7,struct.pack('!4sIHHHH',b'PQU1',ident,offset,len(chunk),4608,0)+chunk)
    rejected('unsupported_parameter_profile',struct.pack('!4sIII',b'PQV1',ident,0,0))
    out=Path(out);out.write_text(json.dumps({'scope':'Fresh physical Ethernet uploads and device verification; upload excluded from API time',
                                           'rows':rows,'guards':guards,'overall':'PASS'},indent=2))
    return rows
