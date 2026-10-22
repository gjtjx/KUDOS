"""Unit contracts: validation, routing, answer selection, localization and LLM transport."""
import csv
import json
import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from pydantic import ValidationError
from app.agent import Agent
from app.answers import is_visit_flow, local_answer, visit_answer, upcoming_bookings
from app.knowledge import retrieve
from app.localization import normalize_input, translated_value, localized_booking
from app.models import ChatInput, BookingInput

DATA = Path(__file__).resolve().parents[2] / 'mock-data'
def catalog():
    result = {}
    for table in ('clinics', 'doctors', 'treatments'):
        with (DATA/(table+'.csv')).open(encoding='utf-8-sig',newline='') as f:
            result[table] = list(csv.DictReader(f))
    return result

def source(table, row):
    key = {'clinics':'clinic_id','doctors':'doctor_id','treatments':'treatment_id'}[table]
    return {'source':table+'.csv','id':row[key],'data':row}

class ModelTests(unittest.TestCase):
    def test_chat_trim_and_default_patient(self):
        body=ChatInput(message=' hello ',session_id='a',request_id='b')
        self.assertEqual(body.message,'hello'); self.assertEqual(body.patient_id,'P001')

    def test_chat_rejects_invalid_fields(self):
        for change in ({'message':' '},{'message':'x'*4001},{'session_id':'x:y'},{'request_id':''},{'patient_id':'P002'},{'unknown':True}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                ChatInput(**({'message':'hi','session_id':'a','request_id':'b'}|change))

    def test_booking_time_and_identifiers(self):
        base=dict(doctor_id='D101',treatment_id='T001',booking_date='2035-11-08',booking_time='09:30',request_id='a')
        self.assertEqual(BookingInput(**base).booking_time.hour,9)
        for change in ({'booking_time':'09:30:01'},{'booking_time':'09:30:00.001'},{'booking_time':'09:30Z'},{'booking_time':'24:00'},{'doctor_id':'d101'},{'treatment_id':'T1'},{'notes':'x'*1001},{'booking_date':'2035-02-30'},{'extra':1}):
            with self.subTest(change=change), self.assertRaises(ValidationError): BookingInput(**(base|change))

class AnswerTests(unittest.TestCase):
    def setUp(self):
        self.catalog=catalog(); self.profile={'known_allergies':'Penicillin, Peanuts'}

    def test_visit_flow_language_variants(self):
        for q in ('我到医院的流程','我到醫院的流程','就診流程','看病的步骤','到了診所如何報到','What should I expect when visiting the clinic?','What happens when I arrive?','check-in','Guide me through my visit'):
            with self.subTest(q=q): self.assertTrue(is_visit_flow(q))

    def test_other_questions_are_not_visit_flow(self):
        for q in ('取消预约','cancel booking process','Book D101 T001','診所營業時間','医院地址'):
            with self.subTest(q=q): self.assertFalse(is_visit_flow(q))

    def test_unknown_answer_has_no_unrelated_allergy_or_recommendation(self):
        text=local_answer('unknownzz',[],self.profile,self.catalog)
        self.assertNotIn('Penicillin',text); self.assertNotIn('T001',text)
        self.assertIn('Please specify',text)

    def test_hours_only_shows_relevant_clinic_fields(self):
        sources=[source('clinics',self.catalog['clinics'][0]),source('treatments',self.catalog['treatments'][0])]
        text=local_answer('營業時間',sources,self.profile,self.catalog)
        self.assertIn('08:00',text); self.assertNotIn('Penicillin',text)
        self.assertNotIn('T001',text); self.assertNotIn('取消',text)

    def test_preparation_keeps_conditional_fasting(self):
        text=local_answer('T001 就診準備',[source('treatments',self.catalog['treatments'][0])],self.profile,self.catalog)
        self.assertIn('如已安排抽血',text); self.assertNotIn('對應醫生',text)

    def test_explicit_clinic_policy_does_not_mix_clinics(self):
        text=local_answer('C002 cancel policy',[source('clinics',c) for c in self.catalog['clinics']],self.profile,self.catalog)
        self.assertIn('12 小時',text); self.assertNotIn('24 小時',text); self.assertIn('cannot cancel',text)

    def test_price_and_address_field_selection(self):
        for q,table,expected,excluded in [('T003 price','treatments','200','pre_treatment_instructions'),('C001 address','clinics','Medical Center','operating_hours')]:
            text=local_answer(q,[source(table,r) for r in self.catalog[table]],self.profile,self.catalog)
            self.assertIn(expected,text); self.assertNotIn(excluded,text)

    def test_service_recommends_matching_doctor(self):
        text=local_answer('skin',[source('treatments',self.catalog['treatments'][2])],self.profile,self.catalog)
        self.assertIn('D103',text); self.assertNotIn('D101',text)

    def test_allergy_does_not_invent_service(self):
        text=local_answer('花生過敏',[source('treatments',self.catalog['treatments'][0])],self.profile,self.catalog)
        self.assertIn('no dedicated allergy',text); self.assertIn('D101',text)

    def test_visit_no_booking_does_not_invent_clinic_policy(self):
        text,sources=visit_answer([],self.catalog,Agent.booking_text)
        self.assertIn('報到',text); self.assertIn('general orientation',text)
        self.assertIn('no upcoming',text); self.assertEqual(sources,[])
        self.assertNotIn('30 minutes',text)

    def test_next_booking_uses_actual_instant_and_confirmed_status(self):
        def b(zone,time,status='Confirmed'):
            return dict(timezone=zone,booking_date='2035-11-08',booking_time=time,status=status)
        la=b('America/Los_Angeles','09:00'); ny=b('America/New_York','10:00')
        result=upcoming_bookings([la,ny,b('America/New_York','08:00','Cancelled')],datetime(2035,11,8,14,tzinfo=timezone.utc))
        self.assertEqual(result,[ny,la])
        self.assertEqual(upcoming_bookings([ny],datetime(2036,1,1,tzinfo=timezone.utc)),[])

class LocalizationTests(unittest.TestCase):
    def test_input_normalization_preserves_ids(self):
        self.assertEqual(normalize_input('幫我預約 D101 體檢'),'帮我预约 D101 体检')
    def test_translation_fallback_and_numeric_value(self):
        self.assertIn('一般健康檢查 /',translated_value('T001','treatment_name','General Health Checkup'))
        self.assertEqual(translated_value('X','price',150),'150')
    def test_booking_localization_preserves_original(self):
        b={'treatment_id':'T001','treatment_name':'General Health Checkup','pre_treatment_instructions':'original','status':'Confirmed'}
        got=localized_booking(b)
        self.assertEqual(got['treatment_name'],'General Health Checkup')
        self.assertIn('已確認',got['status_label'])

class RetrievalTests(unittest.TestCase):
    def test_empty_nonmatching_query_skips_database(self):
        db=MagicMock(); self.assertEqual(retrieve(db,'！！！'),[]); db.rows.assert_not_called()
    def test_expansion_and_parameterized_fts(self):
        db=MagicMock(); db.rows.return_value=[]
        retrieve(db,'皮膚過敏 " OR drop')
        sql,params=db.rows.call_args.args
        self.assertNotIn('drop',sql); self.assertIn('dermatology',params[0]); self.assertIn('checkup',params[0])
    def test_source_deserialization(self):
        db=MagicMock(); db.rows.return_value=[{'source':'clinics.csv','record_id':'C001','content':'{"clinic_id":"C001"}'}]
        self.assertEqual(retrieve(db,'C001')[0]['data'],{'clinic_id':'C001'})

class RoutingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        with patch.dict(os.environ,{'AI_MODE':'local'}): self.agent=Agent(None,None)
        self.state={'draft':{},'active':False,'history':[]}

    async def test_intents_and_slot_extraction(self):
        for message,intent in [('我到医院的流程','visit_flow'),('我的下一次預約','bookings'),('Book a new appointment','book'),('取消草稿','cancel_draft'),('cancel existing appointment','knowledge'),('clinic hours','knowledge')]:
            with self.subTest(message=message): self.assertEqual((await self.agent.route(message,self.state,{}))['intent'],intent)
        result=await self.agent.route('Book D101 T001 2035-11-08 9:30 pm',self.state,{})
        self.assertEqual([result[s] for s in ('doctor_id','treatment_id','booking_date','booking_time')],['D101','T001','2035-11-08','21:30'])

    async def test_am_pm_boundaries(self):
        for t,expected in [('12 am','00:00'),('12 pm','12:00'),('1 pm','13:00'),('09:30','09:30')]:
            with self.subTest(t=t): self.assertEqual((await self.agent.route('Book '+t,self.state,{}))['booking_time'],expected)
        with self.assertRaises(ValueError): await self.agent.route('Book 13 pm',self.state,{})

    async def test_draft_answers_and_unrelated_questions(self):
        self.state['active']=True
        self.assertEqual((await self.agent.route('D101',self.state,{}))['intent'],'book')
        self.assertEqual((await self.agent.route('我到醫院的流程',self.state,{}))['intent'],'visit_flow')
        self.assertEqual((await self.agent.route('clinic hours',self.state,{}))['intent'],'knowledge')

    async def test_aliases_and_tomorrow(self):
        result=await self.agent.route('Book Sarah checkup tomorrow',self.state,{})
        self.assertEqual(result['doctor_id'],'D101'); self.assertEqual(result['treatment_id'],'T001')
        self.assertRegex(result['booking_date'],r'^\d{4}-\d{2}-\d{2}$')

    async def test_malformed_llm_contract_rejected(self):
        self.agent.mode='llm'
        for name,args in [('wrong',{'intent':'book'}),('route_intent',[]),('route_intent',{'intent':'delete'}),('route_intent',{'intent':'book','doctor_id':123}),('route_intent',{'intent':'book','extra':True})]:
            self.agent.llm=AsyncMock(return_value={'tool_calls':[{'function':{'name':name,'arguments':json.dumps(args)}}]})
            with self.subTest(args=args),self.assertRaises(ValueError): await self.agent.route('hello',self.state,{})

    async def test_llm_http_contract_and_failure(self):
        response=httpx.Response(200,json={'choices':[{'message':{'content':'answer'}}]},request=httpx.Request('POST','https://example.test/chat/completions'))
        client=MagicMock(); client.__aenter__=AsyncMock(return_value=client); client.__aexit__=AsyncMock(return_value=False); client.post=AsyncMock(return_value=response)
        with patch.dict(os.environ,{'LLM_MODEL':'test-model','LLM_API_KEY':'test-only','LLM_BASE_URL':'https://example.test/'}),patch('app.agent.httpx.AsyncClient',return_value=client):
            self.assertEqual(await self.agent.llm([{'role':'user','content':'hello'}]),{'content':'answer'})
            args,kwargs=client.post.call_args
            self.assertEqual(args[0],'https://example.test/chat/completions'); self.assertNotIn('tools',kwargs['json'])
            await self.agent.llm([],tools=[{'type':'function'}]); self.assertEqual(client.post.call_args.kwargs['json']['tool_choice']['function']['name'],'route_intent')
            client.post.return_value=httpx.Response(429,request=httpx.Request('POST',args[0]))
            with self.assertRaises(httpx.HTTPStatusError): await self.agent.llm([])

    def test_mode_configuration_validation(self):
        with patch.dict(os.environ,{'AI_MODE':'unknown'}),self.assertRaises(ValueError): Agent(None,None)
        with patch.dict(os.environ,{'AI_MODE':'llm','LLM_API_KEY':'','LLM_MODEL':''}),self.assertRaises(ValueError): Agent(None,None)
