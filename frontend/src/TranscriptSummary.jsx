import React, { useState } from 'react';
import { api } from './api';
import { replyDisplay } from './replyDisplay';
const labels={chief_complaint:'主訴 / Chief complaint',diagnosis:'診斷 / Diagnosis',medication:'用藥 / Medication',doctor_instructions:'醫囑 / Doctor instructions'};
export default function TranscriptSummary({mode,catalog}){
  const [open,setOpen]=useState(false),[transcript,setTranscript]=useState(''),[result,setResult]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  async function submit(e){
    e.preventDefault();if(busy||!transcript.trim()||mode!=='llm')return;
    setBusy(true);setError('');setResult(null);
    try{setResult(await api('/transcripts/summarize',{method:'POST',body:JSON.stringify({transcript:transcript.trim()})}))}
    catch(e){setError('摘要未完成 / Summary failed: '+(e.name==='TimeoutError'?'請求逾時，請重試 / Request timed out; please retry':e.message))}
    finally{setBusy(false)}
  }
  const displaySummary=result?Object.fromEntries(Object.entries(result.summary).map(([key,value])=>[key,value==null?value:replyDisplay(value,catalog)])):null;
  return <section className="panel transcript-panel">
    <div className="panel-title"><div><h3>逐字稿摘要 / Transcript summary</h3><span>整理已轉成文字的對話 / Summarize a written transcript</span></div><button aria-expanded={open} onClick={()=>setOpen(!open)}>{open?'收合 / Collapse':'開啟 / Open'}</button></div>
    {open&&<div className="transcript-body">
      <p>只摘錄原文明確提及的內容，未提及欄位留空。請勿將摘要視為新的診斷或處方。 / Extracts explicit facts only; missing fields remain empty. This is not a new diagnosis or prescription.</p>
      <p>逐字稿會傳送至已設定的模型服務，本系統不將其存入資料庫。 / Transcripts are sent to the configured model provider and are not stored in this application's database.</p>
      {mode!=='llm'&&<p>此功能需要真實模型連線。 / This feature requires a live model connection.</p>}
      <form onSubmit={submit}><label htmlFor="transcript">醫病對話逐字稿 / Doctor-patient transcript</label><textarea id="transcript" rows={6} maxLength={16000} value={transcript} disabled={busy} onChange={e=>setTranscript(e.target.value)}/><button disabled={busy||!transcript.trim()||mode!=='llm'} type="submit">{busy?'正在整理 / Summarizing…':'產生摘要 / Generate summary'}</button></form>
      {error&&<p role="alert" className="error">{replyDisplay(error,catalog)}</p>}
      {result&&<div aria-live="polite"><p>{replyDisplay(result.notice,catalog)}</p><dl>{Object.entries(labels).map(([key,label])=><React.Fragment key={key}><dt>{label}</dt><dd>{displaySummary[key]??'原文未提及 / Not mentioned'}{result.evidence[key]?.map((quote,i)=><blockquote key={i}>{replyDisplay(quote,catalog)!==quote&&<small>顯示引文已隱藏內部編號／來源標籤 / Internal IDs and source labels hidden in this displayed quote<br/></small>}{replyDisplay(quote,catalog)}</blockquote>)}</dd></React.Fragment>)}</dl><details><summary>顯示用 JSON / Display JSON</summary><pre>{JSON.stringify(displaySummary,null,2)}</pre></details></div>}
    </div>}
  </section>;
}
