"""Run using Vitis -s, with ETH_BUILD pointing to the build directory."""
from pathlib import Path
import os,vitis
out=Path(os.environ['ETH_BUILD'])
client=vitis.create_client()
try:
 client.set_workspace(str(out/'vsw'))
 platform=client.create_platform_component(name='plat',hw_design=str(out/'hw.xsa'))
 domain=platform.add_domain(name='mb',cpu='mb',os='standalone')
 domain.set_lib('xilsecure')
 platform.build()
 print('ETH_PLATFORM_PASS')
finally:vitis.dispose()
