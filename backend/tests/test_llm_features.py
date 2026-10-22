import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from fastapi.testclient import TestClient
from app.agent import Agent, TOOLS
from app.llm import complete, configuration, ProviderError
from app.main import create_app
from app.transcripts import summarize, FIELDS

ROOT=Path(__file__).resolve().parents[2]
TRACE={'tool':'LLM summarize_transcript','status':'ok','model':'test-model'}
def summary_result(**changes):
    args={**dict.fromkeys(FIELDS),'evidence':{k:[] for k in FIELDS}}
    args.update(changes)
    return {'tool_calls':[{'function':{'name':'summarize_transcript','arguments':json.dumps(args)}}]},dict(TRACE)

class LLMTransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'LLM_API_KEY':'unit-test-key','LLM_MODEL':'test-model','LLM_BASE_URL':'https://example.test/v1','LLM_API_STYLE':'responses','LLM_TOOL_CHOICE':'forced','LLM_STRICT_TOOLS':'true'})
        self.env.start();self.addCleanup(self.env.stop)
    def client(self,body,status=200):
        client=MagicMock();client.__aenter__=AsyncMock(return_value=client);client.__aexit__=AsyncMock(return_value=False)
        client.post=AsyncMock(return_value=httpx.Response(status,json=body,request=httpx.Request('POST','https://example.test/v1/responses')))
        return client
    async def test_responses_tool_and_text_parsing(self):
        client=self.client({'id':'resp-real-shape','status':'completed','model':'test-model','output':[{'type':'function_call','name':'route_intent','call_id':'call1','arguments':'{"intent":"knowledge"}'}],'usage':{'input_tokens':10,'output_tokens':5}})
        with patch('app.llm.httpx.AsyncClient',return_value=client):
            msg,trace=await complete([{'role':'user','content':'hi'}],TOOLS)
            self.assertEqual(msg['tool_calls'][0]['function']['name'],'route_intent');self.assertEqual(trace['input_tokens'],10)
            payload=client.post.call_args.kwargs['json'];self.assertIn('input',payload);self.assertEqual(payload['tools'][0]['name'],'route_intent');self.assertFalse(payload['store'])
            client.post.return_value=httpx.Response(200,json={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'hello'},{'type':'output_text','text':'world'}]}]},request=httpx.Request('POST','https://example.test'))
            msg,_=await complete([]);self.assertEqual(msg['content'],'hello\nworld')
    async def test_poe_compatible_auto_tools_still_requires_actual_call(self):
        os.environ.update(LLM_API_STYLE='chat_completions',LLM_TOOL_CHOICE='auto',LLM_STRICT_TOOLS='false')
        client=self.client({'choices':[{'message':{'content':'I did not call the tool'}}]})
        with patch('app.llm.httpx.AsyncClient',return_value=client),self.assertRaisesRegex(ProviderError,'invalid_tool_response'):
            await complete([],TOOLS)
        payload=client.post.call_args.kwargs['json'];self.assertEqual(payload['tool_choice'],'auto');self.assertNotIn('strict',payload['tools'][0]['function'])
        self.assertTrue(TOOLS[0]['function']['strict'])
    async def test_safe_provider_errors_and_incomplete_outputs(self):
        for status,code in [(401,'authentication_failed'),(402,'insufficient_credits'),(404,'model_or_endpoint_not_found'),(429,'rate_limited'),(500,'provider_unavailable')]:
            client=self.client({'error':{'message':'secret'}},status)
            with self.subTest(status=status),patch('app.llm.httpx.AsyncClient',return_value=client),self.assertRaisesRegex(ProviderError,code): await complete([])
        for body,code in [({'status':'incomplete'},'incomplete_response'),({'status':'completed','output':[]},'empty_response')]:
            with patch('app.llm.httpx.AsyncClient',return_value=self.client(body)),self.assertRaisesRegex(ProviderError,code): await complete([])
    def test_configuration_validation(self):
        for changes in ({'LLM_API_STYLE':'bad'},{'LLM_BASE_URL':'http://remote.test'},{'LLM_BASE_URL':'https://user:secret@example.test'},{'LLM_TIMEOUT_SECONDS':'0'},{'LLM_TOOL_CHOICE':'bad'}):
            with self.subTest(changes=changes),patch.dict(os.environ,changes),self.assertRaises(ValueError): configuration()
    async def test_visit_flow_in_llm_mode_never_uses_local_shortcut(self):
        os.environ['AI_MODE']='llm';agent=Agent(None,None)
        agent.llm=AsyncMock(return_value={'tool_calls':[{'function':{'name':'route_intent','arguments':json.dumps({'intent':'visit_flow'})}}]})
        result=await agent.route('我到医院的流程',{'draft':{},'history':[],'active':False},{})
        agent.llm.assert_awaited_once();self.assertEqual(result['intent'],'visit_flow')

class SummaryUnitTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_fields_are_null(self):
        with patch('app.transcripts.complete',AsyncMock(return_value=summary_result())):
            result=await summarize('病人：診所幾點開門？')
        self.assertTrue(all(v is None for v in result['summary'].values()))
    async def test_verbatim_evidence_and_bilingual_summary(self):
        evidence={k:[] for k in FIELDS};evidence['chief_complaint']=['頭痛兩天']
        with patch('app.transcripts.complete',AsyncMock(return_value=summary_result(chief_complaint='頭痛兩天 / Headache for two days',evidence=evidence))):
            result=await summarize('病人：頭痛兩天。')
        self.assertIn('Headache',result['summary']['chief_complaint']);self.assertIsNone(result['summary']['diagnosis'])
    async def test_fabricated_evidence_rejected(self):
        evidence={k:[] for k in FIELDS};evidence['diagnosis']=['診斷為流感']
        with patch('app.transcripts.complete',AsyncMock(return_value=summary_result(diagnosis='流感 / Flu',evidence=evidence))),self.assertRaisesRegex(ProviderError,'unverifiable_summary_quote'):
            await summarize('病人：我頭痛。')
    async def test_missing_evidence_and_invalid_schema_rejected(self):
        for result in (summary_result(diagnosis='Flu'),summary_result(extra=True)):
            with patch('app.transcripts.complete',AsyncMock(return_value=result)),self.assertRaises(ProviderError): await summarize('headache')
        with self.assertRaises(ValueError): await summarize(' ')

    async def test_one_bounded_repair_preserves_exact_evidence(self):
        bad={k:[] for k in FIELDS};bad['chief_complaint']=['頭痛了兩天']
        good={k:[] for k in FIELDS};good['chief_complaint']=['頭痛兩天']
        with patch('app.transcripts.complete',AsyncMock(side_effect=[summary_result(chief_complaint='頭痛兩天 / Headache for two days',evidence=bad),summary_result(chief_complaint='頭痛兩天 / Headache for two days',evidence=good)])) as provider:
            result=await summarize('病人：頭痛兩天。')
        self.assertEqual(provider.await_count,2);self.assertEqual(result['evidence']['chief_complaint'],['頭痛兩天'])
        self.assertEqual(len(result['tool_trace']),2)

    async def test_invalid_quotes_fail_after_two_calls(self):
        evidence={k:[] for k in FIELDS};evidence['diagnosis']=['不存在的診斷']
        with patch('app.transcripts.complete',AsyncMock(return_value=summary_result(diagnosis='unsupported',evidence=evidence))) as provider:
            with self.assertRaises(ProviderError): await summarize('病人：頭痛。')
        self.assertEqual(provider.await_count,2)

class SummaryAPITests(unittest.TestCase):
    def setUp(self):
        folder=ROOT/'runtime'/'tests';folder.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=folder)
        with patch.dict(os.environ,{'AI_MODE':'local'}): self.app=create_app(Path(self.temp.name)/'test.db',ROOT/'mock-data')
        self.client=TestClient(self.app)
    def tearDown(self): self.client.close();self.temp.cleanup()
    def test_validation_and_local_mode_refusal(self):
        for transcript in ('',' ','a'*16001): self.assertEqual(self.client.post('/api/transcripts/summarize',json={'transcript':transcript}).status_code,422)
        self.assertEqual(self.client.post('/api/transcripts/summarize',json={'transcript':'hello'}).status_code,503)
    def test_summary_has_no_booking_or_session_side_effects(self):
        self.app.state.agent.mode='llm';before=self.client.get('/api/bookings').json()
        with patch('app.transcripts.complete',AsyncMock(return_value=summary_result())):
            r=self.client.post('/api/transcripts/summarize',json={'transcript':'hello'})
        self.assertEqual(r.status_code,200);self.assertEqual(before,self.client.get('/api/bookings').json())
        self.assertEqual(self.app.state.db.rows('SELECT * FROM sessions'),[])
    def test_provider_failure_is_explicit(self):
        self.app.state.agent.mode='llm'
        for error in (ProviderError('insufficient_credits'),ValueError('internal detail')):
            with patch('app.main.summarize',AsyncMock(side_effect=error)):
                r=self.client.post('/api/transcripts/summarize',json={'transcript':'hello'})
            self.assertEqual(r.status_code,502);self.assertNotIn('internal detail',r.text)
