import React, { useState, useEffect, useRef } from 'react';


import { api } from './api';
import { replyDisplay } from './replyDisplay';
import TranscriptSummary from './TranscriptSummary';
import TracePanel from './TracePanel';
const uuid=()=>crypto.randomUUID();
const slotLabels={doctor_id:'醫生 / Doctor',treatment_id:'服務 / Treatment',booking_date:'日期 / Date',booking_time:'時間 / Time'};
const intentLabels={visit_flow:'就診流程 / Visit guide',knowledge:'知識查詢 / Knowledge',bookings:'預約查詢 / Booking history',patient_doctors:'我的醫生 / My doctors',book:'建立預約 / New booking',cancel_draft:'取消草稿 / Cancel draft'};
const suggestions=[
  ['我到醫院的流程','What should I expect when visiting the clinic?'],
  ['我有花生過敏，可以諮詢誰？','Who can I consult about my peanut allergy?'],
  ['我的下一次預約是甚麼時候？','When is my next appointment?'],
  ['幫我預約 D101 的 T001 體檢','Book a T001 checkup with D101'],
  ['診所的取消政策是甚麼？','What are the clinic cancellation policies?']
];
function Pair({zh,en}){return <><span lang="zh-Hant">{zh}</span><span className="translation" lang="en">{en}</span></>}
function errorText(e){return e.name==='TimeoutError'?'請求逾時，請重試。 / Request timed out. Please retry.':e.message==='Failed to fetch'?'無法連接伺服器，請檢查後端是否運行。 / Cannot connect to the server. Check that the backend is running.':e.message}
export default function App(){
  const [session,setSession]=useState(()=>localStorage.getItem('clinic-session')||uuid());
  const [messages,setMessages]=useState([]);
  const [input,setInput]=useState('');
  const [bookings,setBookings]=useState([]);
  const [profile,setProfile]=useState(null);
  const [health,setHealth]=useState(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [draft,setDraft]=useState({});
  const [retry,setRetry]=useState(null);
  const [catalog,setCatalog]=useState(null);
  const bottom=useRef(null);
  useEffect(()=>{localStorage.setItem('clinic-session',session)},[session]);
  useEffect(()=>{Promise.all([api('/profile'),api('/health'),api('/catalog'),api('/bookings')]).then(([p,h,c,b])=>{setProfile(p);setHealth(h);setCatalog(c);setBookings(b)}).catch(e=>setError(errorText(e)))},[]);
  useEffect(()=>{bottom.current?.scrollIntoView({behavior:'smooth',block:'nearest'})},[messages,busy]);
  async function refresh(){try{setBookings(await api('/bookings'));setError('')}catch(e){setError('重新整理預約失敗 / Could not refresh bookings: '+errorText(e))}}
  async function send(text=input, pending=null){
    if(busy||!text.trim())return;
    const request=pending||{message:text.trim(),session_id:session,request_id:uuid()};
    setBusy(true);setError('');setRetry(null);
    if(!pending){setMessages(m=>[...m,{role:'user',text:request.message}]);setInput('')}
    try{
      const data=await api('/chat',{method:'POST',body:JSON.stringify(request)});
      setMessages(m=>[...m,{role:'assistant',text:data.reply,...data}]);setDraft(data.draft);
      try{setBookings(await api('/bookings'))}catch(e){setError('對話已完成，但預約列表更新失敗，請按重新整理。 / Chat completed, but bookings could not refresh. Please refresh the list.')}
    }catch(e){setError(errorText(e));setRetry(request)}
    finally{setBusy(false)}
  }
  function reset(){setSession(uuid());setMessages([]);setDraft({});setRetry(null);setError('');setInput('')}
  return <div className="app">
    <header><div className="brand"><span className="logo">＋</span><div><h1>ClinicPilot <span>AI</span></h1><p>關懷，從對話開始 · Care starts with a conversation</p></div></div><span className="mode">{health?.mode==='llm'?'LLM · 模型工具呼叫 / Model tools'+(health.model?' · '+health.model:''):health?'LOCAL · 本機示範 / Local demo':'連線中 / Connecting…'}</span></header>
    <div className="intro"><div><span className="eyebrow">患者工作台 / PATIENT WORKBENCH</span><h2><Pair zh="讓每一次複診，更輕鬆。" en="Make every follow-up visit easier."/></h2><p><Pair zh="了解診所與醫生、尋找合適的服務，並在對話中完成預約。" en="Explore clinics, doctors and services. Book through conversation."/></p></div><div className="patient"><b>{profile?profile.first_name+' '+profile.last_name:'載入患者 / Loading patient…'}</b><span>固定示範患者 / Demo patient · P001</span><small>已知過敏 / Allergies：{profile?.known_allergies_zh||'—'} / {profile?.known_allergies||'—'}</small></div></div>
    <main>
      <section className="panel chat"><div className="panel-title"><div><h3>就診助手</h3><span>Clinic assistant</span></div><button disabled={busy} onClick={reset}>新對話 / New chat</button></div>
        <div className="messages" aria-live="polite">
          {!messages.length&&<div className="welcome"><div className="bot-icon">✦</div><h3><Pair zh="你好，John。" en="Hello, John."/></h3><p><Pair zh="可先查詢服務，或告訴我想預約的醫生與時間。" en="Ask about a service, or tell me your preferred doctor and time."/></p><div className="suggestions">{suggestions.map(([zh,en])=><button disabled={busy} key={en} onClick={()=>send(zh)}><span><Pair zh={zh} en={en}/></span><span aria-hidden="true">↗</span></button>)}</div></div>}
          {messages.map((m,i)=><article key={i} className={'message '+m.role}><span className="who">{m.role==='user'?'你 / YOU':'CLINICPILOT'}</span><div className="bubble">{m.role==='assistant'?replyDisplay(m.text):m.text}</div>{m.tool_trace&&<details><summary>{m.mode==='local'?'本機規則 / Local rules':'LLM'} · {intentLabels[m.intent]||m.intent} · {m.latency_ms} ms · 查看呼叫紀錄 / Tool trace</summary>{m.tool_trace.map((t,j)=><div key={j}>{t.tool} → {t.status==='ok'?'成功 / OK':t.status==='rejected'?'已拒絕 / Rejected':t.status}{t.booking_id?' · '+t.booking_id:''}{t.model?' · '+t.model:''}{t.response_id?' · '+t.response_id:''}</div>)}</details>}</article>)}
          {busy&&<p className="thinking" role="status">正在處理，請稍候… / Working on your request…</p>}<div ref={bottom}/>
        </div>
        {Object.keys(draft).length>0&&<div className="draft"><b>預約草稿 / Booking draft</b>{['doctor_id','treatment_id','booking_date','booking_time'].map(k=><span key={k}>{slotLabels[k]}: {draft[k]||'待填寫 / Required'}</span>)}</div>}
        {error&&<div role="alert" className="error">{error}{retry&&<button disabled={busy} onClick={()=>send(retry.message,retry)}>重試 / Retry request</button>}</div>}
        <form onSubmit={e=>{e.preventDefault();send()}}><label className="sr-only" htmlFor="message">輸入訊息 / Message</label><textarea id="message" placeholder="輸入訊息 / Message — 2035-11-08, 09:30" value={input} onChange={e=>setInput(e.target.value)} maxLength={4000} disabled={busy} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send()}}}/><button className="send" disabled={busy||!input.trim()} type="submit">傳送 / Send ↑</button></form>
        <p className="footnote">服務導覽與預約示範，不提供診斷或處方。時間採診所當地時區。 / Service navigation and booking demo, not diagnosis or prescribing. Times use the clinic’s local timezone.</p>
      </section>
      <aside><section className="panel"><div className="panel-title"><div><h3>我的預約 / My bookings</h3><span>資料庫紀錄 / Database records · {bookings.length}</span></div><button onClick={refresh}>重新整理 / Refresh</button></div><div className="bookings">{bookings.length?bookings.map(b=><article className="booking" key={b.booking_id}><span className="status">{b.status_label||b.status}</span><h4><Pair zh={b.treatment_name_zh||b.treatment_name} en={b.treatment_name}/></h4><p>{b.doctor_name}</p><strong>{b.booking_date} · {b.booking_time.slice(0,5)}</strong><small>{b.clinic_name} · {b.timezone}</small><small className="id">{b.booking_id}</small></article>):<p className="empty">暫無預約，或正在載入。 / No bookings, or still loading.</p>}</div></section>
      <section className="panel guide"><span className="eyebrow">使用方式 / HOW IT WORKS</span><h3>三步完成預約 / Book in three steps</h3><ol><li><Pair zh="選擇醫生與服務" en="Choose a doctor and treatment"/></li><li><Pair zh="提供日期與當地時間" en="Provide a date and local time"/></li><li><Pair zh="資訊齊全後自動儲存，預約列表即時更新" en="Complete details are saved; the bookings list updates"/></li></ol><p>本機模式支援醫生及服務名稱或編號；日期建議使用 YYYY-MM-DD。 / Local mode accepts doctor and service names or IDs. Use YYYY-MM-DD for dates.</p></section>
      {catalog&&<details className="panel catalog"><summary>查看醫生與服務目錄 / Doctors & services</summary>{catalog.doctors.map(d=><p key={d.doctor_id}><b>{d.doctor_id} · {d.full_name}</b><br/>{d.zh?.specialty} / {d.specialty} · 診金 / Consultation ${d.consultation_fee_usd}</p>)}{catalog.treatments.map(t=><p key={t.treatment_id}>{t.treatment_id} · {t.zh?.treatment_name} / {t.treatment_name}<br/>${t.price_usd} · {t.duration_minutes} 分鐘 / min</p>)}</details>}
      </aside>
    </main><TranscriptSummary mode={health?.mode}/><TracePanel/><footer>CLINICPILOT AI · 作業原型 / Take-home MVP <span>React / FastAPI / SQLite</span></footer>
  </div>;
}
