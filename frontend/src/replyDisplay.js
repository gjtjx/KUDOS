// Presentation only: retain original replies and structured evidence in the API.
const files=/(?:patient_treatment_history|patient_bookings|patients|clinics|doctors|treatments)\.csv/gi;
function citationOnly(text){
  if(text.search(files)<0)return false;
  return !text.replace(files,'').replace(/\b[BCDTPH]\d+\b/gi,'')
    .replace(/\b(?:source|sources|record|records|id|ids)\b/gi,'')
    .replace(/來源|来源|資料來源|数据来源|紀錄|記錄|記錄編號|編號/g,'')
    .replace(/[\s:：,，;；、.。()（）\[\]【】/]+/g,'');
}
export function replyDisplay(text){
  return text.split('\n').map(line=>{
    if(citationOnly(line))return '';
    line=line.replace(/[（(【\[][^()（）\[\]【】\n]*[）)】\]]/g,part=>citationOnly(part)?'':part);
    line=line.replace(/(?:來源|来源|Sources?)\s*[:：][^。\n]*[。.]?/gi,part=>citationOnly(part)?'':part);
    // Inline attribution may contain factual content; rename the filename rather
    // than deleting the surrounding clause (prices, instructions, names, etc.).
    return line.replace(files,/[\u4e00-\u9fff]/.test(line)?'現有資料':'available records').trim();
  }).filter((line,i,lines)=>line||i>0&&lines[i-1]).join('\n').trim();
}
