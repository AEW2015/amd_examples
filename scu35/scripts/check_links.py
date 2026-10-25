"""Check portable local links and notebook syntax; no external requests or hardware."""
from pathlib import Path
from urllib.parse import unquote,urlsplit
import json,re
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
def main():
    checks=0
    for p in [ROOT/'docs/scu35_presenter.html',ROOT/'docs/presenter/index.html',*ROOT.glob('evidence/*/report.html')]:
        soup=BeautifulSoup(p.read_text(encoding='utf-8'),'html.parser')
        for el in soup.find_all(['a','img','script','link']):
            href=el.get('href') or el.get('src')
            if not href or href.startswith(('http:','https:','data:','mailto:','#','javascript:')):continue
            dest=(p.parent/unquote(urlsplit(href).path)).resolve()
            assert dest.is_relative_to(ROOT) and dest.is_file(),f'{p.relative_to(ROOT)}: {href}'
            checks+=1
    for p in ROOT.rglob('*.md'):
        for href in re.findall(r'\]\(([^\s)]+)\)',p.read_text(encoding='utf-8')):
            if href.startswith(('http:','https:','#','mailto:')):continue
            dest=(p.parent/unquote(urlsplit(href).path)).resolve()
            assert dest.is_relative_to(ROOT) and dest.exists(),f'{p.relative_to(ROOT)}: {href}'
            checks+=1
    print('LOCAL_LINKS_PASS',checks)
if __name__=='__main__':main()
