import React, { useState } from 'react';
import { api } from './api';
import { replyDisplay } from './replyDisplay';

const number=value=>value==null?'—':value.toLocaleString();
const duration=value=>value==null?'—':(value/1000).toFixed(2)+' s';
const names={chat:'對話 / Chat',transcript_summary:'逐字稿摘要 / Transcript summary',route_intent:'意圖識別 / Intent routing',answer:'回答 / Answer',summarize_transcript:'摘要 / Summary'};
const statuses={ok:'成功 / OK',error:'失敗 / Failed',running:'處理中 / Running',interrupted:'已中斷 / Interrupted'};
const outcomes={cached:'使用既有結果 / Cached',booked:'已建立預約 / Booked',rejected:'預約未通過驗證 / Booking rejected',draft:'保留草稿 / Draft',answered:'已回答 / Answered',summarized:'已摘要 / Summarized'};
export default function TracePanel({catalog}){
  const [open,setOpen]=useState(false),[data,setData]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  async function refresh(){
    if(busy)return;
    setBusy(true);setError('');
    try{setData(await api('/observability?limit=20'))}
    catch{setError('無法載入使用紀錄，請重試。 / Could not load activity. Please retry.')}
    finally{setBusy(false)}
  }
  function toggle(){if(!open)refresh();setOpen(!open)}
  return <section className="panel trace-panel">
    <div className="panel-title"><div><h3>模型使用紀錄 / Model activity</h3><span>耗時、用量與處理結果 / Timing, usage and results</span></div><button aria-expanded={open} disabled={busy} onClick={toggle}>{open?'收合紀錄 / Collapse activity':'查看紀錄 / View activity'}</button></div>
    {open&&<div className="trace-body">
      <p>僅保存執行資訊，不保存提示內容、逐字稿或密鑰。 / Activity stores execution metadata, not prompts, transcripts or credentials.</p>
      <button disabled={busy} onClick={refresh}>更新紀錄 / Refresh activity</button>
      {busy&&<p role="status">載入紀錄中 / Loading activity…</p>}
      {error&&<p role="alert">{error}</p>}
      {data&&<>
        {!data.enabled&&<p>追蹤目前已停用；以下為已保留的紀錄。 / Tracing is disabled; retained records appear below.</p>}
        <div className="trace-stats">
          <div><b>{number(data.summary.requests)}</b><span>請求 / Requests</span></div>
          <div><b>{number(data.summary.llm_calls)}</b><span>模型呼叫 / Model calls</span></div>
          <div><b>{number(data.summary.errors??0)}</b><span>失敗請求 / Failed requests</span></div>
          <div><b>{duration(data.summary.mean_latency_ms)}</b><span>平均請求耗時 / Mean request time</span></div>
        </div>
        <p>已回報 Token：輸入 {number(data.summary.input_tokens)} ／ 輸出 {number(data.summary.output_tokens)} · 快取命中 {number(data.summary.cache_hits??0)}<br/>Reported tokens: input / output · Cached requests</p>
        <small>統計範圍為保留的紀錄（上限 {data.retention_limit} 筆）；未回報用量顯示 —，不估算費用。 / Totals cover retained records; missing usage is shown as —. No cost estimate.</small>
        {!data.traces.length&&<p>尚無紀錄，完成一次對話或摘要後更新。 / No activity yet. Complete a chat or summary, then refresh.</p>}
        <div className="trace-list">{data.traces.map(t=><details key={t.trace_id}>
          <summary>{replyDisplay(names[t.operation]||t.operation,catalog)} · {replyDisplay(statuses[t.status]||t.status,catalog)} · {duration(t.duration_ms)}{t.cache_hit?' · 快取 / Cached':''}</summary>
          <p>{new Date(t.started_at).toLocaleString()} · {outcomes[t.outcome]||'—'}</p>
          {t.spans.length?<ol>{t.spans.map(s=><li key={s.span_id}><b>{replyDisplay(names[s.operation]||s.operation,catalog)}</b> · {replyDisplay(s.model||'',catalog)} · {replyDisplay(statuses[s.status]||s.status,catalog)} · {duration(s.duration_ms)}<br/>Token {number(s.input_tokens)} / {number(s.output_tokens)}{s.error_code&&<span> · {replyDisplay(s.error_code,catalog)||'處理失敗 / Processing failed'}</span>}</li>)}</ol>:<p>沒有新增模型呼叫 / No new model calls</p>}
        </details>)}</div>
      </>}
    </div>}
  </section>;
}
