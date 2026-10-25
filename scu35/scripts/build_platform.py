"""Vitis Python entry point; invoke using lab.py build, not system Python."""
from pathlib import Path
import os,vitis
out=Path(os.environ['SCU35_BUILD'])
workspace=out/'vsw'
if (workspace/'plat').exists():raise RuntimeError('Platform exists; use a fresh build directory')
client=vitis.create_client()
try:
    client.set_workspace(str(workspace))
    platform=client.create_platform_component(name='plat',hw_design=str(out/'hw.xsa'))
    domain=platform.add_domain(name='mb',cpu='mb',os='standalone')
    for library in ('xilsecure','xilpuf','xilnvm'):domain.set_lib(library)
    platform.build()
    bsp=workspace/'plat/export/plat/sw/mb'
    header=(bsp/'include/xparameters.h').read_text()
    assert 'XPAR_XTMRCTR' in header and 'XPAR_XTRNGPSX' in header and 'XPAR_XGPIO' not in header
    for n in ('libxilsecure.a','libxilpuf.a','libxilnvm.a'):assert (bsp/'lib'/n).is_file()
    print('PLATFORM_BUILD_PASS',bsp)
finally:vitis.dispose()
