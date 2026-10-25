"""Portable SCU35 lab entry point. Offline replay is the default; hardware is explicit."""
from pathlib import Path
import argparse,hashlib,json,os,platform,re,shutil,subprocess,sys,time

ROOT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def config():
    path=Path(os.environ.get('SCU35_CONFIG',ROOT/'config.json'))
    c=json.loads(path.read_text()) if path.exists() else {}
    for key,env in [('tools','AMD_TOOLS'),('hardware_vivado','SCU35_HW_VIVADO'),('build_dir','SCU35_BUILD')]:
        if os.environ.get(env):c[key]=os.environ[env]
    c.setdefault('build_dir',str(ROOT/'out'))
    c.setdefault('jobs',2)
    return c
def tool(c,name):
    if name=='hardware_vivado' and c.get(name):return Path(c[name])
    if c.get(name):return Path(c[name])
    if name in ('gcc','ar','readelf','objdump'):
        base=Path(c['riscv_bin']) if c.get('riscv_bin') else Path(c['tools'])/'Vitis/gnu/riscv'/('nt' if os.name=='nt' else 'lin')/'bin'
        return base/('riscv64-unknown-elf-'+name+('.exe' if os.name=='nt' else ''))
    product='Vitis' if name=='vitis' else 'Vivado'
    return Path(c['tools'])/product/'bin'/(name+('.bat' if os.name=='nt' else ''))
def run(args,cwd=None,log=None,env=None,timeout=3600):
    args=list(map(str,args));print('RUN',args[0],flush=True)
    # shell=False; arguments never interpolated into a shell command.
    with (Path(log).open('w',encoding='utf-8') if log else open(os.devnull,'w')) as f:
        p=subprocess.run(args,cwd=cwd,stdout=f if log else None,stderr=subprocess.STDOUT if log else None,env=env,timeout=timeout)
    if p.returncode:raise RuntimeError(f'Command failed ({p.returncode}); log: {log}')
def manifest(folder,scope):
    folder=Path(folder)
    files=[p for p in folder.rglob('*') if p.is_file() and p.name!='build_manifest.json' and not any(x in p.parts for x in ['.Xil','ip_user_files','vsw','ipi'])]
    data={'scope':scope,'hardware_tested':False,'host':platform.platform(),'files':{p.relative_to(folder).as_posix():sha(p) for p in files}}
    (folder/'build_manifest.json').write_text(json.dumps(data,indent=2)+'\n')
    return data
def doctor(c):
    print('Host:',platform.platform(),'Python:',platform.python_version(),'Source:',ROOT)
    print('Build:',Path(c['build_dir']).resolve())
    if 'tools' not in c:raise ValueError('Set AMD_TOOLS or config.json tools to the directory containing Vivado/ and Vitis/.')
    for name in ['vivado','vitis','bootgen','gcc','readelf']:
        p=tool(c,name);print(name,p,'FOUND' if p.is_file() else 'MISSING')
        if not p.is_file():raise FileNotFoundError(p)
    print('Tool version, SU35P availability and licensing are checked by the actual build. Match the hardware client to your hw_server version.')
def firmware(c,out):
    bsp=out/'vsw/plat/export/plat/sw/mb'
    source=ROOT/'fw/bench.c'
    # AMD's Windows GCC can split source paths containing spaces internally.
    # Stage byte-identical inputs under the short build root on every OS.
    staged=out/'src';staged.mkdir(exist_ok=True)
    for name in ['bench.c','lscript.ld']:shutil.copy2(ROOT/'fw'/name,staged/name)
    args=[tool(c,'gcc'),'-march=rv32i_zicsr_zifencei','-mabi=ilp32','-DSDT','-O2','-g',f'-specs={bsp}/Xilinx.spec',f'-I{bsp}/include',staged/'bench.c',f'-Wl,-T,{staged}/lscript.ld',f'-L{bsp}/lib','-Wl,--start-group,-lxilstandalone,-lxiltimer,-lxilsecure,-lxilpuf,-lgloss,-lxil,-lgcc,-lc','-Wl,--end-group',f'-Wl,-Map,{out}/bench.map','-o',out/'bench.elf']
    run(args,log=out/'firmware.log')
    p=subprocess.run([str(tool(c,'readelf')),'-lW','-SW',str(out/'bench.elf')],capture_output=True,text=True,check=True)
    (out/'elf_layout.txt').write_text(p.stdout)
    for line in p.stdout.splitlines():
        if line.strip().startswith('LOAD'):
            fields=line.split();address=int(fields[3],16);size=int(fields[4],16)
            if size and address+size>0x20000:raise ValueError('Loadable application bytes outside 128 KiB BRAM')
    ident=re.search(r'#define CMP_BUILD_ID "([a-f0-9]+)"',source.read_text())[1]
    (out/'firmware.json').write_text(json.dumps({'build_id':ident,'source_sha256':sha(source),'elf_sha256':sha(out/'bench.elf'),'note':'Firmware ID labels the C source snapshot; ELF SHA binds this compiler/BSP build.'},indent=2)+'\n')
