import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const r=path.dirname(fileURLToPath(import.meta.url));const phase=process.argv.includes('--after')?'after':'before';
const out=path.join(path.dirname(r),'.local','competitor_review','history_city_2026-10-19',phase);await fs.mkdir(out,{recursive:true});
const w=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(r,'阅见生活_竞品视频分析_终版.xlsx')));w.recalculate();
const views=[['01_视频总览','A418:I421'],['02_带货脚本拆解','A419:L421'],['03_视觉模板','K419:V421'],['04_账号对标与高频规律','A291:N294'],['06_异常待复核','A110:F116'],['07_口径与运行摘要','A12:C17']];
for(let i=0;i<views.length;i++){if(process.argv.includes('--summary-only')&&i!==5)continue;const[sheetName,range]=views[i];const b=await w.render({sheetName,range,scale:1});await fs.writeFile(path.join(out,`${i+1}.png`),new Uint8Array(await b.arrayBuffer()));}
const t=await w.inspect({kind:'table',range:'07_口径与运行摘要!A12:C17',include:'values,formulas',tableMaxRows:6,tableMaxCols:3,maxChars:1800});
await fs.writeFile(path.join(out,'inspection.txt'),t.ndjson??JSON.stringify(t));await fs.writeFile(path.join(out,'render.json'),JSON.stringify({phase,count:views.length,recalculate_called:true},null,2));console.log(JSON.stringify({phase,rendered:views.length}));
