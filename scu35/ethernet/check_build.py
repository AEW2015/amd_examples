"""Validate ELF memory, catalog-only IPI, routed timing/DRC and artifact hashes."""
from pathlib import Path
import argparse,hashlib,json,os,re,struct
SRC=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check(out,session=None,cdc_review=None):
 out=Path(out).resolve();checks={};artifacts=[]
 def artifact(role,path):
  path=Path(path).resolve();assert path.is_file() and path.stat().st_size>0,path
  artifacts.append({'role':role,'path':os.path.relpath(path,out).replace('\\','/'),'sha256':sha(path)})
 # Compiler/staged source binding, including the linker script.
 assert sha(SRC/'main.c')==sha(out/'src/main.c')
 assert sha(SRC/'../fw/lscript.ld')==sha(out/'src/lscript.ld')
 fw=json.loads((out/'firmware.json').read_text())
 assert fw['source_sha256']==sha(SRC/'main.c') and fw['elf_sha256']==sha(out/'eth.elf')
 checks['source_binding']={'status':'pass','evidence':'firmware.json'}
 b=(out/'eth.elf').read_bytes();assert b[:6]==b'\x7fELF\x01\x01'
 h=struct.unpack_from('<16sHHIIIIIHHHHHH',b);bram_end=0;shared_end=0
 for i in range(h[10]):
  v=struct.unpack_from('<IIIIIIII',b,h[5]+i*h[9])
  if v[0]!=1:continue
  va,mem=v[2],v[5]
  if va<0x20000:assert va+mem<=0x20000;bram_end=max(bram_end,va+mem)
  else:assert 0x0402b000<=va and va+mem<=0x0402e000;shared_end=max(shared_end,va+mem)
 checks['memory']={'status':'pass','local_bram_used_bytes':bram_end,'local_bram_free_bytes':0x20000-bram_end,'shared_used_bytes':shared_end-0x0402b000}
 bd=out/'prj/eth.srcs/sources_1/bd/hw/sys.bd'
 design=json.loads(bd.read_text())['design'];ips={}
 def walk(parts,prefix=''):
  for name,obj in parts.items():
   path=prefix+name
   if 'components' in obj:walk(obj['components'],path+'/')
   else:
    assert obj.get('vlnv','').startswith('xilinx.com:ip:'),(path,obj.get('vlnv'))
    ips[path]=obj['vlnv']
 walk(design['components'])
 assert ips['ethernet']=='xilinx.com:ip:axi_ethernetlite:3.0'
 assert ips['pmc']=='xilinx.com:ip:pmcbridge:1.0'
 checks['catalog_ip']={'status':'pass','ip_instances':ips,'scope':'Generated top wrapper only; no custom functional RTL'}
 timing=(out/'timing_summary.txt').read_text(errors='replace')
 m=re.search(r'^\s*(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)',timing,re.M)
 assert m,'Timing summary not found'
 assert float(m[1])>=0 and float(m[5])>=0 and int(m[3])==int(m[7])==0,('Timing failed',m.group())
 checks['routed_timing']={'status':'pass','setup_slack_ns':float(m[1]),'hold_slack_ns':float(m[5]),'evidence':'timing_summary.txt','scope':'100 MHz fabric and 100 Mb/s MII, with documented PCB skew assumption and slow-control exceptions'}
 drc=(out/'drc.txt').read_text(errors='replace')
 assert not re.search(r'\|\s*(?:Error|Critical Warning)\s*\|',drc,re.I),'DRC errors/critical warnings'
 checks['drc']={'status':'pass','evidence':'drc.txt'}
 checks['cdc_review']={'status':'incomplete','evidence':'cdc.txt','note':'Review remaining non-vendor-waived crossings; timing closure alone is not a CDC proof.'}
 if cdc_review:
  review=json.loads(Path(cdc_review).read_text())
  assert review['status']=='reviewed_for_lab_demonstration'
  assert review['pdi_sha256']==sha(out/'ethernet.pdi') and review['cdc_details_sha256']==sha(out/'cdc_details.txt')
  checks['cdc_review']={'status':'pass','evidence':os.path.relpath(cdc_review,out),'scope':'Review completed for laboratory use; four vendor reset-fanout critical warnings remain unwaived. Production CDC/reset-stress qualification is not claimed.'}
 if session:
  s=json.loads(Path(session).read_text());assert s['pdi_sha256']==sha(out/'ethernet.pdi')
  assert s['hardware_pass'] and s['recovery_pass']
  checks['hardware_and_recovery']={'status':'pass','evidence':os.path.relpath(session,out)}
 else:checks['hardware_and_recovery']={'status':'incomplete','note':'No new hardware execution claimed'}
 for role,path in [('firmware_source',SRC/'main.c'),('constraints',SRC/'board.xdc'),('rebuild',SRC/'build.tcl'),('host',SRC/'host.py'),('bd',bd),('bd_tcl',out/'sys.tcl'),('elf',out/'eth.elf'),('programming_image',out/'ethernet.pdi'),('hardware_handoff',out/'hw.xsa'),('routed_checkpoint',out/'routed.dcp'),('plm',out/'plm.elf'),('timing',out/'timing_summary.txt'),('drc',out/'drc.txt'),('cdc',out/'cdc.txt')]:artifact(role,path)
 if cdc_review:artifact('cdc_review',cdc_review);artifact('cdc_details',out/'cdc_details.txt')
 if session:
  artifact('hardware_session',session)
  for name in ['program.log','restore.log','uart.txt','ethernet/results.json']:
   artifact('hardware_evidence',Path(session).parent/name)
 result={'overall':'INCOMPLETE' if any(c['status']=='incomplete' for c in checks.values()) else 'PASS','scope':'SCU35 laboratory Ethernet crypto demonstration; not production CDC, networking, security or line-rate qualification.','artifacts':artifacts,'checks':checks}
 (out/'handoff.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'overall':result['overall'],'checks':checks},indent=2));return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--session',type=Path);p.add_argument('--cdc-review',type=Path);a=p.parse_args();check(a.out,a.session,a.cdc_review)
