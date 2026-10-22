"""API/data regressions exercising real SQLite and the REST tool boundary."""
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.db import Database
from app.main import create_app
from app.knowledge import retrieve_grounded

ROOT=Path(__file__).resolve().parents[2]
class RegressionTests(unittest.TestCase):
    def setUp(self):
        root=ROOT/'runtime'/'tests'; root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root); self.path=Path(self.temp.name)/'test.db'
        with patch.dict(os.environ,{'AI_MODE':'local'}): self.app=create_app(self.path,ROOT/'mock-data')
        self.client=TestClient(self.app); self.db=self.app.state.db
    def tearDown(self):
        self.client.close(); self.temp.cleanup()
    def chat(self,message,key='a',session='visit'):
        return self.client.post('/api/chat',json=dict(message=message,request_id=key,session_id=session))

    def test_reported_new_chat_visit_process(self):
        before=self.client.get('/api/bookings').json()
        result=self.chat('我到医院的流程').json()
        self.assertEqual(result['intent'],'visit_flow')
        self.assertIn('出發前',result['reply']); self.assertIn('On arrival',result['reply'])
        self.assertIn('資料中沒有',result['reply']); self.assertNotIn('現有資料無法回答',result['reply'])
        self.assertNotIn('Known allergies: Penicillin',result['reply']); self.assertNotIn('可討論的服務',result['reply'])
        self.assertIsNone(result['booking']); self.assertEqual(result['draft'],{})
        self.assertEqual(before,self.client.get('/api/bookings').json())
        self.assertEqual(result['tool_trace'][0]['tool'],'GET /api/bookings')

    def test_visit_with_upcoming_booking_has_grounded_details(self):
        with self.db.connect() as c:
            c.execute("UPDATE patient_bookings SET booking_date='2035-11-08' WHERE booking_id='B1001'")
            c.execute("UPDATE patient_bookings SET status='Completed' WHERE booking_id='B1004'")
        r=self.chat('我到醫院的流程').json()
        self.assertIn('B1001',r['reply']); self.assertIn('123 Medical',r['reply'])
        self.assertIn('如已安排抽血',r['reply']); self.assertEqual({s['id'] for s in r['sources']},{'C001','T001'})

    def test_visit_during_draft_does_not_book_or_discard(self):
        first=self.chat('Book D101 T001').json()
        r=self.chat('我到医院的流程','b').json()
        self.assertEqual(r['draft'],first['draft']); self.assertIsNone(r['booking'])
        booked=self.chat('2035-11-08 09:30','c').json()
        self.assertIsNotNone(booked['booking'])

    def test_new_session_does_not_inherit_draft(self):
        self.chat('Book D101 T001')
        r=self.chat('我到医院的流程',session='new').json()
        self.assertEqual(r['draft'],{})

    def test_visit_with_no_future_booking(self):
        with self.db.connect() as c: c.execute("UPDATE patient_bookings SET status='Completed' WHERE patient_id='P001'")
        r=self.chat('check-in').json()
        self.assertIn('no upcoming',r['reply']); self.assertEqual(r['sources'],[])

    def test_hours_preparation_and_price_retrieval(self):
        for q,expected,excluded in [('診所營業時間','08:00','Penicillin'),('T001 就診準備','如已安排抽血','對應醫生'),('T003 多少钱','200','Penicillin')]:
            with self.subTest(q=q):
                reply=self.chat(q,key=str(len(q)),session=q.encode().hex()[:60]).json()['reply']
                self.assertIn(expected,reply); self.assertNotIn(excluded,reply)

    def test_health_catalog_and_static_frontend(self):
        self.assertEqual(self.client.get('/api/health').json()['mode'],'local')
        self.assertEqual(set(self.client.get('/api/catalog').json()),{'clinics','doctors','treatments'})
        if (ROOT/'frontend'/'dist').exists():
            self.assertIn('text/html',self.client.get('/').headers['content-type'])

    def test_readme_symptom_query_excludes_auxiliary_word_matches(self):
        before = self.client.get('/api/bookings').json()
        result = self.chat('I have a skin rash. What service is available?').json()
        self.assertEqual(result['intent'], 'knowledge')
        self.assertEqual({s['id'] for s in result['sources']}, {'D103', 'T003'})
        self.assertIn('Dermatology', result['reply'])
        self.assertNotIn('Flu Shot', result['reply'])
        self.assertEqual(self.client.get('/api/bookings').json(), before)
        # Ignoring the auxiliary verb must not suppress an explicit flu request.
        flu = self.chat('Do you have flu shots?', key='flu').json()
        self.assertIn('T004', {s['id'] for s in flu['sources']})

    def test_database_rollback_and_foreign_keys(self):
        with self.assertRaises(RuntimeError):
            with self.db.connect() as c:
                c.execute("UPDATE patients SET first_name='Changed' WHERE patient_id='P001'")
                raise RuntimeError('rollback')
        self.assertEqual(self.db.profile()['first_name'],'John')
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.connect() as c: c.execute("INSERT INTO booking_keys VALUES('bad','{}','missing')")

    def test_session_and_request_save_is_atomic(self):
        original={'draft':{},'active':False,'history':[]}
        self.db.save('atomic',original,'key','message',{'reply':'ok'})
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.save('atomic',{'draft':{'doctor_id':'D104'}},'key','different',{})
        self.assertEqual(self.db.state('atomic'),original)
        self.assertEqual(json.loads(self.db.rows('SELECT response FROM requests WHERE id=?',('key',))[0]['response']),{'reply':'ok'})

    def test_seed_rejects_bad_headers(self):
        data=Path(self.temp.name)/'data'; shutil.copytree(ROOT/'mock-data',data)
        (data/'clinics.csv').write_text('wrong\nvalue\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'CSV schema'): Database(Path(self.temp.name)/'invalid.db',data)

    def test_history_is_patient_scoped_and_bounded(self):
        self.assertTrue(all(h['patient_id']=='P001' for h in self.db.profile()['history']))
        for i in range(11): self.chat('clinic hours',key=str(i))
        self.assertEqual(len(self.db.state('visit')['history']),20)

    def test_database_error_does_not_expose_internal_details(self):
        with patch.object(self.db,'profile',side_effect=sqlite3.OperationalError('private path')):
            r=self.client.get('/api/profile')
        self.assertEqual(r.status_code,503); self.assertNotIn('private path',r.text)

    def test_model_id_retrieval_includes_only_related_evidence(self):
        sources=retrieve_grounded(self.db,'D103 T003 dermatology preparation')
        self.assertEqual({s['id'] for s in sources},{'D103','T003','C002'})
        self.assertEqual(retrieve_grounded(self.db,'T999'),[])
        self.assertTrue(retrieve_grounded(self.db,'skin rash'))
