import React from 'react';
import { beforeEach, test, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../App';
import { api } from '../api';
vi.mock('../api',()=>({api:vi.fn()}));
const booking={booking_id:'B1',doctor_name:'Dr. Sarah Jenkins',treatment_name:'General Health Checkup',treatment_name_zh:'一般健康檢查',status:'Confirmed',status_label:'已確認 / Confirmed',booking_date:'2035-11-08',booking_time:'09:30:00',clinic_name:'Metro Care',timezone:'America/New_York'};
const reply={reply:'就診流程 / Visit guide response',intent:'visit_flow',mode:'local',latency_ms:10,draft:{},sources:[{id:'C001',source:'clinics.csv'}],tool_trace:[{tool:'GET /api/bookings',status:'ok'}]};
const initial={
  '/profile':{first_name:'John',last_name:'Doe',known_allergies:'Penicillin, Peanuts',known_allergies_zh:'青黴素、花生'},
  '/health':{mode:'local'}, '/bookings':[booking],
  '/catalog':{doctors:[{doctor_id:'D101',full_name:'Dr. Sarah Jenkins',specialty:'General Practice',zh:{specialty:'全科'},consultation_fee_usd:150}],treatments:[{treatment_id:'T001',treatment_name:'General Health Checkup',zh:{treatment_name:'一般健康檢查'},price_usd:150,duration_minutes:30}]}
};
beforeEach(()=>{api.mockReset().mockImplementation(async(path)=>path==='/chat'?reply:initial[path])});
async function mount(){render(<App/>);await screen.findByText('John Doe');return userEvent.setup()}
const chats=()=>api.mock.calls.filter(([path])=>path==='/chat').map(([,options])=>JSON.parse(options.body));
async function send(user,text='我到医院的流程'){await user.type(screen.getByRole('textbox'),text);await user.click(screen.getByRole('button',{name:/傳送/}))}

test('loads bilingual profile, booking list, mode and catalog',async()=>{
  await mount(); expect(screen.getByText('LOCAL · 本機示範 / Local demo')).toBeInTheDocument();
  expect(screen.getByText('B1')).toBeInTheDocument();expect(screen.getByText(/青黴素、花生/)).toBeInTheDocument();
  expect(screen.getByText(/D101 · Dr. Sarah/)).toBeInTheDocument();
});
test('new conversation sends reported phrase and renders grounded response and trace',async()=>{
  const user=await mount();await send(user);
  expect(await screen.findByText(reply.reply)).toBeInTheDocument();
  expect(chats()[0].message).toBe('我到医院的流程');expect(chats()[0].session_id).toBe(localStorage.getItem('clinic-session'));
  expect(screen.queryByText('clinics.csv · C001')).not.toBeInTheDocument();expect(screen.getByText(/就診流程 \/ Visit guide ·/)).toBeInTheDocument();
  expect(api.mock.calls.filter(([p])=>p==='/bookings')).toHaveLength(2);
});
test('suggested question submits Traditional Chinese',async()=>{
  const user=await mount();await user.click(screen.getByRole('button',{name:/我到醫院的流程/}));
  await screen.findByText(reply.reply);expect(chats()[0].message).toBe('我到醫院的流程');
});

test('patient doctor question shows relationship answer and preserves booking draft',async()=>{
  api.mockImplementation(async(path)=>path==='/chat'?{...reply,intent:'patient_doctors',reply:'未指定主治醫生 / No assigned primary doctor',draft:{doctor_id:'D103',treatment_id:'T003'},sources:[{source:'patient_treatment_history.csv',id:'H9002'}],tool_trace:[{tool:'GET /api/patient-doctors',status:'ok'}]}:initial[path]);
  const user=await mount();await send(user,'我的医生是？');
  expect(await screen.findByText('未指定主治醫生 / No assigned primary doctor')).toBeInTheDocument();
  expect(screen.getByText(/我的醫生 \/ My doctors ·/)).toBeInTheDocument();
  expect(screen.queryByText('patient_treatment_history.csv · H9002')).not.toBeInTheDocument();
  expect(screen.getByText('醫生 / Doctor: D103')).toBeInTheDocument();
  expect(screen.getByText('B1')).toBeInTheDocument();
});
test('empty or whitespace input cannot send',async()=>{
  const user=await mount();expect(screen.getByRole('button',{name:/傳送/})).toBeDisabled();
  await user.type(screen.getByRole('textbox'),'   ');fireEvent.submit(screen.getByRole('textbox').closest('form'));
  expect(chats()).toHaveLength(0);
});
test('pending request prevents duplicate sends and reset',async()=>{
  const user=await mount();let resolve;api.mockImplementation(path=>path==='/chat'?new Promise(r=>resolve=r):Promise.resolve(initial[path]));
  await send(user);expect(screen.getByRole('status')).toBeInTheDocument();
  expect(screen.getByRole('button',{name:/新對話/})).toBeDisabled();expect(screen.getByRole('button',{name:/傳送/})).toBeDisabled();
  fireEvent.submit(screen.getByRole('textbox').closest('form'));expect(chats()).toHaveLength(1);
  resolve(reply);await screen.findByText(reply.reply);
});
test('draft shows missing fields then successful booking refreshes list',async()=>{
  const user=await mount();let calls=0;
  api.mockImplementation(async(path)=>path==='/chat'?(++calls===1?{...reply,reply:'請補日期與時間',draft:{doctor_id:'D101',treatment_id:'T001'}}:{...reply,reply:'預約已儲存',draft:{}}):path==='/bookings'&&calls===2?[booking,{...booking,booking_id:'B2'}]:initial[path]);
  await send(user,'Book D101 T001');await screen.findByText('預約草稿 / Booking draft');expect(screen.getByText('日期 / Date: 待填寫 / Required')).toBeInTheDocument();
  await send(user,'2035-11-08 09:30');await screen.findByText('B2');expect(screen.queryByText('預約草稿 / Booking draft')).not.toBeInTheDocument();
});
test('new chat clears messages, draft, unsent text and rotates session',async()=>{
  localStorage.setItem('clinic-session','old');const user=await mount();await send(user);await screen.findByText(reply.reply);
  await user.type(screen.getByRole('textbox'),'unsent');await user.click(screen.getByRole('button',{name:/新對話/}));
  expect(screen.queryByText(reply.reply)).not.toBeInTheDocument();expect(screen.getByRole('textbox')).toHaveValue('');
  expect(localStorage.getItem('clinic-session')).not.toBe('old');expect(screen.getByText('B1')).toBeInTheDocument();
  await send(user);expect(chats()[1].session_id).not.toBe(chats()[0].session_id);
});
test('retry reuses original request ID without duplicating user message',async()=>{
  const user=await mount();let failed=false;
  api.mockImplementation(async(path)=>{if(path==='/chat'){if(!failed){failed=true;throw Error('Failed to fetch')}return reply}return initial[path]});
  await send(user);expect(await screen.findByRole('alert')).toHaveTextContent('無法連接伺服器');
  await user.click(screen.getByRole('button',{name:/重試/}));await screen.findByText(reply.reply);
  expect(chats()[0]).toEqual(chats()[1]);expect(screen.getAllByText('我到医院的流程')).toHaveLength(1);
});
test('booking refresh failure after chat does not offer to repeat successful booking',async()=>{
  const user=await mount();api.mockImplementation(async(path)=>{if(path==='/bookings')throw Error('offline');return path==='/chat'?reply:initial[path]});
  await send(user);expect(await screen.findByRole('alert')).toHaveTextContent('Chat completed');
  expect(screen.queryByRole('button',{name:/重試/})).not.toBeInTheDocument();expect(screen.getByText(reply.reply)).toBeInTheDocument();
});
test('manual refresh handles errors and recovers',async()=>{
  const user=await mount();api.mockRejectedValueOnce(Error('offline'));
  await user.click(screen.getByRole('button',{name:/重新整理/}));expect(await screen.findByRole('alert')).toHaveTextContent('Could not refresh');
  await user.click(screen.getByRole('button',{name:/重新整理/}));await waitFor(()=>expect(screen.queryByRole('alert')).not.toBeInTheDocument());
});
test('startup timeout is visible',async()=>{
  api.mockRejectedValue(Object.assign(Error('timeout'),{name:'TimeoutError'}));render(<App/>);
  expect(await screen.findByRole('alert')).toHaveTextContent('請求逾時');
});
test('Enter sends, Shift+Enter and IME composition do not',async()=>{
  const user=await mount();await user.type(screen.getByRole('textbox'),'hello');
  fireEvent.keyDown(screen.getByRole('textbox'),{key:'Enter',shiftKey:true});
  fireEvent.keyDown(screen.getByRole('textbox'),{key:'Enter',isComposing:true});expect(chats()).toHaveLength(0);
  fireEvent.keyDown(screen.getByRole('textbox'),{key:'Enter'});await screen.findByText(reply.reply);expect(chats()).toHaveLength(1);
});
test('LLM mode and rejected tool result render correctly',async()=>{
  api.mockImplementation(async(path)=>path==='/health'?{mode:'llm'}:path==='/chat'?{...reply,mode:'llm',intent:'book',tool_trace:[{tool:'POST /api/bookings',status:'rejected'}]}:initial[path]);
  const user=await mount();expect(screen.getByText(/LLM · 模型工具呼叫/)).toBeInTheDocument();
  await send(user);await screen.findByText(reply.reply);expect(screen.getByText(/POST \/api\/bookings → 已拒絕/)).toBeInTheDocument();
});

test('hides source filenames in assistant replies without changing user text or API evidence',async()=>{
  const original={...reply,reply:'Dr. Sarah Jenkins 的診金 USD 150。（來源：doctors.csv，D101）\nDr. Sarah Jenkins has a USD 150 fee. (Source: doctors.csv, D101)',sources:[{source:'doctors.csv',id:'D101'},{source:'treatments.csv',id:'T001'}]};
  api.mockImplementation(async(path)=>path==='/chat'?original:initial[path]);
  const user=await mount();await send(user,'doctors.csv');
  expect(await screen.findByText(/Dr. Sarah Jenkins has a USD 150 fee/)).toBeInTheDocument();
  const assistant=document.querySelector('.message.assistant .bubble');
  expect(assistant.textContent).not.toMatch(/\.csv/i);
  expect(assistant.textContent).toContain('USD 150');
  expect(document.querySelector('.message.user .bubble')).toHaveTextContent('doctors.csv');
  expect(document.querySelector('.sources')).toBeNull();
  expect(original.reply).toContain('doctors.csv');expect(original.sources).toHaveLength(2);
});
