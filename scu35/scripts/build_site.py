"""Build a static GitHub Pages lesson; no vendor tools or hardware required."""
from pathlib import Path
from urllib.parse import urlsplit, unquote, quote
import argparse, base64, json, mimetypes
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
REPO = 'https://github.com/AEW2015/amd_examples'
BRANCH = 'scu35-pmc-lab'
WEB = f'{REPO}/blob/{BRANCH}/scu35/'
CSS = """
body.lesson .presenter-only,body.lesson #audience-toggle{display:none!important}
.lesson-complete{margin:12px 0}.lesson-complete[aria-pressed=true]{background:#176649;color:white}
.lesson-progress{padding:12px 0;font-size:14px}.lesson-progress progress{width:100%;accent-color:#087f8c}
.chapter-tab.completed .num{background:#176649;color:white}.lesson-links{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0}
body.lesson .side-bottom{font-size:12px}body.lesson .lesson-status{display:block;min-height:1.4em}
@media print{.lesson-complete,.lesson-progress{display:none!important}}
"""
JS = """
(()=>{
 const key='scu35:lesson:v1';let done=new Set();
 try{const saved=JSON.parse(localStorage.getItem(key)||'[]');if(Array.isArray(saved))done=new Set(saved.filter(x=>typeof x==='string'));}catch{}
 const ids=[...document.querySelectorAll('.chapter')].map(c=>c.id);done=new Set([...done].filter(id=>ids.includes(id)));
 const render=()=>{
  document.querySelector('#lesson-progress').value=done.size;
  document.querySelector('#lesson-count').textContent=`${done.size} of ${ids.length} chapters complete`;
  document.querySelectorAll('[data-complete]').forEach(b=>{let yes=done.has(b.dataset.complete);b.setAttribute('aria-pressed',String(yes));b.textContent=yes?'Completed — click to undo':'Mark chapter complete';});
  document.querySelectorAll('.chapter-tab').forEach(t=>t.classList.toggle('completed',done.has(t.getAttribute('aria-controls'))));
 };
 document.querySelectorAll('[data-complete]').forEach(b=>b.addEventListener('click',()=>{const id=b.dataset.complete;done.has(id)?done.delete(id):done.add(id);try{localStorage.setItem(key,JSON.stringify([...done]));document.querySelector('#lesson-status').textContent='Progress saved in this browser.';}catch{document.querySelector('#lesson-status').textContent='Progress lasts for this session; browser storage is unavailable.';}render();}));
 document.querySelector('#lesson-reset').addEventListener('click',()=>{done.clear();try{localStorage.removeItem(key);}catch{}render();document.querySelector('#lesson-status').textContent='Lesson progress cleared.';});render();
})();
"""

