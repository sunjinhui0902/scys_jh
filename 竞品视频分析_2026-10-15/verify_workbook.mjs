import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';
const root=path.dirname(fileURLToPath(import.meta.url));
const filename=path.join(root,'阅见生活_竞品视频分析_终版.xlsx');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(filename));
wb.recalculate();
const names=['01_视频总览','02_带货脚本拆解','03_视觉模板','04_账号对标与高频规律','05_原创带货模板库','06_异常待复核','07_口径与运行摘要'];
const dir=path.join(root,'reports','workbook_previews');await fs.mkdir(dir,{recursive:true});
const summary=await wb.inspect({kind:'sheet',include:'id,name',maxChars:2500});
await fs.writeFile(path.join(dir,'sheet_inspection.txt'),summary.ndjson??JSON.stringify(summary),'utf8');
const outputs=[];
for(const name of names){
  const range=name.startsWith('07')?'A1:C16':name.startsWith('05')?'A1:J7':name.startsWith('06')?'A1:F10':name.startsWith('04')?'A1:H12':name.startsWith('03')?'A1:J10':name.startsWith('02')?'A1:H10':'A1:M10';
  const blob=await wb.render({sheetName:name,range,scale:1,format:'png'});
  const target=path.join(dir,name+'.png');await fs.writeFile(target,new Uint8Array(await blob.arrayBuffer()));outputs.push({sheet:name,range,path:target});
}
const sources=(await fs.readFile(path.join(root,'manifest','manifest.jsonl'),'utf8')).trim().split(/\r?\n/).map(s=>JSON.parse(s));
const candidates=JSON.parse(await fs.readFile(path.join(root,'clusters','deep_candidates.json'),'utf8'));
const longest=[...candidates].sort((a,b)=>b.reason.length-a.reason.length)[0];
const row=6+sources.findIndex(s=>s.video_id===longest.video_id);
const range=`N${row-1}:W${row+1}`;
const detail=await wb.render({sheetName:names[0],range,scale:1,format:'png'});
const detailPath=path.join(dir,'01_候选原因.png');await fs.writeFile(detailPath,new Uint8Array(await detail.arrayBuffer()));
outputs.push({sheet:names[0],range,path:detailPath});
await fs.writeFile(path.join(root,'manifest','workbook_visual_qa.json'),JSON.stringify({rendered_at:new Date().toISOString(),engine:'@oai/artifact-tool import+render',outputs,status:'RENDERED_PENDING_VISUAL_REVIEW'},null,2),'utf8');
console.log(JSON.stringify({sheets_rendered:new Set(outputs.map(o=>o.sheet)).size,previews:outputs.length,outputs},null,2));
const pngChecks=[];
for(const output of outputs){
  const bytes=await fs.readFile(output.path);
  const signature=[...bytes.subarray(0,8)];
  const valid=bytes.length>=1000&&[137,80,78,71,13,10,26,10].every((v,i)=>signature[i]===v);
  pngChecks.push({path:output.path,bytes:bytes.length,signature,valid});
}
await fs.writeFile(path.join(root,'manifest','render_run_result.json'),JSON.stringify({at:new Date().toISOString(),status:pngChecks.every(c=>c.valid)?'PASS':'FAIL',pngChecks},null,2),'utf8');
if(pngChecks.some(c=>!c.valid))throw new Error('Invalid PNG outputs; see render_run_result.json');
// All awaited imports, inspections, renders and output checks have succeeded.
// Explicitly end the bounded runner after artifact-tool's background workers.
process.exit(0);
