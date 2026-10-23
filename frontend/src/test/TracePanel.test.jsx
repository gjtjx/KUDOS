import React from 'react';
import { beforeEach, test, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TracePanel from '../TracePanel';
import { api } from '../api';
vi.mock('../api',()=>({api:vi.fn()}));
const empty={enabled:true,retention_limit:1000,summary:{requests:0,llm_calls:0,errors:null,input_tokens:null,output_tokens:null,cache_hits:null,mean_latency_ms:null},traces:[]};
const traced={...empty,summary:{requests:2,llm_calls:1,errors:1,input_tokens:120,output_tokens:20,cache_hits:1,mean_latency_ms:1500},traces:[
  {trace_id:'t1',operation:'chat',status:'ok',duration_ms:1500,started_at:'2026-10-22T14:00:00Z',cache_hit:true,outcome:'cached',spans:[]},
  {trace_id:'t2',operation:'transcript_summary',status:'error',duration_ms:2500,started_at:'2026-10-22T14:01:00Z',cache_hit:false,outcome:null,spans:[{span_id:'s1',operation:'summarize_transcript',model:'test-model',status:'error',duration_ms:2100,input_tokens:null,output_tokens:null,error_code:'timeout'}]}
]};
beforeEach(()=>{api.mockReset().mockResolvedValue(empty)});
async function open(){const user=userEvent.setup();render(<TracePanel/>);await user.click(screen.getByRole('button',{name:/查看紀錄/}));return user}
test('fetches only when opened and renders empty metadata-only notice',async()=>{
 render(<TracePanel/>);expect(api).not.toHaveBeenCalled();
 await userEvent.click(screen.getByRole('button',{name:/查看紀錄/}));
 expect(await screen.findByText(/尚無紀錄/)).toBeInTheDocument();
 expect(api).toHaveBeenCalledWith('/observability?limit=20');
 expect(screen.getByText(/不保存提示內容/)).toBeInTheDocument();
});
test('renders totals, cached requests, errors and individual calls',async()=>{
 api.mockResolvedValue(traced);await open();
 expect(await screen.findByText(/輸入 120/)).toBeInTheDocument();expect(screen.queryByText(/Trace ID/)).not.toBeInTheDocument();
 expect(screen.getByText(/test-model/)).toBeInTheDocument();
 expect(screen.getByText(/timeout/)).toBeInTheDocument();
 expect(screen.getByText(/沒有新增模型呼叫/)).toBeInTheDocument();
 expect(screen.getByText(/輸入 120/)).toBeInTheDocument();
});
test('failed fetch can be retried without showing exception details',async()=>{
 api.mockRejectedValueOnce(Error('private-provider-error'));const user=await open();
 expect(await screen.findByRole('alert')).toHaveTextContent('無法載入');
 expect(screen.queryByText('private-provider-error')).not.toBeInTheDocument();
 await user.click(screen.getByRole('button',{name:/更新紀錄/}));
 await screen.findByText(/尚無紀錄/);expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
test('shows disabled notice and allows collapse/reopen',async()=>{
 api.mockResolvedValue({...empty,enabled:false});const user=await open();
 await screen.findByText(/追蹤目前已停用/);
 await user.click(screen.getByRole('button',{name:/收合紀錄/}));
 expect(screen.queryByText(/追蹤目前已停用/)).not.toBeInTheDocument();
 await user.click(screen.getByRole('button',{name:/查看紀錄/}));
 expect(await screen.findByText(/追蹤目前已停用/)).toBeInTheDocument();
});
test('pending refresh disables duplicate actions',async()=>{
 let resolve;api.mockImplementation(()=>new Promise(r=>resolve=r));await open();
 expect(screen.getByRole('status')).toHaveTextContent('載入紀錄中');
 expect(screen.getByRole('button',{name:/更新紀錄/})).toBeDisabled();
 expect(screen.getByRole('button',{name:/收合紀錄/})).toBeDisabled();
 resolve(empty);await screen.findByText(/尚無紀錄/);
});
test('unknown future statuses and missing duration remain visible',async()=>{
 api.mockResolvedValue({...empty,traces:[{trace_id:'future',operation:'future_operation',status:'future_status',duration_ms:null,started_at:'2026-10-22T14:00:00Z',spans:[{span_id:'future-span',operation:'future_tool',model:'m',status:'other',duration_ms:null,input_tokens:1,output_tokens:2}]}]});
 await open();expect(await screen.findByText(/future_operation/)).toBeInTheDocument();expect(screen.getByText('future_tool')).toBeInTheDocument();
});
