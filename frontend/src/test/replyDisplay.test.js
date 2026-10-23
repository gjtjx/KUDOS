import {test,expect} from 'vitest';
import {replyDisplay} from '../replyDisplay';

test('removes citation-only parentheses in both languages',()=>{
  expect(replyDisplay('診金 USD 150。（來源：doctors.csv，D101）\nFee USD 150. (Source: doctors.csv, D101)'))
    .toBe('診金 USD 150。\nFee USD 150.');
});
test('removes separate source lines and trailing citations',()=>{
  expect(replyDisplay('服務 30 分鐘。來源：treatments.csv，T001。\nSources: treatments.csv, T001')).toBe('服務 30 分鐘。');
});
test('renames inline attribution without deleting clinical or billing facts',()=>{
  const text=replyDisplay('根據 doctors.csv（D101），Dr. Sarah Jenkins 診金 USD 150。\nAccording to treatments.csv (T001), the service takes 30 minutes.');
  expect(text).not.toContain('.csv');expect(text).toContain('Dr. Sarah Jenkins');expect(text).toContain('USD 150');expect(text).toContain('30 minutes');
});
test('preserves factual parentheses even if they mention a filename',()=>{
  expect(replyDisplay('服務（treatments.csv T001，30 分鐘，USD 150）')).toContain('30 分鐘，USD 150');
});
test('preserves dates, IDs, conditional preparation and contact details',()=>{
  const text='B1001: 2026-11-05 09:00 America/New_York · D101 · T001\nFast for 8 hours only if blood tests are scheduled. Call +1-555-019-2831.';
  expect(replyDisplay(text)).toBe(text);
});
test('handles all six source files and multiple repeated calls',()=>{
  for(const file of ['doctors','treatments','clinics','patients','patient_bookings','patient_treatment_history']){
    for(let i=0;i<2;i++)expect(replyDisplay(`來源：${file}.csv，D101`)).toBe('');
  }
});
test('does not treat arbitrary parenthetical content as a source',()=>{
  expect(replyDisplay('正常（120/80）。This is normal (120/80).')).toBe('正常（120/80）。This is normal (120/80).');
});
test('empty strings and blank lines are safe',()=>{
  expect(replyDisplay('')).toBe('');expect(replyDisplay('\n\nHello\n\nWorld\n')).toBe('Hello\n\nWorld');
});
