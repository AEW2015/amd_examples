"""Build the advanced resident-buffer PMC benchmark; keep separate from vendor PLM."""
from pathlib import Path
import json,os,shutil,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lab import ROOT,run,tool,sha,manifest

def build_native(c,fixture=None,stock_plm=None):
    out=Path(c['build_dir']).resolve()/'native'
    if out.exists():raise RuntimeError('Native build exists; choose another build_dir')
    shutil.copytree(ROOT/'native',out,ignore=shutil.ignore_patterns('__pycache__'))
    (out/'build').mkdir(exist_ok=True)
    if fixture:
        if not stock_plm:raise ValueError('--fixture requires --stock-plm from that Vivado build')
        shutil.copy2(fixture,out/'inputs/system_wrapper.rcdo')
        shutil.copy2(stock_plm,out/'build/stock_plm.elf')
        (out/'seed.bif').write_text('new_bif: {id_code=0x04e80093 image {name=pmcl_subsys id=0 partition {id=1,type=bootloader,file=build/stock_plm.elf} partition {id=2,type=pldata,file=inputs/system_wrapper.rcdo}}}\n')
        run([tool(c,'bootgen'),'-arch','spartanup','-image','seed.bif','-o','build/fixture_seed.pdi','-w'],cwd=out,log=out/'build/seed.log')
        run([sys.executable,'pdi_tools.py','derive'],cwd=out,log=out/'build/derive.log')
    gcc=tool(c,'gcc');ar=tool(c,'ar')
    flags=['-march=rv32imac_zicsr_zifencei','-mabi=ilp32','-Os','-g','-ffunction-sections','-fdata-sections','-ffreestanding','-fno-builtin','-fno-stack-protector','-msmall-data-limit=0','-nostdlib','-nostartfiles','-Wall','-Wextra','-Werror']
    run([gcc,*flags,'-I','bsp/include','-c','bsp/pmc_bsp.c','-o','build/pmc_bsp.o'],cwd=out,log=out/'build/bsp.log')
    run([ar,'rcs','build/libpmc_bsp.a','build/pmc_bsp.o'],cwd=out,log=out/'build/ar.log')
    run([sys.executable,'pdi_tools.py','spec'],cwd=out,log=out/'build/spec.log')
    sources=['startup.S','hello.c','monitor.c','probe.S','sha3.c','loader.c','benchmarks.c','aes_test.c','trng_test.c','stream_test.c','peripheral_tests.c','pit2_api_test.c','iomodule_tests.c','fast.c','native_pq.c','bsp/experimental/pmc_pit2_irq.c','bsp/experimental/pmc_stream.c']
    args=[gcc,*flags,'-Wl,--gc-sections,--no-relax','-Wl,--build-id=none','-Wl,-T,plm.ld','-Wl,-Map,build/plm.map',*sources,'-I','bsp/experimental','-I','bsp/include','build/libpmc_bsp.a','-lgcc','-o','build/plm.elf']
    run(args,cwd=out,log=out/'build/compiler.log')
    run([tool(c,'bootgen'),'-arch','spartanup','-image','pmc.bif','-o','build/pmc_independent.pdi','-w'],cwd=out,log=out/'build/bootgen.log')
    run([sys.executable,'pdi_tools.py','verify'],cwd=out,log=out/'build/verify.log')
    meta={'pdi_sha256':sha(out/'build/pmc_independent.pdi'),'elf_sha256':sha(out/'build/plm.elf'),'inputs':{name:sha(out/name) for name in ['inputs/pq_vectors.json','inputs/pq_upload.tcl','inputs/hss.c']},'hardware_tested':False,'fixture_scope':'Retained, hash-checked PL fixture. Its original RTL/XDC/build source is included under fixture/. Firmware rebuilt here.'}
    (out/'build/build_meta.json').write_text(json.dumps(meta,indent=2)+'\n')
    manifest(out,'Native PMC benchmark build only; not a production loader or authenticated boot.')
    print('NATIVE_BUILD_PASS',out/'build/pmc_independent.pdi')
