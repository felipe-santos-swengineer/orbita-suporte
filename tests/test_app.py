import os
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

temp = tempfile.TemporaryDirectory()
os.environ['DATABASE_PATH'] = os.path.join(temp.name, 'test.db')
from fastapi.testclient import TestClient
from backend import main


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        login=self.client.post('/api/auth/login',json={'email':'admin@orbita.local','password':'Orbita@Admin123'})
        self.client.headers['X-CSRF-Token']=login.json()['csrf']
        with main.database() as db:
            for row in db.execute('SELECT storage_name FROM attachments'):
                (main.upload_dir()/row['storage_name']).unlink(missing_ok=True)
            for table in ['attachments', 'events', 'tickets', 'documents']:
                db.execute('DELETE FROM ' + table)

    def ticket(self):
        response = self.client.post('/api/tickets', json={
            'title': 'VPN indisponível', 'requester': 'Ana',
            'description': 'A VPN apresenta erro de conexão para toda a equipe.'})
        self.assertEqual(response.status_code, 201)
        return response.json()['id']

    def test_review_workflow_and_sources(self):
        self.client.post('/api/documents', json={'title': 'Conexão VPN', 'content': 'Para erros na VPN, verifique a conexão de rede e registre a mensagem de erro.'})
        ticket_id = self.ticket()
        self.assertTrue(self.client.get('/api/documents?q=VPN').json())
        payload = {'message': {'content': '{"category":"Rede","priority":"Alta","reason":"Equipe afetada.","response":"Informe a mensagem de erro da VPN."}'}}
        with patch.object(main, 'ollama', return_value=payload):
            result = self.client.post(f'/api/tickets/{ticket_id}/analyze')
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()['sources'])
        self.assertEqual(self.client.get(f'/api/tickets/{ticket_id}').json()['category'], 'Não classificado')
        review = {'decision': 'approved', 'category': 'Rede', 'priority': 'Alta', 'response': 'Resposta editada pelo atendente.'}
        self.assertEqual(self.client.post(f'/api/tickets/{ticket_id}/review', json=review).status_code, 200)
        ticket = self.client.get(f'/api/tickets/{ticket_id}').json()
        self.assertEqual(ticket['category'], 'Rede')
        self.assertEqual(ticket['events'][0]['content'], review['response'])
        self.assertEqual(self.client.post(f'/api/tickets/{ticket_id}/review', json=review).status_code, 409)

    def test_offline_keeps_ticket(self):
        ticket_id = self.ticket()
        with patch.object(main, 'ollama', side_effect=ConnectionError):
            self.assertEqual(self.client.post(f'/api/tickets/{ticket_id}/analyze').status_code, 503)
            self.assertFalse(self.client.get('/api/health').json()['online'])
        self.assertIsNone(self.client.get(f'/api/tickets/{ticket_id}').json()['analysis'])

    def test_rejection_and_validation(self):
        ticket_id = self.ticket()
        with main.database() as db:
            db.execute('UPDATE tickets SET analysis=? WHERE id=?', ('{"review":"pending"}', ticket_id))
        review = {'decision': 'rejected', 'response': '', 'category': 'Outros', 'priority': 'Baixa'}
        self.assertEqual(self.client.post(f'/api/tickets/{ticket_id}/review', json=review).status_code, 200)
        self.assertEqual(self.client.get(f'/api/tickets/{ticket_id}').json()['category'], 'Não classificado')
        self.assertEqual(self.client.patch(f'/api/tickets/{ticket_id}/status', json={'status':'Inválido'}).status_code, 422)
        self.assertEqual(self.client.get('/api/tickets/9999').status_code, 404)

    def test_invalid_model_output_is_not_saved(self):
        ticket_id = self.ticket()
        with patch.object(main, 'ollama', return_value={'message': {'content': '{"category":"inventada"}'}}):
            self.assertEqual(self.client.post(f'/api/tickets/{ticket_id}/analyze').status_code, 503)
        self.assertIsNone(self.client.get(f'/api/tickets/{ticket_id}').json()['analysis'])

    def test_actionable_ollama_errors(self):
        ticket_id = self.ticket()
        cases = [
            (urllib.error.URLError('connection refused'), 503, 'ollama serve'),
            (urllib.error.HTTPError('/api/chat', 404, 'missing model', {}, None), 503, 'ollama pull'),
            (TimeoutError(), 504, 'OLLAMA_TIMEOUT'),
        ]
        for failure, status, message in cases:
            with self.subTest(message=message), patch.object(main, 'ollama', side_effect=failure):
                result = self.client.post(f'/api/tickets/{ticket_id}/analyze')
                self.assertEqual(result.status_code, status)
                self.assertIn(message, result.json()['detail'])

    def test_no_sources_requires_triage(self):
        ticket_id = self.ticket()
        payload = {'message': {'content': '{"category":"Rede","priority":"Alta","reason":"Equipe afetada.","response":"Reinicie todos os servidores."}'}}
        with patch.object(main, 'ollama', return_value=payload):
            result = self.client.post(f'/api/tickets/{ticket_id}/analyze').json()
        self.assertIn('mensagem de erro', result['response'])
        self.assertNotIn('Reinicie', result['response'])

    def test_assignment_comments_and_validation(self):
        ticket_id = self.ticket()
        result = self.client.patch(f'/api/tickets/{ticket_id}/assignment', json={'assignee': '  Felipe  ', 'priority': 'Crítica'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['assignee'], 'Felipe')
        self.assertEqual(result.json()['sla']['hours'], 2)
        comment = {'author': 'Ana', 'content': 'Erro persiste após nova tentativa.'}
        self.assertEqual(self.client.post(f'/api/tickets/{ticket_id}/comments', json=comment).status_code, 201)
        detail = self.client.get(f'/api/tickets/{ticket_id}').json()
        self.assertEqual(detail['events'][0]['author'], 'Administrador Demo')
        self.assertEqual(detail['events'][0]['content'], comment['content'])
        self.assertEqual(self.client.post(f'/api/tickets/{ticket_id}/comments', json={'author':'  ', 'content':' '}).status_code, 422)
        self.assertEqual(self.client.post('/api/tickets/999/comments', json=comment).status_code, 404)
        self.client.patch(f'/api/tickets/{ticket_id}/assignment', json={'assignee':'', 'priority':'Alta'})
        self.assertEqual(self.client.get('/api/tickets').json()[0]['assignee'], '')

    def test_sla_boundaries_and_resolution(self):
        start = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
        ticket = {'created_at':start.isoformat(), 'priority':'Crítica', 'status':'Aberto', 'resolved_at':None}
        for hours, state in [(0,'on_track'),(1.7,'warning'),(2,'warning'),(2.1,'overdue')]:
            self.assertEqual(main.sla(ticket, start+timedelta(hours=hours))['state'], state)
        ticket.update(status='Resolvido', resolved_at=(start+timedelta(hours=1)).isoformat())
        self.assertEqual(main.sla(ticket, start+timedelta(days=100))['state'], 'met')
        ticket['resolved_at']=(start+timedelta(hours=3)).isoformat()
        self.assertEqual(main.sla(ticket)['state'], 'breached')

    def test_resolve_reopen_keeps_original_deadline(self):
        ticket_id=self.ticket()
        due=self.client.get(f'/api/tickets/{ticket_id}').json()['sla']['due_at']
        self.client.patch(f'/api/tickets/{ticket_id}/status', json={'status':'Resolvido'})
        resolved=self.client.get(f'/api/tickets/{ticket_id}').json()
        self.assertIsNotNone(resolved['resolved_at'])
        self.client.patch(f'/api/tickets/{ticket_id}/status', json={'status':'Resolvido'})
        self.assertEqual(self.client.get(f'/api/tickets/{ticket_id}').json()['resolved_at'], resolved['resolved_at'])
        self.client.patch(f'/api/tickets/{ticket_id}/status', json={'status':'Em análise'})
        reopened=self.client.get(f'/api/tickets/{ticket_id}').json()
        self.assertIsNone(reopened['resolved_at'])
        self.assertEqual(reopened['sla']['due_at'], due)

    def test_legacy_database_migration(self):
        legacy=os.path.join(temp.name, 'legacy.db')
        import sqlite3
        with sqlite3.connect(legacy) as db:
            db.executescript('DROP TABLE IF EXISTS tickets; DROP TABLE IF EXISTS events; CREATE TABLE tickets(id INTEGER PRIMARY KEY,title TEXT,description TEXT,requester TEXT,status TEXT,category TEXT,priority TEXT,analysis TEXT,created_at TEXT); CREATE TABLE events(id INTEGER PRIMARY KEY,ticket_id INTEGER,kind TEXT,content TEXT,created_at TEXT);')
            db.execute("INSERT INTO tickets VALUES(1,'Legado','Descrição','Ana','Resolvido','Rede','Alta',NULL,?)", (main.now(),))
        with patch.object(main, 'DB', legacy):
            main.init_db()
            main.init_db()
            with main.database() as db:
                ticket=main.get_ticket(db,1)
            self.assertEqual(ticket['title'],'Legado')
            self.assertEqual(ticket['assignee'],'')
            self.assertIsNotNone(ticket['resolved_at'])

    def test_knowledge_edit_search_and_category(self):
        body={'title':'Roteiro de VPN', 'content':'Colete o código de erro e o horário da falha na conexão.', 'category':'Rede', 'tags':'remoto, túnel'}
        response=self.client.post('/api/documents',json=body)
        self.assertEqual(response.status_code,201)
        document_id=response.json()['id']
        self.assertEqual(len(self.client.get('/api/documents?q=tunel&category=Rede').json()),1)
        self.assertEqual(self.client.get('/api/documents?category=Acesso').json(),[])
        body.update(title='Roteiro atualizado',content='Colete a mensagem completa e encaminhe ao responsável de redes.')
        self.assertEqual(self.client.put(f'/api/documents/{document_id}',json=body).status_code,200)
        doc=self.client.get('/api/documents?q=atualizado').json()[0]
        self.assertEqual(doc['content'],body['content'])
        self.assertIsNotNone(doc['updated_at'])
        self.assertTrue(main.search('tunel'))
        self.assertEqual(self.client.put('/api/documents/999',json=body).status_code,404)
        self.assertEqual(self.client.post('/api/documents',json={**body,'content':' '*30}).status_code,422)

    def test_starter_articles_seed_once(self):
        seed_db=os.path.join(temp.name,'seed.db')
        if os.path.exists(seed_db):
            os.remove(seed_db)
        with patch.object(main,'DB',seed_db):
            main.init_db()
            self.assertEqual(len(main.documents()),6)
            main.init_db()
            self.assertEqual(len(main.documents()),6)
            with main.database() as db:
                db.execute('DELETE FROM documents')
            main.init_db()
            self.assertEqual(main.documents(),[])

    def test_attachment_upload_download_delete_and_ticket_isolation(self):
        ticket_id=self.ticket()
        result=self.client.post(f'/api/tickets/{ticket_id}/attachments',params={'filename':'../../evidência.txt'},content=b'Mensagem de erro: conexao indisponivel')
        self.assertEqual(result.status_code,201)
        attachment=result.json()
        self.assertEqual(attachment['filename'],'evidência.txt')
        url=f"/api/tickets/{ticket_id}/attachments/{attachment['id']}"
        download=self.client.get(url)
        self.assertEqual(download.content,b'Mensagem de erro: conexao indisponivel')
        self.assertIn('attachment',download.headers['content-disposition'])
        self.assertEqual(download.headers['x-content-type-options'],'nosniff')
        another=self.ticket()
        self.assertEqual(self.client.get(f"/api/tickets/{another}/attachments/{attachment['id']}").status_code,404)
        self.assertEqual(len(self.client.get(f'/api/tickets/{ticket_id}').json()['attachments']),1)
        self.assertEqual(self.client.delete(url).status_code,200)
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(list(main.upload_dir().iterdir()),[])

    def test_invalid_and_oversized_attachments_leave_no_files(self):
        ticket_id=self.ticket()
        endpoint=f'/api/tickets/{ticket_id}/attachments'
        for name,data,status in [('test.exe',b'abc',422),('test.png',b'not an image',422),('empty.txt',b'',422),('binary.log',b'\x00abc',422)]:
            with self.subTest(name=name):
                result=self.client.post(endpoint,params={'filename':name},content=data)
                self.assertEqual(result.status_code,status)
        with patch.object(main,'MAX_ATTACHMENT_SIZE',10):
            result=self.client.post(endpoint,params={'filename':'large.txt'},content=b'x'*11)
            self.assertEqual(result.status_code,413)
        self.assertEqual(list(main.upload_dir().iterdir()),[])
        self.assertEqual(self.client.post('/api/tickets/999/attachments',params={'filename':'a.txt'},content=b'hello').status_code,404)

    def test_solution_draft_requires_resolution_and_publication_for_search(self):
        ticket_id=self.ticket()
        with main.database() as db:
            main.event(db,ticket_id,'approved','Procedimento exclusivo: verifique o indicador orbitalteste e registre o resultado.')
            solution_id=db.execute("SELECT id FROM events WHERE kind='approved'").fetchone()[0]
        url=f'/api/tickets/{ticket_id}/solutions/{solution_id}/article'
        self.assertEqual(self.client.post(url).status_code,409)
        self.client.patch(f'/api/tickets/{ticket_id}/status',json={'status':'Resolvido'})
        draft=self.client.post(url).json()
        self.assertEqual(draft['status'],'draft')
        self.assertEqual(main.search('orbitalteste'),[])
        self.assertEqual(self.client.post(url).json()['id'],draft['id'])
        self.assertEqual(len(self.client.get('/api/documents').json()),1)
        self.assertEqual(draft['source_ticket_id'],ticket_id)
        self.assertIn('orbitalteste',draft['content'])
        body={key:draft[key] for key in ['title','content','category','tags']}
        body['status']='published'
        self.assertEqual(self.client.put(f"/api/documents/{draft['id']}",json=body).status_code,200)
        self.assertTrue(main.search('orbitalteste'))
        another=self.ticket()
        self.client.patch(f'/api/tickets/{another}/status',json={'status':'Resolvido'})
        self.assertEqual(self.client.post(f'/api/tickets/{another}/solutions/{solution_id}/article').status_code,404)

    def test_attachment_count_limit(self):
        ticket_id=self.ticket()
        with main.database() as db:
            for number in range(20):
                db.execute('INSERT INTO attachments(ticket_id,filename,storage_name,size,media_type,created_at) VALUES(?,?,?,?,?,?)',
                           (ticket_id,f'evidence-{number}.txt',f'fixture-{number}.txt',1,'text/plain',main.now()))
        result=self.client.post(f'/api/tickets/{ticket_id}/attachments',params={'filename':'extra.txt'},content=b'one too many')
        self.assertEqual(result.status_code,409)
        self.assertEqual(len(self.client.get(f'/api/tickets/{ticket_id}').json()['attachments']),20)
        self.assertEqual(list(main.upload_dir().iterdir()),[])

    def test_similar_cases_rank_filter_and_latest_approved_solution(self):
        original=self.ticket()
        related=self.ticket()
        unrelated=self.client.post('/api/tickets',json={'title':'Impressora sem papel','requester':'Bruno','description':'Bandeja vazia na impressora do escritório.'}).json()['id']
        self.client.patch(f'/api/tickets/{related}/status',json={'status':'Resolvido'})
        with main.database() as db:
            main.event(db,related,'approved','Primeira resposta aprovada.')
            main.event(db,related,'approved','Última resposta aprovada e editada.')
        results=self.client.get(f'/api/tickets/{original}/similar').json()
        self.assertEqual(results[0]['id'],related)
        self.assertEqual(results[0]['score'],100)
        self.assertEqual(results[0]['solution'],'Última resposta aprovada e editada.')
        self.assertNotIn(unrelated,[r['id'] for r in results])
        self.assertNotIn(original,[r['id'] for r in results])
        self.assertEqual(len(self.client.get(f'/api/tickets/{original}/similar?resolved_only=true').json()),1)
        self.client.patch(f'/api/tickets/{related}/status',json={'status':'Em análise'})
        self.assertEqual(self.client.get(f'/api/tickets/{original}/similar?resolved_only=true').json(),[])
        self.assertIsNone(self.client.get(f'/api/tickets/{original}/similar').json()[0]['solution'])
        self.assertEqual(self.client.get('/api/tickets/999/similar').status_code,404)

    def test_metrics_empty_and_invalid_period(self):
        result=self.client.get('/api/metrics').json()
        self.assertEqual(result['total'],0)
        self.assertIsNone(result['average_resolution_seconds'])
        self.assertIsNone(result['sla_met_percent'])
        self.assertEqual(result['by_status'],{})
        self.assertEqual(len(result['trend']),14)
        self.assertEqual(self.client.get('/api/metrics?days=8').status_code,422)

    def test_metrics_cohort_resolution_and_reopenings(self):
        fixed=datetime(2026,11,12,18,tzinfo=timezone.utc)
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):
                return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)
        resolved,overdue,reopened,old=[self.ticket() for _ in range(4)]
        for state in ['Resolvido','Em análise','Resolvido','Aberto']:
            self.client.patch(f'/api/tickets/{reopened}/status',json={'status':state})
        with main.database() as db:
            db.execute("UPDATE tickets SET created_at=?,resolved_at=?,status='Resolvido',category='Rede' WHERE id=?",((fixed-timedelta(days=3)).isoformat(),(fixed-timedelta(days=3,hours=-2)).isoformat(),resolved))
            db.execute("UPDATE tickets SET created_at=?,category='Rede' WHERE id=?",((fixed-timedelta(hours=30)).isoformat(),overdue))
            db.execute('UPDATE tickets SET created_at=? WHERE id=?',((fixed-timedelta(hours=1)).isoformat(),reopened))
            db.execute("UPDATE tickets SET created_at=?,resolved_at=?,status='Resolvido' WHERE id=?",((fixed-timedelta(days=100)).isoformat(),(fixed-timedelta(days=100,hours=-100)).isoformat(),old))
        with patch.object(main,'datetime',Clock):
            result=self.client.get('/api/metrics?days=30').json()
            all_time=self.client.get('/api/metrics?days=0').json()
        self.assertEqual(result['total'],3)
        self.assertEqual(result['resolved'],1)
        self.assertEqual(result['open'],2)
        self.assertEqual(result['overdue'],1)
        self.assertEqual(result['average_resolution_seconds'],7200)
        self.assertEqual(result['sla_met_percent'],100)
        self.assertEqual(result['reopened_tickets'],1)
        self.assertEqual(result['reopening_events'],2)
        self.assertEqual(result['by_category']['Rede'],2)
        self.assertEqual(result['trend'][-1]['opened'],1)
        self.assertEqual(all_time['total'],4)
        self.assertEqual(all_time['sla_met_percent'],50)
        self.assertEqual(all_time['average_resolution_seconds'],183600)


if __name__ == '__main__':
    unittest.main()
