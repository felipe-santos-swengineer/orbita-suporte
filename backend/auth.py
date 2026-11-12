"""Local accounts, revocable sessions and API role enforcement."""
import hashlib
import hmac
import os
import re
import secrets
import time
from contextvars import ContextVar
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Literal

actor = ContextVar('actor', default=None)
DEMO_ACCOUNTS = [
    ('Solicitante Demo', 'solicitante@orbita.local', 'requester', 'Orbita@Solicitante123'),
    ('Atendente Demo', 'atendente@orbita.local', 'agent', 'Orbita@Atendente123'),
    ('Administrador Demo', 'admin@orbita.local', 'admin', 'Orbita@Admin123'),
]


def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return salt + ':' + digest


def verify_password(password, stored):
    salt, digest = stored.split(':')
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(value, digest)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def public_user(row):
    return {key: row[key] for key in ['id', 'name', 'email', 'role', 'active']}


def init_auth(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT UNIQUE NOT NULL,
      role TEXT NOT NULL,password_hash TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL,csrf TEXT NOT NULL,expires_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS login_failures(key TEXT NOT NULL,created_at REAL NOT NULL);
    ''')
    if not db.execute("SELECT 1 FROM migrations WHERE name='demo_accounts_v6'").fetchone():
        for name, email, role, password in DEMO_ACCOUNTS:
            db.execute('INSERT OR IGNORE INTO users(name,email,role,password_hash) VALUES(?,?,?,?)', (name, email, role, password_hash(password)))
        db.execute("INSERT INTO migrations VALUES('demo_accounts_v6')")


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=180)
    password: str = Field(min_length=1, max_length=256)


class UserInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=3, max_length=180)
    role: Literal['requester', 'agent', 'admin']
    active: bool = True
    password: str = Field(default='', max_length=256)


class PasswordInput(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(min_length=10, max_length=256)


def install_auth(app, database):
    def denied(message, code=403):
        return JSONResponse({'detail': message}, status_code=code, headers={'Cache-Control': 'no-store'})

    @app.middleware('http')
    async def authenticate(request: Request, call_next):
        path, method = request.url.path, request.method
        if not path.startswith('/api/'):
            return await call_next(request)
        if method not in ['GET', 'HEAD', 'OPTIONS']:
            origin = request.headers.get('origin')
            if request.headers.get('sec-fetch-site') == 'cross-site' or (origin and (urlsplit(origin).netloc != request.url.netloc or urlsplit(origin).scheme != request.url.scheme)):
                return denied('Origem da requisição não permitida.')
        if path == '/api/auth/login' and method == 'POST':
            return await call_next(request)
        cookie = request.cookies.get('orbita_session', '')
        with database() as db:
            session = db.execute('SELECT users.*,sessions.csrf FROM sessions JOIN users ON users.id=sessions.user_id WHERE token_hash=? AND expires_at>? AND active=1', (token_hash(cookie), time.time())).fetchone() if cookie else None
            user = public_user(session) if session else None
            if user and method not in ['GET', 'HEAD', 'OPTIONS'] and not hmac.compare_digest(request.headers.get('x-csrf-token', ''), session['csrf']):
                return denied('Sessão inválida para esta ação. Atualize a página.')
            if not user:
                return denied('Entre na sua conta para continuar.', 401)
            request.state.user = user
            request.state.csrf = session['csrf']
            if path.startswith('/api/users') and user['role'] != 'admin':
                return denied('Somente administradores podem gerenciar usuários.')
            if user['role'] == 'requester':
                if path == '/api/metrics' or path.endswith('/similar'):
                    return denied('Este recurso está disponível para a equipe de suporte.')
                match = re.match(r'^/api/tickets/(\d+)(?:/|$)', path)
                if match:
                    ticket = db.execute('SELECT requester_id FROM tickets WHERE id=?', (int(match[1]),)).fetchone()
                    if not ticket or ticket['requester_id'] != user['id']:
                        return denied('Chamado não encontrado.', 404)
                if method not in ['GET', 'HEAD', 'OPTIONS']:
                    allowed = path in ['/api/tickets', '/api/auth/logout', '/api/auth/password'] or bool(re.fullmatch(r'/api/tickets/\d+/(comments|attachments)', path))
                    if method == 'DELETE' and re.fullmatch(r'/api/tickets/\d+/attachments/\d+', path):
                        attachment = db.execute('SELECT uploader_id FROM attachments WHERE id=?', (int(path.split('/')[-1]),)).fetchone()
                        allowed = bool(attachment and attachment['uploader_id'] == user['id'])
                    if not allowed:
                        return denied('Seu perfil não tem permissão para esta ação.')
            if user['role'] == 'agent' and method == 'DELETE' and path.startswith('/api/documents/'):
                return denied('Somente administradores podem excluir artigos.')
        context = actor.set(user)
        try:
            response = await call_next(request)
            response.headers['Cache-Control'] = 'no-store'
            return response
        finally:
            actor.reset(context)

    @app.post('/api/auth/login')
    def login(body: LoginInput, request: Request):
        email = body.email.strip().lower()
        key = token_hash(email + ':' + (request.client.host if request.client else 'local'))
        with database() as db:
            db.execute('DELETE FROM login_failures WHERE created_at<?', (time.time() - 900,))
            if db.execute('SELECT COUNT(*) FROM login_failures WHERE key=?', (key,)).fetchone()[0] >= 5:
                return denied('Muitas tentativas. Aguarde 15 minutos e tente novamente.', 429)
            row = db.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            # Use the same password work even for unknown accounts.
            valid = verify_password(body.password, row['password_hash'] if row else '0'*32 + ':' + '0'*128)
            if not row or not valid or not row['active']:
                db.execute('INSERT INTO login_failures VALUES(?,?)', (key, time.time()))
                return denied('E-mail ou senha inválidos.', 401)
            db.execute('DELETE FROM login_failures WHERE key=?', (key,))
            db.execute('DELETE FROM sessions WHERE expires_at<?', (time.time(),))
            if request.cookies.get('orbita_session'):
                db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash(request.cookies['orbita_session']),))
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)', (token_hash(token), row['id'], csrf, time.time() + 28800))
            response = JSONResponse({'user': public_user(row), 'csrf': csrf}, headers={'Cache-Control': 'no-store'})
            response.set_cookie('orbita_session', token, max_age=28800, httponly=True, samesite='strict', secure=os.getenv('COOKIE_SECURE') == '1')
            return response

    @app.get('/api/auth/me')
    def me(request: Request):
        return {'user': request.state.user, 'csrf': request.state.csrf}

    @app.post('/api/auth/logout')
    def logout(request: Request):
        with database() as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash(request.cookies.get('orbita_session', '')),))
        response = JSONResponse({'ok': True})
        response.delete_cookie('orbita_session')
        return response

    @app.post('/api/auth/password')
    def change_password(body: PasswordInput, request: Request):
        with database() as db:
            row = db.execute('SELECT * FROM users WHERE id=?', (request.state.user['id'],)).fetchone()
            if not verify_password(body.current_password, row['password_hash']):
                raise HTTPException(400, 'Senha atual incorreta.')
            db.execute('UPDATE users SET password_hash=? WHERE id=?', (password_hash(body.new_password), row['id']))
            db.execute('DELETE FROM sessions WHERE user_id=?', (row['id'],))
        return {'ok': True}

    @app.get('/api/users')
    def users():
        with database() as db:
            return [public_user(row) for row in db.execute('SELECT * FROM users ORDER BY name')]

    def validate_user(body):
        if len(body.name.strip()) < 2 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', body.email.strip()):
            raise HTTPException(422, 'Informe nome e e-mail válidos.')
        if body.password and len(body.password) < 10:
            raise HTTPException(422, 'A senha precisa ter pelo menos 10 caracteres.')

    @app.post('/api/users', status_code=201)
    def create_user(body: UserInput):
        validate_user(body)
        if not body.password:
            raise HTTPException(422, 'Informe uma senha com pelo menos 10 caracteres.')
        with database() as db:
            if db.execute('SELECT 1 FROM users WHERE email=?', (body.email.strip().lower(),)).fetchone():
                raise HTTPException(409, 'Este e-mail já está cadastrado.')
            cursor = db.execute('INSERT INTO users(name,email,role,active,password_hash) VALUES(?,?,?,?,?)', (body.name.strip(), body.email.strip().lower(), body.role, int(body.active), password_hash(body.password)))
            return public_user(db.execute('SELECT * FROM users WHERE id=?', (cursor.lastrowid,)).fetchone())

    @app.put('/api/users/{user_id}')
    def edit_user(user_id: int, body: UserInput):
        validate_user(body)
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Usuário não encontrado.')
            if row['role'] == 'admin' and row['active'] and (body.role != 'admin' or not body.active) and db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0] <= 1:
                raise HTTPException(409, 'Mantenha pelo menos um administrador ativo.')
            if db.execute('SELECT 1 FROM users WHERE email=? AND id<>?', (body.email.strip().lower(), user_id)).fetchone():
                raise HTTPException(409, 'Este e-mail já está cadastrado.')
            db.execute('UPDATE users SET name=?,email=?,role=?,active=?,password_hash=? WHERE id=?', (body.name.strip(), body.email.strip().lower(), body.role, int(body.active), password_hash(body.password) if body.password else row['password_hash'], user_id))
            db.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))
        return {'ok': True}