def build(out):
 out.mkdir(parents=True, exist_ok=True)
 queue = [(ROOT/'docs/scu35_presenter.html', 'presenter.html')]
 seen = set()
 def hosted(value, source):
  if not value or value.startswith(('#','https:','http:','mailto:','data:','javascript:')): return value
  bits=urlsplit(value); path=(source.parent/unquote(bits.path)).resolve()
  if not path.is_relative_to(ROOT) or not path.is_file(): raise ValueError(f'Unresolved site link: {source}: {value}')
  rel=path.relative_to(ROOT).as_posix()
  if path.suffix=='.html':
   target='files/'+rel
   queue.append((path,target))
   return '/amd_examples/'+target+('#'+bits.fragment if bits.fragment else '')
  return WEB+quote(rel,safe='/')+('#'+bits.fragment if bits.fragment else '')
 def transform(source):
  soup=BeautifulSoup(source.read_text(encoding='utf-8'),'html.parser')
  for el in soup.find_all(href=True): el['href']=hosted(el['href'],source)
  for el in soup.find_all('img',src=True):
   if el['src'].startswith(('data:','http:','https:')):continue
   path=(source.parent/unquote(el['src'])).resolve()
   if not path.is_relative_to(ROOT) or not path.is_file():raise ValueError(f'Missing image {path}')
   el['src']='data:'+(mimetypes.guess_type(path.name)[0] or 'application/octet-stream')+';base64,'+base64.b64encode(path.read_bytes()).decode()
  for script in soup.find_all('script'):
   if script.string and 'window.PRESENTER=' in script.string:
    data=json.loads(script.string.split('window.PRESENTER=',1)[1].rstrip(';'))
    def walk(obj):
     if isinstance(obj,dict):
      for k,v in obj.items():
       if k=='link' and isinstance(v,str):obj[k]=hosted(v,source)
       else:walk(v)
     elif isinstance(obj,list):
      for v in obj:walk(v)
    walk(data);script.string='window.PRESENTER='+json.dumps(data).replace('<','\\u003c')+';'
  return soup
 presenter=transform(queue[0][0])
 # Keep the recent vendor-driver folder links in both hosted versions.
 libraries={'XilNvm':'lib/sw_services/xilnvm','XilPuf':'lib/sw_services/xilpuf','XilSecure':'lib/sw_services/xilsecure','PMCL_TRNG':'XilinxProcessorIPLib/drivers/trngpsx'}
 table=presenter.select_one('#examples table')
 if table:
  for row in table.select('tbody tr'):
   cell=row.find(['td','th'])
   library=next((v for k,v in libraries.items() if cell and cell.get_text().startswith(k)),None)
   if cell and library and not cell.find('a'):
    a=presenter.new_tag('a',href='https://github.com/Xilinx/embeddedsw/tree/b5cd5477bb44b9fadd98be10ea2f12705b9287f3/'+library)
    a.string=cell.get_text();cell.clear();cell.append(a)
 (out/'presenter.html').write_text(str(presenter),encoding='utf-8')
 lesson=BeautifulSoup(str(presenter),'html.parser');lesson.body['class']=lesson.body.get('class',[])+['lesson']
 chapter_count=len(lesson.select('.chapter'))
 lesson.title.string='SCU35 PMC Security — Self-paced Lab'
 lesson.find('meta',attrs={'name':'description'})['content']='A self-paced SCU35 PMC security lab: AMD examples, IPI, PDI, SHA3, AES, PUF and post-quantum authentication, with recorded hardware evidence.'
 lesson.select_one('.side-title').string='SCU35 PMC security · Learn at your own pace'
 lesson.select_one('.side-bottom').clear()
 lesson.select_one('.side-bottom').append(BeautifulSoup('<b>Self-paced lab</b><p>Recorded hardware evidence · Oct 25, 2026. This page does not connect to hardware.</p><a href="presenter.html">Original presenter view</a>','html.parser'))
 progress=BeautifulSoup(f'<div class="lesson-progress"><label for="lesson-progress" id="lesson-count">0 of {chapter_count} chapters complete</label><progress id="lesson-progress" max="{chapter_count}" value="0"></progress><button id="lesson-reset">Reset lesson progress</button><small class="lesson-status" id="lesson-status" role="status">Progress is stored only in this browser.</small></div>','html.parser')
 lesson.select_one('.chapter-nav').insert_before(progress)
 notice=lesson.select_one('#portable-notice');notice.clear()
 notebook_count=len(list((ROOT/'notebooks').glob('*.ipynb')))
 notice.append(BeautifulSoup(f'<b>Learn first, run locally when ready.</b> Explore the diagrams and saved results here without installing tools or connecting a board. For a fresh run, clone the lab and follow the setup guide. No eFUSE or flash writes are part of this lab.<div class="lesson-links"><a href="{WEB}README.md">Setup &amp; reproduction guide</a><a href="#notebooks" data-chapter="notebooks">{notebook_count} PMC notebook walkthroughs</a><a href="{REPO}/tree/{BRANCH}/scu35/notebooks">Open notebooks on GitHub</a><a href="{REPO}/archive/refs/heads/{BRANCH}.zip">Download source ZIP</a><a href="presenter.html">Presenter view</a></div>','html.parser'))
 for chapter in lesson.select('.chapter'):
  b=lesson.new_tag('button',attrs={'class':'lesson-complete','data-complete':chapter['id'],'aria-pressed':'false'});b.string='Mark chapter complete'
  chapter.select_one('.chapter-footer').insert_before(b)
 style=lesson.new_tag('style');style.string=CSS;lesson.head.append(style)
 script=lesson.new_tag('script');script.string=JS;lesson.body.append(script)
 (out/'index.html').write_text(str(lesson),encoding='utf-8')
 for source,target in queue:
  if target=='presenter.html' or target in seen:continue
  seen.add(target);dest=out/target;dest.parent.mkdir(parents=True,exist_ok=True)
  dest.write_text(str(transform(source)),encoding='utf-8')
 (out/'.nojekyll').write_text('',encoding='utf-8')
 (out/'README.md').write_text(f'# SCU35 PMC security lesson\n\nPublished from [{BRANCH}]({REPO}/tree/{BRANCH}/scu35).\n\nRebuild: `python scripts/build_site.py --out /path/to/site` from the scu35 directory.\n',encoding='utf-8')
 print(f'Built {chapter_count} lessons, presenter, and {len(seen)} linked evidence pages in {out}')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=ROOT/'out/site');args=p.parse_args();build(args.out.resolve())
