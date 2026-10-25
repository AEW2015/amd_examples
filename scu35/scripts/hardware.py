"""Explicit volatile programming with exact cable selection, bounded capture and recovery."""
from pathlib import Path
import hashlib,json,os,re,secrets,shutil,subprocess,sys,tempfile,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lab import ROOT,run,tool,sha

def execute(c,pdi,mode='runtime'):
    import serial
    for key in ['hardware_vivado','server','cable','restore_pdi','restore_sha256']:
        if not c.get(key):raise ValueError('Set config.json '+key)
    if mode=='runtime' and not c.get('serial_port'):raise ValueError('Set serial_port')
    if not re.fullmatch('[A-Za-z0-9]+',c['cable']):raise ValueError('An exact cable serial is required')
    restore=Path(c['restore_pdi']).resolve()
    if sha(restore)!=c['restore_sha256'].lower():raise ValueError('Recovery PDI hash differs')
    if not pdi.is_file():raise FileNotFoundError(pdi)
    if mode=='native':
        source_meta=json.loads((pdi.parent/'build_meta.json').read_text())
        if sha(pdi)!=source_meta['pdi_sha256'] or sha(pdi.parent/'plm.elf')!=source_meta['elf_sha256']:
            raise ValueError('Native image/ELF identity differs from its build metadata')
        for name in ['pq_upload.tcl','pq_vectors.json']:
            if sha(ROOT/'native/inputs'/name)!=source_meta['inputs']['inputs/'+name]:raise ValueError('Public vector identity differs')
    attempt=Path(c['build_dir']).resolve()/'runs'/time.strftime('%Y%m%dT%H%M%S')
    attempt.mkdir(parents=True)
    locks=Path(tempfile.gettempdir())/'scu35-locks';locks.mkdir(exist_ok=True)
    lock=locks/(hashlib.sha256((c['server']+'/'+c['cable']).encode()).hexdigest()+'.lock')
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    os.write(fd,json.dumps({'pid':os.getpid(),'attempt':str(attempt)}).encode());os.close(fd)
    recovery=False;armed=False;port=None;proc=None
    metadata={'pdi_sha256':sha(pdi),'restore_sha256':sha(restore),'mode':mode,'server':c['server'],'cable':c['cable']}
    if mode=='native':
        for name in ['pq_upload.tcl','pq_vectors.json']:shutil.copy2(ROOT/'native/inputs'/name,attempt/name)
        shutil.copy2(pdi,attempt/'test.pdi')
        shutil.copy2(pdi.parent/'plm.elf',attempt/'plm.elf')
        shutil.copy2(pdi.parent/'build_meta.json',attempt/'build_meta.json')
    (attempt/'session.json').write_text(json.dumps(metadata,indent=2)+'\n')
    def command(image,expected='accept'):
        return [str(tool(c,'hardware_vivado')),'-mode','batch','-nolog','-nojournal','-source',str(ROOT/'hw/program.tcl'),'-tclargs',c['server'],c['cable'],str(image),expected]
    try:
        if mode=='runtime':port=serial.Serial(c['serial_port'],115200,timeout=.25)
        armed=True
        with (attempt/'program.log').open('w',encoding='utf-8') as log:
            args=command(pdi,'reject' if mode=='reject' else 'accept')
            if mode=='native':
                args=[str(tool(c,'hardware_vivado')),'-mode','batch','-nolog','-nojournal','-source',str(ROOT/'hw/native_test.tcl'),'-tclargs',str(pdi),str(attempt),str(secrets.randbits(32)),str(secrets.randbits(32)),c['server'],c['cable'],str(restore)]
            proc=subprocess.Popen(args,cwd=attempt,stdout=log,stderr=subprocess.STDOUT)
            if mode=='runtime':
                deadline=time.monotonic()+240;done=False
                with (attempt/'uart.txt').open('w',encoding='utf-8') as uart:
                    while time.monotonic()<deadline:
                        line=port.readline().decode('utf-8',errors='replace');uart.write(line);uart.flush()
                        if line:print(line.rstrip())
                        if 'TMR_FAIL,' in line:raise RuntimeError('Timer self-test failed')
                        if 'CMP_DONE,' in line:
                            if 'CMP_DONE,0' not in line:raise RuntimeError('Device reported failure')
                            done=True;break
                        if proc.poll() not in (None,0):raise RuntimeError('Programming process failed')
                if not done:raise TimeoutError('No complete runtime result before deadline')
            proc.wait(timeout=1200 if mode=='native' else 180)
        if proc.returncode or 'PROGRAM_CHECK_PASS' not in (attempt/'program.log').read_text():raise RuntimeError('Programming status verification failed')
        if mode=='runtime':
            sys.path.insert(0,str(ROOT/'host'));from compare import parse_capture
            result=parse_capture(attempt/'uart.txt','7d1bf77bc454dd1f')
            assert len(result['rows'])==31
        if mode=='native':
            sys.path.insert(0,str(ROOT/'native'));from analyze import validate
            validate(attempt/'results.txt')
        metadata['demo_pass']=True
    finally:
        if port:port.close()
        if proc and proc.poll() is None:proc.terminate();proc.wait(timeout=30)
        if armed:
            try:
                run(command(restore),cwd=attempt,log=attempt/'restore.log',timeout=240)
                recovery='PROGRAM_CHECK_PASS' in (attempt/'restore.log').read_text()
            finally:
                metadata['recovery_pass']=recovery
                (attempt/'session.json').write_text(json.dumps(metadata,indent=2)+'\n')
        if recovery or not armed:lock.unlink()
    if not recovery:raise RuntimeError('Recovery failed; lock retained. Inspect '+str(attempt))
    print('HARDWARE_SESSION_PASS',attempt)
