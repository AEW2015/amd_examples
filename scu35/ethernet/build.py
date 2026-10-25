"""SCU35 IPI Ethernet build: hardware, standalone platform, application, PDI."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess
SRC=Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--tools',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
 p.add_argument('--phase',choices=['hardware','platform','firmware','image','all'],default='all');a=p.parse_args()
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
 if len(str(out))>70 or any(c.isspace() for c in str(out)):raise ValueError('Use a fresh short build path without spaces')
 suffix='.bat' if os.name=='nt' else ''
 vivado=a.tools/'Vivado/bin'/('vivado'+suffix);vitis=a.tools/'Vitis/bin'/('vitis'+suffix)
 gcc=a.tools/'Vitis/gnu/riscv'/('nt' if os.name=='nt' else 'lin')/'bin'/('riscv64-unknown-elf-gcc'+('.exe' if os.name=='nt' else ''))
 phases=['hardware','platform','firmware','image'] if a.phase=='all' else [a.phase]
 for phase in phases:
  env=os.environ.copy();env['ETH_BUILD']=str(out)
  if phase in ['hardware','image']:cmd=[vivado,'-mode','batch','-nolog','-nojournal','-source',SRC/'build.tcl','-tclargs',SRC,out,phase,'2']
  elif phase=='platform':
   shutil.copy2(SRC/'build_platform.py',out/'build_platform.py');cmd=[vitis,'-s',out/'build_platform.py']
  else:
   staged=out/'src';staged.mkdir(exist_ok=True)
   shutil.copy2(SRC/'main.c',staged/'main.c')
   shutil.copy2(SRC/'../fw/lscript.ld',staged/'lscript.ld')
   bsp=out/'vsw/plat/export/plat/sw/mb'
   cmd=[gcc,'-march=rv32i_zicsr_zifencei','-mabi=ilp32','-DSDT','-O2','-g',f'-specs={bsp}/Xilinx.spec',f'-I{bsp}/include',staged/'main.c',f'-Wl,-T,{staged}/lscript.ld',f'-L{bsp}/lib','-Wl,--start-group,-lxilstandalone,-lxiltimer,-lxilsecure,-lgloss,-lxil,-lgcc,-lc','-Wl,--end-group',f'-Wl,-Map,{out}/eth.map','-o',out/'eth.elf']
  with (out/(phase+'.log')).open('w',encoding='utf-8') as log:
   result=subprocess.run(list(map(str,cmd)),cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=5400)
  if result.returncode:raise RuntimeError(f'{phase} failed; inspect {out}/{phase}.log')
  if phase=='firmware':
   metadata={'source_sha256':hashlib.sha256((SRC/'main.c').read_bytes()).hexdigest(),'elf_sha256':hashlib.sha256((out/'eth.elf').read_bytes()).hexdigest(),'compiler_command':list(map(str,cmd))}
   (out/'firmware.json').write_text(json.dumps(metadata,indent=2)+'\n')
  print('ETH_PHASE_PASS',phase,flush=True)
if __name__=='__main__':main()
