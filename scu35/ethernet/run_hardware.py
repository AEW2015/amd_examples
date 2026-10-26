"""Explicit SCU35 volatile programming, Ethernet test, UART capture, and recovery."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import argparse,hashlib,json,os,re,socket,subprocess,threading,time,uuid
import serial
from host import run
from host import Client
from pq import run as run_pq
from verify_capture import verify
SRC=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--vivado',type=Path,required=True,help='Must match the running hw_server release')
 p.add_argument('--pdi',type=Path,required=True);p.add_argument('--restore',type=Path,required=True)
 p.add_argument('--restore-sha256',required=True);p.add_argument('--cable',required=True)
 p.add_argument('--serial',required=True);p.add_argument('--server',default='localhost:3121')
 p.add_argument('--bind',default='192.168.10.1');p.add_argument('--board',default='192.168.10.2')
 p.add_argument('--out',type=Path,required=True);p.add_argument('--count',type=int,default=50)
 p.add_argument('--pq',action='store_true',help='Also upload and verify actual LMS/HSS vectors and negative cases')
 p.add_argument('--restore-completion-marker',help='Optional known-good recovery firmware completion line; permits one documented SSS-status recovery retry')
 a=p.parse_args()
 if sha(a.restore)!=a.restore_sha256.lower():raise ValueError('Recovery image hash mismatch')
 if not a.cable.isalnum():raise ValueError('Exact cable serial required')
 if not a.pdi.is_file():raise FileNotFoundError(a.pdi)
 a.out.mkdir(parents=True,exist_ok=False)
 # Coordinate with the existing local SCU35 workflows. An existing lease is
 # never considered stale merely because its timestamp has passed.
 lock=Path.home()/'codex/hardware-coordination'/('scu35-'+a.cable+'.lock')
 lock.parent.mkdir(parents=True,exist_ok=True)
 lease_id=str(uuid.uuid4());now=datetime.now(timezone.utc)
 fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
 with os.fdopen(fd,'w') as f:json.dump({'owner':'ethernet/root','target':a.cable,'lease_id':lease_id,'acquired_utc':now.isoformat(),'expires_utc':(now+timedelta(minutes=30)).isoformat(),'task':'SCU35 physical Ethernet PMC crypto test with recovery'},f)
 metadata={'pdi_sha256':sha(a.pdi),'restore_sha256':sha(a.restore),'cable':a.cable,'server':a.server,'started_utc':now.isoformat(),'hardware_pass':False,'recovery_pass':False}
 stop=threading.Event();ready=threading.Event();restore_complete=threading.Event();uart=None;reader=None;armed=False
 def program(image,filename):
  cmd=[str(a.vivado),'-mode','batch','-nolog','-nojournal','-source',str(SRC/'../hw/program.tcl'),'-tclargs',a.server,a.cable,str(image.resolve()),'accept']
  with (a.out/filename).open('w',encoding='utf-8') as log:
   result=subprocess.run(cmd,cwd=a.out,stdout=log,stderr=subprocess.STDOUT,timeout=240)
  if result.returncode or 'PROGRAM_CHECK_PASS' not in (a.out/filename).read_text(errors='replace'):raise RuntimeError('Programming/status failed: '+filename)
 try:
  uart=serial.Serial(a.serial,115200,timeout=.1)
  def read_uart():
   with (a.out/'uart.txt').open('w',encoding='utf-8') as log:
    while not stop.is_set():
     line=uart.readline().decode('utf-8',errors='replace')
     if line:
      log.write(line);log.flush();print(line.rstrip(),flush=True)
      if 'E35_READY,' in line:ready.set()
      if a.restore_completion_marker and a.restore_completion_marker in line:restore_complete.set()
  reader=threading.Thread(target=read_uart,daemon=True);reader.start()
  armed=True;program(a.pdi,'program.log')
  if not ready.wait(30):raise TimeoutError('No E35_READY UART record')
  ping=['ping','-n' if os.name=='nt' else '-c','2',a.board]
  result=subprocess.run(ping,capture_output=True,text=True,timeout=15)
  (a.out/'ping.txt').write_text(result.stdout+'\n'+result.stderr)
  if result.returncode:raise RuntimeError('Ethernet ICMP reachability failed')
  report=run(a.board,a.bind,a.out/'ethernet',a.count)
  verify(a.out/'ethernet/results.json')
  if a.pq:
   client=Client(a.board,a.bind,a.out/'ethernet/peer_state.json')
   try:run_pq(client,a.out/'pq.json')
   finally:client.close()
   metadata['pq_pass']=True
  metadata['hardware_pass']=report['overall']=='PASS'
 finally:
  if armed:
   restore_complete.clear()
   try:program(a.restore,'restore.log');metadata['recovery_pass']=True
   except Exception as error:
    metadata['initial_recovery_error']=repr(error)
    text=(a.out/'restore.log').read_text(errors='replace')
    match=re.search(r'^DEVICE_STATUS DONE=1 ERROR=(0x[0-9a-fA-F]+)',text,re.M)
    # Preserve the actual error. Never clear/mask hardware status to pass.
    # In the observed active-service transition the first recovery runs but
    # latches SSS_CFG_ERR. Only retry after the named baseline completes its
    # own cleanup, and only for exactly that one status bit.
    if a.restore_completion_marker and match and int(match[1],16)==0x200000 and restore_complete.wait(60):
     metadata['recovery_retry_reason']='First recovery DONE=1 with SSS_CFG_ERR; named baseline completed; retry after its volatile crypto cleanup. No error-status writes.'
     try:program(a.restore,'restore_retry.log');metadata['recovery_pass']=True
     except Exception as retry_error:metadata['recovery_error']=repr(retry_error)
    else:metadata['recovery_error']=repr(error)
  stop.set()
  if reader:reader.join(timeout=2)
  if uart:uart.close()
  metadata['finished_utc']=datetime.now(timezone.utc).isoformat()
  (a.out/'session.json').write_text(json.dumps(metadata,indent=2)+'\n')
  if not armed or metadata['recovery_pass']:
   held=json.loads(lock.read_text())
   if held.get('lease_id')!=lease_id:raise RuntimeError('Lease ownership changed; refusing release')
   lock.unlink()
 if not metadata['recovery_pass']:raise RuntimeError('Recovery failed; retain lease and inspect logs')
 if not metadata['hardware_pass']:raise RuntimeError('Ethernet tests failed')
 print('ETH_HARDWARE_AND_RECOVERY_PASS',a.out)
if __name__=='__main__':main()