def check_implementation(out):
    text=(out/'timing.txt').read_text(errors='replace')
    match=re.search(r'^\s*(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)\s+(-?\d+\.\d+)',text,re.M)
    if not match or float(match[1])<0 or float(match[5])<0 or int(match[3])!=0:
        raise RuntimeError('Implementation timing failed or summary not found; inspect timing.txt')
    drc=(out/'drc.txt').read_text(errors='replace')
    if re.search(r'\|\s*(?:Error|Critical Warning)\s*\|',drc,re.I):raise RuntimeError('DRC errors/critical warnings; inspect drc.txt')
    result={'setup_slack_ns':float(match[1]),'hold_slack_ns':float(match[5]),'scope':'Specified timing constraints; full reports retained. Known RTSTAT-10 PMC no-load warning is not suppressed.'}
    (out/'implementation_checks.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
def build(c,phase):
    out=Path(c['build_dir']).resolve();out.mkdir(parents=True,exist_ok=True)
    # Avoid vendor parser/path-length limitations while allowing arbitrary checkout paths.
    if len(str(out))>70 or not str(out).isascii() or any(ch.isspace() for ch in str(out)):
        raise ValueError('Select a short local ASCII build_dir without spaces, e.g. C:/s35 or /tmp/s35. Checkout may live elsewhere.')
    phases=['hardware','platform','firmware','image'] if phase=='all' else [phase]
    for step in phases:
        if step in ('hardware','image'):
            run([tool(c,'vivado'),'-mode','batch','-nolog','-nojournal','-source',ROOT/'hw/build.tcl','-tclargs',ROOT,out,step,str(c['jobs'])],cwd=out,log=out/(step+'.log'))
        elif step=='platform':
            env=os.environ.copy();env['SCU35_BUILD']=str(out)
            shutil.copy2(ROOT/'scripts/build_platform.py',out/'build_platform.py')
            run([tool(c,'vitis'),'-s',out/'build_platform.py'],cwd=out,log=out/'platform.log',env=env)
            if 'PLATFORM_BUILD_PASS' not in (out/'platform.log').read_text(errors='replace') or not (out/'vsw/plat/export/plat/sw/mb/lib/libxilsecure.a').is_file():
                raise RuntimeError('Vitis did not produce a verified platform; inspect platform.log')
        else:firmware(c,out)
    if 'image' in phases:
        impl=out/'ipi/sec.runs/impl_1'
        run([tool(c,'bootgen'),'-arch','spartanup','-image','sec_top.bif','-o',out/'demo.pdi','-w'],cwd=impl,log=out/'bootgen.log')
        shutil.copy2(impl/'sec_top.rcdo',out/'design.rcdo')
        shutil.copy2(impl/'static_files/plm.elf',out/'plm.elf')
        check_implementation(out)
        manifest(out,'Fresh AXI Timer runtime image; build only, no hardware execution.')
    print('BUILD_PHASE_PASS',phase,out)
def replay(out=None):
    sys.path.insert(0,str(ROOT/'host'))
    from compare import parse_capture
    record=ROOT/'evidence/timer/uart.txt'
    data=parse_capture(record,'7d1bf77bc454dd1f')
    print('Recorded timer capture:',len(data['rows']),'rows;',len(data['hashes']),'hashes;',len(data['aes']),'AES vectors; PASS')
    if out:
        from compare import run as compare_run
        Path(out).parent.mkdir(parents=True,exist_ok=True)
        compare_run(record,Path(out),100,5)
    return data
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor');sub.add_parser('verify')
    b=sub.add_parser('build');b.add_argument('--phase',choices=['all','hardware','platform','firmware','image'],default='all')
    r=sub.add_parser('replay');r.add_argument('--out',type=Path)
    compare_parser=sub.add_parser('compare');compare_parser.add_argument('--capture',type=Path,required=True);compare_parser.add_argument('--out',type=Path,required=True);compare_parser.add_argument('--native',action='store_true')
    inspect_parser=sub.add_parser('inspect');inspect_parser.add_argument('--pdi',type=Path);inspect_parser.add_argument('--elf',type=Path)
    p=sub.add_parser('boot');p.add_argument('--height',choices=[5,15],type=int,default=15)
    h=sub.add_parser('hardware');h.add_argument('--pdi',type=Path,required=True);h.add_argument('--mode',choices=['runtime','native','boot','reject'],default='runtime')
    n=sub.add_parser('native');n.add_argument('--fixture',type=Path);n.add_argument('--stock-plm',type=Path)
    args=ap.parse_args();c=config()
    if args.command=='doctor':doctor(c)
    elif args.command=='build':build(c,args.phase)
    elif args.command=='replay':replay(args.out)
    elif args.command=='compare':
        args.out.parent.mkdir(parents=True,exist_ok=True)
        if args.native:
            sys.path.insert(0,str(ROOT/'native'));from analyze import run as measure
            measure(args.capture,args.out)
        else:
            sys.path.insert(0,str(ROOT/'host'));from compare import run as measure
            measure(args.capture,args.out,1000,50)
    elif args.command=='inspect':
        if args.pdi:run([tool(c,'bootgen'),'-arch','spartanup','-read',args.pdi.resolve()])
        if args.elf:run([tool(c,'readelf'),'-h','-l',args.elf.resolve()])
        if not args.pdi and not args.elf:raise ValueError('Choose --pdi and/or --elf')
    elif args.command=='verify':
        run([sys.executable,ROOT/'scripts/verify.py'])
    elif args.command=='boot':
        sys.path.insert(0,str(ROOT/'scripts'));from boot import build_boot
        build_boot(c,Path(c['build_dir']).resolve(),args.height)
    elif args.command=='hardware':
        sys.path.insert(0,str(ROOT/'scripts'));from hardware import execute
        execute(c,args.pdi.resolve(),args.mode)
    elif args.command=='native':
        sys.path.insert(0,str(ROOT/'scripts'));from native import build_native
        build_native(c,args.fixture,args.stock_plm)
if __name__=='__main__':main()
