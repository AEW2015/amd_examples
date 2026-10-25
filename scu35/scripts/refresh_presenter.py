"""Repair portable evidence links and regenerate the standalone presenter from its HTML/CSS/JS source."""
from pathlib import Path
from urllib.parse import unquote,urlsplit
import base64,json,mimetypes,os,re
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/'docs/presenter/index.html'
def portable_target(value,base):
    if value.startswith(('http:','https:','mailto:','data:','#','javascript:')):return value
    raw=unquote(urlsplit(value).path)
    path=(base/raw).resolve()
    if path.is_relative_to(ROOT) and path.exists():return value
    normalized=raw.replace('\\','/')
    name=Path(normalized).name
    target=None
    if '/assets/' in normalized or normalized.startswith('assets/'):
        p=ROOT/'docs/presenter/assets'/name
        if p.exists():target=p
    if '/sec35/timer/' in normalized:
        if name in ['compare.pdi','bench.elf','timer.xsa','routed.dcp']:target=ROOT/'reference/timer'/name
        elif name in ['features.c','timer_io.c','bench.c','lscript.ld']:target=ROOT/'fw'/name
        elif name.endswith('.bd'):target=ROOT/'hw/sys.bd'
        else:target=ROOT/'evidence/timer'/name
    elif '/sec35/fast/' in normalized:
        if name in ['fast.c','native_pq.c']:target=ROOT/'native'/name
        else:target=ROOT/'evidence/native'/name
    elif '/sec35/boot/' in normalized:
        if name.endswith('.pdi'):target=ROOT/'reference/boot'/name
        elif '/runs/' in normalized:target=ROOT/'evidence/boot/runs'/normalized.split('/runs/',1)[1]
        else:target=ROOT/'evidence/boot'/name
    elif '/sec35/pdi_view/' in normalized:target=ROOT/'evidence/pdi'/name
    elif name.endswith('.ipynb'):
        key='08_highspeed' if 'fast' in name else '06_boot' if 'signed' in name or 'auth' in name or '/boot/' in normalized else '00_start'
        target=ROOT/'notebooks'/(key+'.ipynb')
    elif '/sec35/compare/' in normalized:target=ROOT/'reference/boot/plain.pdi' if name.endswith('.pdi') else ROOT/'README.md'
    if target is None or not target.is_file():target=ROOT/'README.md'
    return os.path.relpath(target,base).replace('\\','/')

