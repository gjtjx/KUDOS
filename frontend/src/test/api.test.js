import { test, expect, vi } from 'vitest';
import { api } from '../api';

test('sends JSON with timeout and returns parsed response',async()=>{
  const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({reply:'ok'})}); vi.stubGlobal('fetch',fetch);
  expect(await api('/chat',{method:'POST',body:'{}'})).toEqual({reply:'ok'});
  expect(fetch).toHaveBeenCalledWith('/api/chat',expect.objectContaining({method:'POST',body:'{}',headers:{'Content-Type':'application/json'},signal:expect.any(AbortSignal)}));
});
test.each(['Invalid fields',[{field:'message'}]])('preserves server error details %j',async(detail)=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,json:async()=>({detail})}));
  await expect(api('/chat')).rejects.toThrow(typeof detail==='string'?detail:JSON.stringify(detail));
});
test('network and malformed JSON failures are not treated as success',async()=>{
  const fetch=vi.fn().mockRejectedValue(new TypeError('Failed to fetch')); vi.stubGlobal('fetch',fetch);
  await expect(api('/health')).rejects.toThrow('Failed to fetch');
  fetch.mockResolvedValue({ok:true,json:async()=>{throw new SyntaxError('bad JSON')}});
  await expect(api('/health')).rejects.toThrow('bad JSON');
});
