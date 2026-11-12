"""Build a standalone, explicitly simulated GitHub Pages showcase."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.knowledge import ARTICLES

target = ROOT / 'dist'
assets = target / 'assets'
assets.mkdir(parents=True, exist_ok=True)
for name in ['app.js', 'auth-ui.js', 'style.css', 'orbita.svg']:
    shutil.copyfile(ROOT / 'frontend' / name, assets / name)
app_js = (assets / 'app.js').read_text(encoding='utf-8')
app_js = '\n'.join("async function health(){$('#health').classList.remove('offline');$('#health').textContent='Demonstração estática · Dados fictícios · IA e anexos disponíveis na instalação local';}" if line.startswith('async function health()') else line for line in app_js.splitlines())
(assets / 'app.js').write_text(app_js, encoding='utf-8')
shutil.copyfile(ROOT / 'pages' / 'demo-api.js', assets / 'demo-api.js')
docs = [{'id': i, 'title': title, 'category': category, 'tags': tags, 'content': content,
         'status': 'published', 'created_at': '2026-11-12T12:00:00Z', 'updated_at': '2026-11-12T12:00:00Z'}
        for i, (title, category, tags, content) in enumerate(ARTICLES, 1)]
(assets / 'demo-data.js').write_text('window.ORBITA_DEMO_ARTICLES = ' + json.dumps(docs, ensure_ascii=False) + ';', encoding='utf-8')
html = (ROOT / 'frontend' / 'index.html').read_text(encoding='utf-8')
html = html.replace('/assets/', './assets/').replace('href="/"', 'href="./"')
html = html.replace('<title>Órbita', '<title>Demo · Órbita')
html = html.replace('<body class="signed-out">', '''<body class="signed-out demo-mode"><div class="demo-banner">DEMONSTRAÇÃO · Dados fictícios salvos apenas neste navegador. Login e permissões simulados. IA e anexos exigem a versão local. <a href="https://github.com/felipe-santos-swengineer/orbita-suporte#login-e-contas-de-demonstração" target="_blank" rel="noopener">Acessos e código ↗</a> <button type="button" onclick="if(confirm('Restaurar os dados fictícios da demonstração?')){localStorage.removeItem('orbita-pages-v1');sessionStorage.removeItem('orbita-demo-user');location.reload();}">Restaurar demo</button></div>''')
html = html.replace('Os acessos estão documentados no README do projeto.', '''<br>Solicitante: solicitante@orbita.local / Orbita@Solicitante123<br>Atendente: atendente@orbita.local / Orbita@Atendente123<br>Admin: admin@orbita.local / Orbita@Admin123<br>Estas contas simulam os papéis; não use dados reais.''')
html = html.replace('<script src="./assets/app.js">', '<script src="./assets/demo-data.js"></script><script src="./assets/demo-api.js"></script><script src="./assets/app.js">')
(target / 'index.html').write_text(html, encoding='utf-8')
(target / '.nojekyll').write_text('', encoding='utf-8')
with (assets / 'style.css').open('a', encoding='utf-8') as css:
    css.write('''\n.demo-banner{position:sticky;top:0;z-index:10;background:#fff3d7;color:#7d612a;padding:12px 20px;text-align:center;font:12px/1.8 system-ui}.demo-banner a{color:#6452a4;margin-left:10px}.demo-banner button{font-size:10px;padding:4px 8px;margin-left:10px;background:#f1e2bf}.demo-mode aside{top:64px}.demo-mode .login-screen{min-height:calc(100vh - 64px)}.demo-mode .login-demo{overflow-wrap:anywhere}@media(max-width:700px){.demo-mode aside{top:auto}.demo-banner{position:static;font-size:10px}.demo-mode .login-screen{min-height:auto}}''')
print('GitHub Pages demo built in dist/')
