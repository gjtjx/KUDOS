import React, { useState, useEffect, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

async function api(path, options={}) {
  const response = await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json'},signal:AbortSignal.timeout(90000)});
  const body = await response.json();
  if (!response.ok) throw Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail));
  return body;
}
const uuid=()=>crypto.randomUUID();
function App(){
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
  useEffect(()=>{Promise.all([api('/profile'),api('/health'),api('/catalog'),api('/bookings')]).then(([p,h,c,b])=>{setProfile(p);setHealth(h);setCatalog(c);setBookings(b)}).catch(e=>setError(e.message))},[]);
  useEffect(()=>{bottom.current?.scrollIntoView({behavior:'smooth',block:'nearest'})},[messages,busy]);
  async function refresh(){try{setBookings(await api('/bookings'));setError('')}catch(e){setError('刷新预约失败：'+e.message)}}
  async function send(text=input, pending=null){
    if(busy||!text.trim())return;
    const request=pending||{message:text.trim(),session_id:session,request_id:uuid()};
    setBusy(true);setError('');setRetry(null);
    if(!pending){setMessages(m=>[...m,{role:'user',text:request.message}]);setInput('')}
    try{
      const data=await api('/chat',{method:'POST',body:JSON.stringify(request)});
      setMessages(m=>[...m,{role:'assistant',text:data.reply,...data}]);setDraft(data.draft);
      try{setBookings(await api('/bookings'))}catch(e){setError('对话已完成，但预约列表刷新失败，请点击刷新。')}
    }catch(e){setError(e.message);setRetry(request)}
    finally{setBusy(false)}
  }
  function reset(){setSession(uuid());setMessages([]);setDraft({});setRetry(null);setError('')}
  return <div className="app">
    <header><div className="brand"><span className="logo">＋</span><div><h1>ClinicPilot <span>AI</span></h1><p>Care starts with a conversation</p></div></div><span className="mode">{health?.mode==='llm'?'LLM · 模型工具调用':health?'LOCAL · 本地演示':'连接中…'}</span></header>
    <div className="intro"><div><span className="eyebrow">PATIENT WORKBENCH</span><h2>让下一次就诊，更简单。</h2><p>了解诊所与医生、寻找合适的服务，并在对话中完成预约。</p></div><div className="patient"><b>{profile?profile.first_name+' '+profile.last_name:'载入患者…'}</b><span>固定演示患者 · P001</span><small>已知过敏：{profile?.known_allergies||'—'}</small></div></div>
    <main>
      <section className="panel chat"><div className="panel-title"><div><h3>就诊助手</h3><span>Clinic assistant</span></div><button disabled={busy} onClick={reset}>新对话</button></div>
        <div className="messages" aria-live="polite">
          {!messages.length&&<div className="welcome"><div className="bot-icon">✦</div><h3>你好，John。</h3><p>可以先询问服务，或告诉我想预约的医生和时间。</p><div className="suggestions">{['我有花生过敏，可以咨询谁？','When is my next appointment?','帮我预约 D101 的 T001 体检','What are the clinic cancellation policies?'].map(q=><button disabled={busy} key={q} onClick={()=>send(q)}>{q}<span>↗</span></button>)}</div></div>}
          {messages.map((m,i)=><article key={i} className={'message '+m.role}><span className="who">{m.role==='user'?'YOU':'CLINICPILOT'}</span><div className="bubble">{m.text}</div>{m.sources?.length>0&&<div className="sources">{m.sources.map(s=><span key={s.id}>{s.source} · {s.id}</span>)}</div>}{m.tool_trace&&<details><summary>{m.mode==='local'?'本地规则':'LLM'} · {m.intent} · {m.latency_ms} ms · 查看调用记录</summary>{m.tool_trace.map((t,j)=><div key={j}>{t.tool} → {t.status}{t.booking_id?' · '+t.booking_id:''}</div>)}</details>}</article>)}
          {busy&&<p className="thinking" role="status">正在处理，请稍候…</p>}<div ref={bottom}/>
        </div>
        {Object.keys(draft).length>0&&<div className="draft"><b>预约草稿</b>{['doctor_id','treatment_id','booking_date','booking_time'].map(k=><span key={k}>{k.replace('booking_','')}: {draft[k]||'待填写'}</span>)}</div>}
        {error&&<div role="alert" className="error">{error}{retry&&<button disabled={busy} onClick={()=>send(retry.message,retry)}>重试同一请求</button>}</div>}
        <form onSubmit={e=>{e.preventDefault();send()}}><label className="sr-only" htmlFor="message">输入消息</label><textarea id="message" placeholder="输入消息，例如：2030-11-08，上午 9:30" value={input} onChange={e=>setInput(e.target.value)} maxLength={4000} disabled={busy} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send()}}}/><button className="send" disabled={busy||!input.trim()} type="submit">发送 ↑</button></form>
        <p className="footnote">服务导航与预约演示，不提供诊断或处方。时间按所选诊所当地时区记录。</p>
      </section>
      <aside><section className="panel"><div className="panel-title"><div><h3>我的预约</h3><span>来自数据库 · {bookings.length} 条</span></div><button onClick={refresh}>刷新</button></div><div className="bookings">{bookings.length?bookings.map(b=><article className="booking" key={b.booking_id}><span className="status">{b.status}</span><h4>{b.treatment_name}</h4><p>{b.doctor_name}</p><strong>{b.booking_date} · {b.booking_time.slice(0,5)}</strong><small>{b.clinic_name} · {b.timezone}</small><small className="id">{b.booking_id}</small></article>):<p className="empty">暂无预约，或正在载入。</p>}</div></section>
      <section className="panel guide"><span className="eyebrow">HOW IT WORKS</span><h3>三步完成预约</h3><ol><li>选择医生和服务</li><li>提供日期与当地时间</li><li>信息齐全后自动保存，右侧即时更新</li></ol><p>本地模式支持医生姓名或编号、服务名称或编号；日期建议使用 YYYY-MM-DD。</p></section>
      {catalog&&<details className="panel catalog"><summary>查看医生与服务目录</summary>{catalog.doctors.map(d=><p key={d.doctor_id}><b>{d.doctor_id} · {d.full_name}</b><br/>{d.specialty} · consultation ${d.consultation_fee_usd}</p>)}{catalog.treatments.map(t=><p key={t.treatment_id}>{t.treatment_id} · {t.treatment_name}<br/>${t.price_usd} · {t.duration_minutes} min</p>)}</details>}
      </aside>
    </main><footer>CLINICPILOT AI · Take-home MVP <span>React / FastAPI / SQLite</span></footer>
  </div>;
}
createRoot(document.getElementById('root')).render(<App/>);

