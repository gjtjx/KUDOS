// Presentation only: retain original replies and structured evidence in the API.
const files=/(?:patient_treatment_history|patient_bookings|patients|clinics|doctors|treatments)\.csv/gi;
function citationOnly(text){
  if(text.search(files)<0)return false;
  return !text.replace(files,'').replace(/\b[CDTPH]\d+\b/gi,'')
    .replace(/\b(?:source|sources|record|records|id|ids)\b/gi,'')
    .replace(/來源|来源|資料來源|数据来源|紀錄|記錄|記錄編號|編號/g,'')
    .replace(/[\s:：,，;；、.。()（）\[\]【】/]+/g,'');
}
const escape=value=>value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
function entityNames(line,catalog){
  const chinese=/[\u4e00-\u9fff]/.test(line);
  const records=[...(catalog?.doctors||[]).map(d=>({id:d.doctor_id,name:d.full_name,names:[d.full_name]})),
    ...(catalog?.treatments||[]).map(t=>({id:t.treatment_id,name:chinese?(t.zh?.treatment_name||t.treatment_name_zh||t.treatment_name):t.treatment_name,
      names:[t.treatment_name,t.zh?.treatment_name,t.treatment_name_zh].filter(Boolean)}))];
  for(const item of records){
    const id=escape(item.id);
    for(const name of item.names){
      const literal=escape(name);
      line=line.replace(new RegExp('('+literal+')\\s*[（(]\\s*'+id+'\\s*[）)]','gi'),'$1');
      line=line.replace(new RegExp('\\b'+id+'\\b\\s*[（(]\\s*('+literal+')\\s*[）)]','gi'),'$1');
      line=line.replace(new RegExp('\\b'+id+'\\b\\s*(?:[·:：-]\\s*)?(?='+literal+')','gi'),'');
      line=line.replace(new RegExp('('+literal+')(?:\\s*[·:：-]\\s*|\\s+)'+id+'\\b','gi'),'$1');
    }
  }
  const names=new Map(records.map(item=>[item.id.toUpperCase(),item.name]));
  return line.replace(/\b([DT])\d+\b/gi,(id,type)=>names.get(id.toUpperCase())||
    (chinese?(type.toUpperCase()==='D'?'未識別醫生':'未識別服務'):(type.toUpperCase()==='D'?'unidentified doctor':'unidentified service'))).trim();
}
export function replyDisplay(text,catalog){
  return text.split('\n').map(line=>{
    if(citationOnly(line))return '';
    line=line.replace(/[（(【\[][^()（）\[\]【】\n]*[）)】\]]/g,part=>citationOnly(part)?'':part);
    line=line.replace(/(?:來源|来源|Sources?)\s*[:：][^。\n]*[。.]?/gi,part=>citationOnly(part)?'':part);
    // Inline attribution may contain factual content; rename the filename rather
    // than deleting the surrounding clause (prices, instructions, names, etc.).
    return entityNames(line.replace(files,/[\u4e00-\u9fff]/.test(line)?'現有資料':'available records'),catalog);
  }).filter((line,i,lines)=>line||i>0&&lines[i-1]).join('\n').trim();
}
