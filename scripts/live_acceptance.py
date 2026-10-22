"""Opt-in paid live-model acceptance. Isolated DB, no mocks, transcript report."""
import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--env-file',type=Path,default=ROOT/'.env')
    parser.add_argument('--summary',action='store_true')
    parser.add_argument('--model',help='Explicit model override for reproducible comparisons')
    args=parser.parse_args()
    load_dotenv(args.env_file,override=True)
    load_dotenv(args.env_file.with_name('.env.local'),override=True)
    os.environ['AI_MODE']='llm'
    if args.model:
        os.environ['LLM_MODEL']=args.model
    from app.main import create_app
    from app.llm import configuration
    from fastapi.testclient import TestClient
    cfg=configuration()
    if not cfg['key'] or not cfg['model']: raise SystemExit('Live provider credentials/model required')
    folder=ROOT/'runtime'/'live-acceptance'/uuid.uuid4().hex
    folder.mkdir(parents=True)
    report={'started_at':datetime.now(timezone.utc).isoformat(),'provider':cfg['base'],'model':cfg['model'],
            'api_style':cfg['style'],'database':str(folder/'test.db'),'turns':[],'checks':[],'status':'running'}
    destination=folder/'report.json'
    print('REPORT '+str(destination),flush=True)
    app=create_app(folder/'test.db',ROOT/'mock-data')
    client=TestClient(app)
    def save(): destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    def check(name,condition):
        report['checks'].append({'name':name,'passed':bool(condition)})
        save()
        if not condition: raise AssertionError(name)
    def chat(message,intent,key,session='main'):
        response=client.post('/api/chat',json={'message':message,'session_id':session,'request_id':key})
        body=response.json()
        report['turns'].append({'user':message,'http_status':response.status_code,'result':body})
        save()
        print(key+' HTTP '+str(response.status_code)+' '+str(body.get('intent','error')),flush=True)
        check(key+' HTTP success',response.status_code==200)
        check(key+' intent',body['intent']==intent)
        check(key+' real routing',any(t['tool']=='LLM route_intent' for t in body['tool_trace']))
        check(key+' bilingual',bool(re.search('[\u4e00-\u9fff]',body['reply'])) and bool(re.search('[A-Za-z]{3}',body['reply'])))
        return body
    try:
        baseline=client.get('/api/bookings').json()
        r=chat('我到医院的流程','visit_flow','01-visit')
        check('visit does not book',r['booking'] is None and len(client.get('/api/bookings').json())==len(baseline))
        r=chat('我有花生過敏，想找合適的醫生諮詢，你推薦甚麼服務？','knowledge','02-allergy')
        check('allergy grounded recommendation','D101' in r['reply'] and 'T001' in r['reply'] and bool(r['sources']))
        r=chat('那位醫生的診金是多少？','knowledge','03-followup')
        check('contextual fee answer','150' in r['reply'])
        r=chat('我也想了解皮膚問題可以找誰，以及哪個服務適合諮詢。','knowledge','04-skin')
        check('skin recommendation','D103' in r['reply'] and 'T003' in r['reply'])
        r=chat('先幫我查一下已經有哪些預約。','bookings','05-existing')
        check('existing bookings from REST',all(b['booking_id'] in r['reply'] for b in baseline))
        r=chat('我想新增一個預約，先讓我確認醫生和服務。','book','06-start')
        check('missing slots do not write',r['booking'] is None)
        r=chat('就選剛才推薦的皮膚科醫生和皮膚科諮詢。','book','07-select')
        check('resolves earlier recommendation',r['draft'].get('doctor_id')=='D103' and r['draft'].get('treatment_id')=='T003')
        draft=dict(r['draft'])
        r=chat('去之前皮膚需要做甚麼準備？','knowledge','08-interleave')
        check('interleaving preserves draft',r['draft']==draft)
        final_message='2035 年 11 月 8 日上午九點半，按診所當地時間。'
        r=chat(final_message,'book','09-create')
        booking=r['booking']
        check('booking actually created',booking is not None)
        check('natural date/time parsed',booking['booking_date']=='2035-11-08' and booking['booking_time']=='09:30:00')
        rows=client.get('/api/bookings').json()
        check('live list increments',len(rows)==len(baseline)+1 and any(b['booking_id']==booking['booking_id'] for b in rows))
        persisted=app.state.db.rows('SELECT * FROM patient_bookings WHERE booking_id=?',(booking['booking_id'],))
        check('SQL record exists',len(persisted)==1)
        retry=client.post('/api/chat',json={'message':final_message,'session_id':'main','request_id':'09-create'}).json()
        check('exact retry no duplicate',retry==r and len(client.get('/api/bookings').json())==len(rows))
        r=chat('幫我預約 D103 的 T001，2035-12-01 10:00。','book','10-invalid','invalid')
        check('mismatch rejected',r['booking'] is None and any(t['status']=='rejected' for t in r['tool_trace']))
        r=chat('把醫生改成 D101。','book','11-correct','invalid')
        check('correction succeeds',r['booking'] is not None and r['booking']['doctor_id']=='D101')
        r=chat('我要預約，醫生還沒選好。','book','12-draft','cancel')
        r=chat('先不約了，放棄這個草稿。','cancel_draft','13-cancel','cancel')
        check('cancel only draft',r['draft']=={} and len(client.get('/api/bookings').json())==len(baseline)+2)
        client.close();client=TestClient(create_app(folder/'test.db',ROOT/'mock-data'))
        check('restart persistence',any(b['booking_id']==booking['booking_id'] for b in client.get('/api/bookings').json()))
        r=chat('請列出我的預約紀錄。','bookings','14-restarted','restart')
        check('model sees persisted booking',booking['booking_id'] in r['reply'])
        if args.summary:
            transcript='病人：我頭痛兩天。醫生：目前診斷為緊張型頭痛。醫生：這次沒有開藥。醫生：請記錄症狀，下週回診。'
            response=client.post('/api/transcripts/summarize',json={'transcript':transcript})
            report['summary']={'http_status':response.status_code,'result':response.json()}
            check('summary success',response.status_code==200)
            summary=response.json()['summary']
            check('summary has four fields',set(summary)=={'chief_complaint','diagnosis','medication','doctor_instructions'})
            check('summary real call',response.json()['tool_trace'][0]['tool']=='LLM summarize_transcript')
            response=client.post('/api/transcripts/summarize',json={'transcript':'病人：我想問診所幾點開門。'})
            report['summary_missing']={'http_status':response.status_code,'result':response.json()}
            check('missing medical facts remain null',response.status_code==200 and all(v is None for v in response.json()['summary'].values()))
        report['status']='passed'
    except Exception as error:
        report['status']='failed';report['failure_type']=type(error).__name__;report['failure']=str(error)[:300]
        raise
    finally:
        client.close();report['finished_at']=datetime.now(timezone.utc).isoformat();save()
        print('RESULT '+report['status']+' '+str(len(report['checks']))+' checks',flush=True)

if __name__=='__main__': main()
