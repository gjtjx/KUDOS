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
test('preserves booking IDs, dates, conditional preparation and contact details',()=>{
  const text='B1001: 2026-11-05 09:00 America/New_York · D101 · T001\nFast for 8 hours only if blood tests are scheduled. Call +1-555-019-2831.';
  const shown=replyDisplay(text);expect(shown).toContain('B1001: 2026-11-05 09:00 America/New_York');expect(shown).toContain('Call +1-555-019-2831.');expect(shown).toContain('only if blood tests are scheduled');expect(shown).not.toMatch(/D101|T001/);
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

const catalog={doctors:[{doctor_id:'D101',full_name:'Dr. Sarah Jenkins'},{doctor_id:'D103',full_name:'Dr. Elena Rostova'}],treatments:[{treatment_id:'T001',treatment_name:'General Health Checkup',zh:{treatment_name:'一般健康檢查'}},{treatment_id:'T003',treatment_name:'Dermatology Consultation',treatment_name_zh:'皮膚科諮詢'}]};
test('resolves doctor and service IDs from live catalog by paragraph language',()=>{
  expect(replyDisplay('醫生 D101，服務 T001。\nDoctor D101, service T001.',catalog)).toBe('醫生 Dr. Sarah Jenkins，服務 一般健康檢查。\nDoctor Dr. Sarah Jenkins, service General Health Checkup.');
});
test('removes redundant ID beside a name without doubling the name',()=>{
  expect(replyDisplay('Dr. Sarah Jenkins（D101） · D101 Dr. Sarah Jenkins · Dr. Sarah Jenkins D101',catalog)).toBe('Dr. Sarah Jenkins · Dr. Sarah Jenkins · Dr. Sarah Jenkins');
});
test('does not duplicate already bilingual treatment names',()=>{
  expect(replyDisplay('T001 一般健康檢查 / General Health Checkup',catalog)).toBe('一般健康檢查 / General Health Checkup');
});
test('resolves a service alternate Chinese label and lowercase IDs',()=>{
  expect(replyDisplay('d103 的 t003',catalog)).toBe('Dr. Elena Rostova 的 皮膚科諮詢');
});
test('preserves seed and generated booking IDs containing doctor-like digits',()=>{
  const bookings='B1001 B1004 BD101ABC12345 B123T001ABCDE';
  expect(replyDisplay(bookings,catalog)).toBe(bookings);
});
test('never guesses a real name for unknown IDs or missing catalog',()=>{
  expect(replyDisplay('D999 / T999',catalog)).toBe('unidentified doctor / unidentified service');
  expect(replyDisplay('醫生 D101 服務 T001',null)).toBe('醫生 未識別醫生 服務 未識別服務');
});
test('does not mutate catalog or raw API response text',()=>{
  const before=JSON.stringify(catalog),text='D101 T001 B1001';replyDisplay(text,catalog);
  expect(JSON.stringify(catalog)).toBe(before);expect(text).toBe('D101 T001 B1001');
});
test('keeps factual parentheses, fees and conditional preparation while replacing IDs',()=>{
  const shown=replyDisplay('T001 (USD 150, 30 minutes). Fast only if blood tests are scheduled.',catalog);
  expect(shown).toBe('General Health Checkup (USD 150, 30 minutes). Fast only if blood tests are scheduled.');
});
test('preserves booking IDs even inside source references',()=>{
  const shown=replyDisplay('預約（來源：patient_bookings.csv，B1001）\nSource: patient_bookings.csv, BABCDEF123456',catalog);
  expect(shown).toContain('B1001');expect(shown).toContain('BABCDEF123456');expect(shown).not.toContain('.csv');
});
test('handles ID followed by parenthesized name and compact suffix separators',()=>{
  expect(replyDisplay('D101（Dr. Sarah Jenkins） · Dr. Sarah Jenkins·D101',catalog)).toBe('Dr. Sarah Jenkins · Dr. Sarah Jenkins');
});
