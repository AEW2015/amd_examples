"""Optional browser QA; requires Playwright and a locally installed browser."""
from pathlib import Path
import json,os
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
def main():
    checks={};errors=[]
    with sync_playwright() as p:
        opts={'headless':True}
        if os.environ.get('SCU35_BROWSER'):opts['executable_path']=os.environ['SCU35_BROWSER']
        browser=p.chromium.launch(**opts)
        page=browser.new_page(viewport={'width':1600,'height':1050})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto((ROOT/'docs/scu35_presenter.html').as_uri())
        chapter_count=page.locator('.chapter-tab').count()
        assert page.locator('#tab-ethernet').count()==1
        for i in range(chapter_count):
            page.locator('.chapter-tab').nth(i).click()
            assert page.locator('.chapter.active').count()==1
        checks[f'{chapter_count}_chapters']='pass'
        page.locator('#tab-address-map').click()
        assert page.locator('#address-map a.register-link').count()==18
        checks['18_register_links']='pass'
        assert page.evaluate('Array.from(document.images).filter(i=>i.getAttribute("src")&&!i.naturalWidth).length')==0
        checks['embedded_images']='pass'
        page.locator('#tab-start').click();page.locator('#boot-variant').count() # The full UI remains client-side only.
        page.set_viewport_size({'width':430,'height':932})
        assert page.evaluate('document.documentElement.scrollWidth-innerWidth')<=2
        checks['mobile_layout']='pass'
        assert not errors,errors
        browser.close()
    print(json.dumps({'overall':'PASS','checks':checks,'errors':errors},indent=2))
if __name__=='__main__':main()
