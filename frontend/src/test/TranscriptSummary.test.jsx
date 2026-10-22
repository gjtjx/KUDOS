import React from 'react';
import { test, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TranscriptSummary from '../TranscriptSummary';
import { api } from '../api';
vi.mock('../api',()=>({api:vi.fn()}));
beforeEach(()=>{api.mockReset()});
const result={summary:{chief_complaint:'頭痛 / Headache',diagnosis:null,medication:null,doctor_instructions:null},evidence:{chief_complaint:['頭痛'],diagnosis:[],medication:[],doctor_instructions:[]},notice:'僅整理原文 / Source extraction only'};
async function open(mode='llm'){render(<TranscriptSummary mode={mode}/>);const user=userEvent.setup();await user.click(screen.getByRole('button',{name:/開啟/}));return user}
test('local mode and empty input cannot request a summary',async()=>{
  const user=await open('local');await user.type(screen.getByRole('textbox'),'hello');
  expect(screen.getByRole('button',{name:/產生摘要/})).toBeDisabled();fireEvent.submit(screen.getByRole('textbox').closest('form'));expect(api).not.toHaveBeenCalled();
});
test('renders structured fields, exact evidence, missing facts and JSON',async()=>{
  api.mockResolvedValue(result);const user=await open();expect(screen.getByRole('button',{name:/產生摘要/})).toBeDisabled();
  await user.type(screen.getByRole('textbox'),'病人：頭痛');await user.click(screen.getByRole('button',{name:/產生摘要/}));
  await screen.findByText('頭痛 / Headache');expect(screen.getAllByText('原文未提及 / Not mentioned')).toHaveLength(3);
  expect(screen.getByText('頭痛')).toBeInTheDocument();expect(api).toHaveBeenCalledWith('/transcripts/summarize',expect.objectContaining({method:'POST',body:JSON.stringify({transcript:'病人：頭痛'})}));
  await user.click(screen.getByRole('button',{name:/收合/}));expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
});
test('pending summary disables duplicate submissions',async()=>{
  let resolve;api.mockImplementation(()=>new Promise(r=>resolve=r));const user=await open();await user.type(screen.getByRole('textbox'),'headache');
  await user.click(screen.getByRole('button',{name:/產生摘要/}));expect(screen.getByRole('button',{name:/正在整理/})).toBeDisabled();
  fireEvent.submit(screen.getByRole('textbox').closest('form'));expect(api).toHaveBeenCalledTimes(1);resolve(result);await screen.findByText('頭痛 / Headache');
});
test.each([Error('provider unavailable'),Object.assign(Error('timeout'),{name:'TimeoutError'})])('shows failure without stale result',async(error)=>{
  api.mockRejectedValue(error);const user=await open();await user.type(screen.getByRole('textbox'),'headache');await user.click(screen.getByRole('button',{name:/產生摘要/}));
  expect(await screen.findByRole('alert')).toHaveTextContent('摘要未完成');expect(screen.queryByText('頭痛 / Headache')).not.toBeInTheDocument();
});
