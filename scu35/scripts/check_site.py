"""Check generated Pages content, and optionally browser-test a served site."""
from pathlib import Path
from urllib.parse import urlsplit, unquote
import argparse, json, os
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]

def static(site):
 pages=list(site.rglob('*.html'))
 for path in pages:
  soup=BeautifulSoup(path.read_text(encoding='utf-8'),'html.parser')
  for a in soup.select('[href]'):
   href=a['href']
   assert not href.lower().startswith(('file:','c:')),href
   if href.startswith(('http:','https:','mailto:','data:','#','javascript:')):continue
   raw=unquote(urlsplit(href).path)
   target=site/raw.removeprefix('/amd_examples/') if raw.startswith('/amd_examples/') else path.parent/raw
   assert target.is_file(),(path,href)
  for el in soup.select('img[src],script[src],link[rel=stylesheet]'):
   value=el.get('src',el.get('href',''))
   assert value.startswith(('data:','https:','http:')), (path,value)
 soup=BeautifulSoup((site/'index.html').read_text(encoding='utf-8'),'html.parser')
 expected=BeautifulSoup((ROOT/'docs/presenter/index.html').read_text(encoding='utf-8'),'html.parser')
 chapter_count=len(expected.select('.chapter'))
 assert len(soup.select('.chapter'))==len(soup.select('[data-complete]'))==chapter_count
 assert soup.select_one('#ethernet') and soup.select_one('#tab-ethernet')
 assert len(soup.select('#ethernet img[src^="data:"]'))==3
 assert not soup.select('.lesson-box,.lesson-check')
 assert 'Check your understanding' not in soup.get_text()
 assert 'Learning goal' not in soup.get_text()
 image_count=len(expected.select('img[src]'))
 assert len(soup.select('img[src^="data:"]'))==image_count
 print(f'PASS: {len(pages)} HTML pages; local navigation/resources; {chapter_count} lessons; {image_count} images')

def browser(url):
 from playwright.sync_api import sync_playwright
 errors=[]
 with sync_playwright() as p:
  opts={'headless':True}
  if os.environ.get('SCU35_BROWSER'):opts['executable_path']=os.environ['SCU35_BROWSER']
  b=p.chromium.launch(**opts);page=b.new_page(viewport={'width':1600,'height':1050})
  page.on('pageerror',lambda error:errors.append(str(error)))
  response=page.goto(url);assert response.status==200
  chapter_count=page.locator('.chapter-tab').count()
  assert page.locator('#tab-ethernet').count()==1
  page.locator('#lesson-reset').click()
  for tab in page.locator('.chapter-tab').all():
   tab.click();active=page.locator('.chapter.active');assert active.count()==1
   active.locator('[data-complete]').click()
  assert page.locator('#lesson-count').inner_text()==f'{chapter_count} of {chapter_count} chapters complete'
  page.reload();assert page.locator('#lesson-count').inner_text()==f'{chapter_count} of {chapter_count} chapters complete'
  page.locator('#lesson-reset').click();assert page.locator('#lesson-progress').get_attribute('value')=='0'
  page.locator('#tab-boot').click()
  for button in page.locator('[data-boot-variant]').all():
   button.click();assert page.locator('#boot-source').get_attribute('href').startswith('https://github.com/')
  page.locator('#tab-start').click()
  assert page.evaluate('Array.from(document.images).filter(i=>i.getAttribute("src")).every(i=>i.complete && i.naturalWidth>0)')
  page.set_viewport_size({'width':430,'height':932});assert page.evaluate('document.documentElement.scrollWidth-innerWidth')<=2
  page.locator('#tab-ethernet').click()
  assert page.locator('#ethernet .cli.command').count()==4
  page.goto(url.rsplit('/',1)[0]+'/presenter.html');assert page.locator('.chapter-tab').count()==chapter_count
  assert not errors,errors
  b.close()
 print(f'PASS: desktop/mobile browser; {chapter_count} chapters; persisted completion/reset; boot selectors; images; Ethernet example; original presenter; no JS errors')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--site',type=Path,default=ROOT/'out/site');p.add_argument('--url');args=p.parse_args()
 static(args.site)
 if args.url:browser(args.url)
