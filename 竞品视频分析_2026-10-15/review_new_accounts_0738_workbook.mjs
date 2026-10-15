import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const root=path.dirname(fileURLToPath(import.meta.url));
const phase=process.argv.includes('--after')?'after':'before';
const dir=path.join(path.dirname(root),'.local','competitor_review','new_accounts_2026-10-16_0738',phase);
await fs.mkdir(dir,{recursive:true});
const workbook=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(root,'阅见生活_竞品视频分析_终版.xlsx')));
workbook.recalculate();
const views=[['01_视频总览','A335:I342'],['02_带货脚本拆解','A338:F342'],['03_视觉模板','K338:V342'],
  ['04_账号对标与高频规律','A10:N13'],['06_异常待复核',phase==='after'?'A30:F34':'A25:F29'],['07_口径与运行摘要','A6:C17']];
const records=[];
for(let i=0;i<views.length;i++){
  const [sheetName,range]=views[i];
  const blob=await workbook.render({sheetName,range,scale:1});
  const target=path.join(dir,`${i+1}.png`);
  await fs.writeFile(target,new Uint8Array(await blob.arrayBuffer()));
  records.push({sheetName,range,path:target});
}
const inspection=await workbook.inspect({kind:'table',range:'07_口径与运行摘要!A6:C17',include:'values,formulas',tableMaxRows:12,tableMaxCols:3,maxChars:2400});
await fs.writeFile(path.join(dir,'inspection.txt'),inspection.ndjson??JSON.stringify(inspection));
await fs.writeFile(path.join(dir,'render.json'),JSON.stringify({phase,recalculate_called:true,records},null,2));
console.log(JSON.stringify({phase,saved_previews:records.length}));