def main():
    soup=BeautifulSoup(INDEX.read_text(encoding='utf-8'),'html.parser')
    for el in soup.find_all(href=True):
        el['href']=portable_target(el['href'],INDEX.parent)
    replacements={
        'C:/aiup/s35tmr/tmr.xpr':'<build_dir>/ipi/sec.xpr',
        'C:/aiup/sec35/timer/static_files/plm.elf':'<build_dir>/plm.elf',
        'C:/aiup/sec35/timer/timer.xsa':'<build_dir>/hw.xsa',
        'C:/aiup/sec35/platform/hw.xsa':'<build_dir>/hw.xsa',
        'C:/aiup/sec35/platform/build_platform.py':'scripts/build_platform.py',
        'C:/aiup/v35plat/plat35/export/plat35/plat35.xpfm':'<build_dir>/vsw/plat/export/plat/plat.xpfm',
        'C:/aiup/v35plat/plat35/export/plat35/sw/mb':'<build_dir>/vsw/plat/export/plat/sw/mb',
        'C:/aiup/v35plat':'<build_dir>/vsw',
        'C:/aiup/cmpenv/Scripts/python.exe':'your selected virtual-environment Python',
        'sec35/timer/inputs/sys_final.bd':'hw/sys.bd',
        'sec35/timer/timer_io.c':'fw/timer_io.c',
        'sec35/timer/features.c':'fw/features.c',
        'sec35/timer/bench.c':'fw/bench.c',
        'sec35/timer/compare.py':'host/compare.py',
        'timer.xsa':'hw.xsa',
        'plat35.xpfm':'plat.xpfm',
    }
    for text in list(soup.find_all(string=True)):
        if text.find_parent(['script','style']):continue
        cli_parent=text.find_parent('div',class_='cli')
        if cli_parent and any(c in cli_parent.get('class',[]) for c in ['output','reference']):continue
        value=str(text)
        for old,new in replacements.items():value=value.replace(old,new)
        if value!=str(text):text.replace_with(value)
    for pre in soup.select('.cli.command pre'):
        text=pre.get_text()
        if 'write_hw_platform' in text:text='# From the scu35 directory; creates the shared IPI/XSA\npython lab.py build --phase hardware'
        elif 'build_platform.py' in text:text='python lab.py build --phase platform'
        elif 'open_project' in text:text='# Open <build_dir>/ipi/sec.xpr in Vivado; inspect the sys block design.'
        elif 'readelf' in text:text='riscv64-unknown-elf-readelf -h -l /path/to/build/plm.elf'
        elif '-arch spartanup -read' in text:text='bootgen -arch spartanup -read /path/to/build/demo.pdi'
        elif 'sec35/compare/execute_notebook.py' in text:text='python lab.py hardware --pdi /path/to/build/demo.pdi'
        elif 'sec35/boot/pdicheck.py' in text or 'sec35/boot/verify.py' in text:text='python lab.py verify\n# Fresh real-design signing/encryption after build:\npython lab.py boot'
        elif 'sec35/boot/run.ps1' in text:
            variant='combo' if 'combo' in text else 'signed'
            text=f'python lab.py hardware --mode boot --pdi /path/to/build/boot_TIMESTAMP/{variant}.pdi'
        elif 'sec35/fast/execute_notebook.py' in text:text='python lab.py hardware --mode native --pdi /path/to/build/native/build/pmc_independent.pdi'
        pre.string=text
    # Embedded boot-selector links are consumed by app.js, not ordinary <a> tags.
    data_script=next(s for s in soup.find_all('script') if s.string and 'window.PRESENTER=' in s.string)
    data=json.loads(data_script.string.split('window.PRESENTER=',1)[1].rstrip(';'))
    def fix(obj):
        if isinstance(obj,dict):
            for key,value in obj.items():
                if key=='link' and isinstance(value,str):obj[key]=portable_target(value,INDEX.parent)
                else:fix(value)
        elif isinstance(obj,list):
            for item in obj:fix(item)
    fix(data);data_script.string='window.PRESENTER='+json.dumps(data).replace('<','\\u003c')+';'
    if not soup.find(id='portable-notice'):
        notice=soup.new_tag('div',id='portable-notice',attrs={'class':'callout'})
        notice.append('Portable lab: use README.md and lab.py for current build/run commands. Recorded output and source excerpts preserve their original paths and timing provenance. Links resolve within this checkout; no original personal workspace is required. ')
        link=soup.new_tag('a',href='../../README.md');link.string='Open reproduction guide';notice.append(link)
        soup.select_one('#start').insert(3,notice)
    INDEX.write_text(str(soup),encoding='utf-8')
    # Other report HTML files keep their content; only broken local anchors are repaired.
    for report in ROOT.rglob('*.html'):
        # The live dashboard has server routes, not presenter/report links.
        if report.is_relative_to(ROOT/'ethernet/web') or 'out' in report.relative_to(ROOT).parts:continue
        if report==INDEX or report.name=='scu35_presenter.html':continue
        s=BeautifulSoup(report.read_text(encoding='utf-8'),'html.parser')
        changed=False
        for a in s.find_all('a',href=True):
            href=a['href']
            if href.startswith(('http:','https:','data:','mailto:','#','javascript:')):continue
            mapped=portable_target(href,report.parent)
            if mapped!=href:a['href']=mapped;changed=True
        if changed:report.write_text(str(s),encoding='utf-8')
    standalone=BeautifulSoup(INDEX.read_text(encoding='utf-8'),'html.parser')
    style=standalone.new_tag('style');style.string=(INDEX.parent/'style.css').read_text(encoding='utf-8')
    standalone.find('link',rel='stylesheet').replace_with(style)
    script=standalone.new_tag('script');script.string=(INDEX.parent/'app.js').read_text(encoding='utf-8')
    standalone.find('script',src='app.js').replace_with(script)
    for img in standalone.find_all('img',src=True):
        p=INDEX.parent/img['src'];mime=mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
        img['src']='data:'+mime+';base64,'+base64.b64encode(p.read_bytes()).decode()
    for a in standalone.find_all('a',href=True):
        href=a['href']
        if href.startswith(('http:','https:','data:','mailto:','#','javascript:')):continue
        a['href']=os.path.relpath((INDEX.parent/unquote(urlsplit(href).path)).resolve(),ROOT/'docs').replace('\\','/')
    text=str(standalone)
    # JSON selector paths move one level up along with the standalone file.
    script=next(s for s in standalone.find_all('script') if s.string and 'window.PRESENTER=' in s.string)
    old=script.string
    data=json.loads(old.split('window.PRESENTER=',1)[1].rstrip(';'))
    def shift(obj):
        if isinstance(obj,dict):
            for key,value in obj.items():
                if key=='link' and isinstance(value,str) and not value.startswith(('http:','https:','#')):obj[key]=os.path.relpath((INDEX.parent/value).resolve(),ROOT/'docs').replace('\\','/')
                else:shift(value)
        elif isinstance(obj,list):
            for item in obj:shift(item)
    shift(data);script.string='window.PRESENTER='+json.dumps(data).replace('<','\\u003c')+';'
    (ROOT/'docs/scu35_presenter.html').write_text(str(standalone),encoding='utf-8')
    print(f"Portable presenter rebuilt; {len(soup.select('.chapter'))} chapters, relative links, embedded visuals")
if __name__=='__main__':main()
