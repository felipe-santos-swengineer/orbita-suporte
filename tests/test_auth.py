import os
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import main
from backend.auth import DEMO_ACCOUNTS, verify_password


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.db_patch=patch.object(main,'DB',os.path.join(self.folder.name,'auth.db'))
        self.db_patch.start()
        main.init_db()
        self.admin=self.login('admin@orbita.local','Orbita@Admin123')
        self.agent=self.login('atendente@orbita.local','Orbita@Atendente123')
        self.requester=self.login('solicitante@orbita.local','Orbita@Solicitante123')

    def tearDown(self):
        self.db_patch.stop()
        self.folder.cleanup()

    def login(self,email,password):
        client=TestClient(main.app)
        result=client.post('/api/auth/login',json={'email':email,'password':password})
        self.assertEqual(result.status_code,200)
        client.headers['X-CSRF-Token']=result.json()['csrf']
        return client

    def ticket(self,client):
        return client.post('/api/tickets',json={'title':'VPN sem acesso','description':'Conexão com a VPN indisponível desde cedo.','requester':'Identidade falsa'}).json()['id']

    def test_auth_session_csrf_expiration_and_logout(self):
        guest=TestClient(main.app)
        for path in ['/api/tickets','/api/documents','/api/metrics','/api/users','/api/health']:
            self.assertEqual(guest.get(path).status_code,401)
        response=guest.post('/api/auth/login',json={'email':'ADMIN@orbita.local','password':'Orbita@Admin123'})
        self.assertEqual(response.status_code,200)
        self.assertIn('HttpOnly',response.headers['set-cookie'])
        self.assertIn('SameSite=strict',response.headers['set-cookie'])
        self.assertEqual(guest.post('/api/auth/logout').status_code,403)
        guest.headers['X-CSRF-Token']=response.json()['csrf']
        self.assertEqual(guest.post('/api/auth/logout').status_code,200)
        self.assertEqual(guest.get('/api/auth/me').status_code,401)
        with main.database() as db:
            db.execute('UPDATE sessions SET expires_at=0')
        self.assertEqual(self.admin.get('/api/tickets').status_code,401)

    def test_requester_ownership_and_role_permissions(self):
        own=self.ticket(self.requester)
        other=self.ticket(self.agent)
        detail=self.requester.get(f'/api/tickets/{own}').json()
        self.assertEqual(detail['requester'],'Solicitante Demo')
        with main.database() as db:
            db.execute('UPDATE tickets SET analysis=? WHERE id=?', ('{"response":"Rascunho interno","review":"pending"}',own))
            main.event(db,own,'analysis','Nota interna de análise.')
        protected=self.requester.get(f'/api/tickets/{own}').json()
        self.assertIsNone(protected['analysis'])
        self.assertNotIn('analysis',[e['kind'] for e in protected['events']])
        self.assertEqual([t['id'] for t in self.requester.get('/api/tickets').json()],[own])
        self.assertEqual(self.requester.get(f'/api/tickets/{other}').status_code,404)
        for path in ['/api/users','/api/metrics',f'/api/tickets/{own}/similar']:
            self.assertEqual(self.requester.get(path).status_code,403)
        for path,method,body in [(f'/api/tickets/{own}/analyze','POST',{}),(f'/api/tickets/{own}/status','PATCH',{'status':'Resolvido'}),('/api/documents','POST',{'title':'Novo artigo','content':'Conteúdo suficiente para um novo artigo.'})]:
            self.assertEqual(self.requester.request(method,path,json=body).status_code,403)
        response=self.requester.post(f'/api/tickets/{own}/comments',json={'author':'Administrador','content':'Comentário legítimo.'})
        self.assertEqual(response.status_code,201)
        self.assertEqual(self.requester.get(f'/api/tickets/{own}').json()['events'][0]['author'],'Solicitante Demo')
        draft=self.admin.post('/api/documents',json={'title':'Artigo confidencial','content':'Rascunho para revisão interna do suporte.','status':'draft'}).json()['id']
        self.assertNotIn(draft,[d['id'] for d in self.requester.get('/api/documents').json()])
        self.assertEqual(self.agent.delete(f'/api/documents/{draft}').status_code,403)
        self.assertEqual(self.admin.delete(f'/api/documents/{draft}').status_code,200)

    def test_attachment_isolation(self):
        own=self.ticket(self.requester)
        other=self.ticket(self.admin)
        file=self.admin.post(f'/api/tickets/{other}/attachments?filename=test.txt',content=b'private file').json()
        url=f"/api/tickets/{other}/attachments/{file['id']}"
        self.assertEqual(self.requester.get(url).status_code,404)
        self.assertEqual(self.requester.delete(url).status_code,404)
        support=self.agent.post(f'/api/tickets/{own}/attachments?filename=help.txt',content=b'support evidence').json()
        self.assertEqual(self.requester.get(f"/api/tickets/{own}/attachments/{support['id']}").status_code,200)
        self.assertEqual(self.requester.delete(f"/api/tickets/{own}/attachments/{support['id']}").status_code,403)
        mine=self.requester.post(f'/api/tickets/{own}/attachments?filename=mine.txt',content=b'own evidence').json()
        self.assertEqual(self.requester.delete(f"/api/tickets/{own}/attachments/{mine['id']}").status_code,200)

    def test_admin_user_management_password_hashes_and_revocation(self):
        self.assertEqual(self.agent.get('/api/users').status_code,403)
        body={'name':'Nova Pessoa','email':'nova@orbita.local','role':'requester','password':'NovaSenhaSegura123','active':True}
        created=self.admin.post('/api/users',json=body)
        self.assertEqual(created.status_code,201)
        self.assertNotIn('password_hash',created.json())
        user_id=created.json()['id']
        person=self.login(body['email'],body['password'])
        body.update(active=False)
        self.assertEqual(self.admin.put(f'/api/users/{user_id}',json=body).status_code,200)
        self.assertEqual(person.get('/api/auth/me').status_code,401)
        self.assertEqual(TestClient(main.app).post('/api/auth/login',json={'email':body['email'],'password':body['password']}).status_code,401)
        admin=self.admin.get('/api/auth/me').json()['user']
        self.assertEqual(self.admin.put(f"/api/users/{admin['id']}",json={**admin,'active':False}).status_code,409)
        with main.database() as db:
            stored=db.execute('SELECT password_hash FROM users WHERE id=?',(user_id,)).fetchone()[0]
        self.assertNotEqual(stored,body['password'])
        self.assertTrue(verify_password(body['password'],stored))
        main.init_db()
        self.assertEqual(len(self.admin.get('/api/users').json()),4)

    def test_password_change_and_login_rate_limit(self):
        self.assertEqual(self.requester.post('/api/auth/password',json={'current_password':'wrong','new_password':'NovaSenhaSegura123'}).status_code,400)
        self.assertEqual(self.requester.post('/api/auth/password',json={'current_password':'Orbita@Solicitante123','new_password':'NovaSenhaSegura123'}).status_code,200)
        self.assertEqual(self.requester.get('/api/auth/me').status_code,401)
        self.login('solicitante@orbita.local','NovaSenhaSegura123')
        guest=TestClient(main.app)
        for _ in range(5):
            self.assertEqual(guest.post('/api/auth/login',json={'email':'unknown@orbita.local','password':'wrong'}).status_code,401)
        self.assertEqual(guest.post('/api/auth/login',json={'email':'unknown@orbita.local','password':'wrong'}).status_code,429)
        self.assertEqual(self.admin.post('/api/auth/logout',headers={'Origin':'https://untrusted.example'}).status_code,403)


if __name__=='__main__':
    unittest.main()
