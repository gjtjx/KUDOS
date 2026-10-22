export async function api(path, options={}) {
  const response = await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json'},signal:AbortSignal.timeout(90000)});
  const body = await response.json();
  if (!response.ok) throw Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail));
  return body;
}
