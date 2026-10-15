import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath}from'node:url';
import{FileBlob,SpreadsheetFile}from'@oai/artifact-tool';
const root=path.dirname(fileURLToPath(import.meta.url));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(root,'阅见生活_竞品视频分析_终版.xlsx')));
const names=['01_视频总览','02_带货脚本拆解','03_视觉模板','04_账号对标与高频规律','05_原创带货模板库','06_异常待复核','07_口径与运行摘要'];
const ranges=['A1:I10','A1:L10','A1:P10','A1:M12','A1:J10','A1:F10','A1:C20'];
const out=path.join(root,'reports','phase4_workbook_previews_final');await fs.mkdir(out,{recursive:true});
const results=[];
async function render(sheet,range,name){const blob=await wb.render({sheetName:sheet,range,scale:1,format:'png'});const target=path.join(out,name+'.png');await fs.writeFile(target,new Uint8Array(await blob.arrayBuffer()));results.push({sheet,range,path:target});}
for(let i=0;i<names.length;i++)await render(names[i],ranges[i],names[i]);
const rows=(await fs.readFile(path.join(root,'manifest','manifest.jsonl'),'utf8')).trim().split(/\r?\n/).map(JSON.parse);
const row=6+rows.findIndex(x=>x.video_id==='v_183328bf0ee8b458');
await render(names[1],`A${row}:L${row+1}`,'02_深度样本导入');
await render(names[2],`K${row}:U${row+1}`,'03_核验边界');
await render(names[4],'K1:Q10','05_原创建议与证据');
const info=await wb.inspect({kind:'sheet',include:'id,name',maxChars:3000});await fs.writeFile(path.join(out,'sheet_inspection.txt'),info.ndjson??JSON.stringify(info),'utf8');
await fs.writeFile(path.join(root,'manifest','phase4_visual_qa.json'),JSON.stringify({at:new Date().toISOString(),engine:'artifact-tool import/render',sheets_rendered:7,previews:results,status:'RENDERED_PENDING_REVIEW'},null,2),'utf8');
console.log(JSON.stringify({sheets:7,previews:results.length}));

