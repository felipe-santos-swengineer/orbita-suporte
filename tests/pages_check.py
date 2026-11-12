"""Smoke test the generated site under a project subpath without any backend."""
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

root=Path(__file__).resolve().parent.parent
subprocess.run([sys.executable,'scripts/build_pages.py'],cwd=root,check=True)
server=subprocess.Popen([sys.executable,'-m','http.server','8012','--bind','127.0.0.1','--directory',str(root)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            urllib.request.urlopen('http://127.0.0.1:8012/dist/').close()
            break
        except OSError:
            time.sleep(.1)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8012/dist/')
        expect(page.locator('.demo-banner')).to_be_visible()
        page.locator('#login-email').fill('admin@orbita.local')
        page.locator('#login-password').fill('Orbita@Admin123')
        page.locator('#login-form button').click()
        expect(page.locator('#rows tr')).to_have_count(3)
        page.locator('[data-ticket="2"]').click()
        expect(page.locator('.similar-card')).to_have_count(1)
        page.locator('.similar-card summary').click()
        expect(page.locator('.similar-solution')).to_contain_text('Exemplo fictício')
        page.locator('#analyze').click()
        expect(page.locator('#modal-error')).to_contain_text('não executa Ollama')
        page.locator('#close').click()
        page.locator('[data-view="metrics"]').click()
        expect(page.locator('.metric-cards .stat')).to_have_count(7)
        page.locator('[data-view="documents"]').click()
        expect(page.locator('.doc-card')).to_have_count(6)
        page.locator('[data-view="users"]').click()
        expect(page.locator('.user-row')).to_have_count(3)
        page.locator('#logout').click()
        page.locator('#login-email').fill('solicitante@orbita.local')
        page.locator('#login-password').fill('Orbita@Solicitante123')
        page.locator('#login-form button').click()
        expect(page.locator('#rows tr')).to_have_count(2)
        page.locator('#create').click()
        page.locator('#title').fill('Chamado de demonstração')
        page.locator('#description').fill('Descrição fictícia para validar o cadastro no navegador.')
        page.locator('#ticket-form button').click()
        expect(page.locator('#comment-form')).to_be_visible()
        page.locator('#close').click()
        page.reload()
        expect(page.locator('#rows tr')).to_have_count(3)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors,errors
        browser.close()
        print('Static Pages demo passed: assets, logins, roles, tickets, similar cases, indicators, articles and persistence.')
finally:
    server.terminate()
    server.wait(timeout=10)
