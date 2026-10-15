import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const root=path.dirname(fileURLToPath(import.meta.url));
const before=process.argv.includes('--before');
const directory=path.join(path.dirname(root),'.local','competitor_review','new_accounts_2026-10-16',before?'before':'after');
await fs.mkdir(directory,{recursive:true});
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(root,'阅见生活_竞品视频分析_终版.xlsx')));
book.recalculate();
const names=['01_视频总览','02_带货脚本拆解','03_视觉模板','04_账号对标与高频规律','06_异常待复核','07_口径与运行摘要'];
const qa=[];
const ranges=before?['A1:I9','A1:L9','A1:P9','A1:N10','A1:F9','A1:C23']:['A336:I342','A336:L342','A336:P342','A1:N14','A24:F31','A1:C23'];
for(let i=0;i<names.length;i++){
  const blob=await book.render({sheetName:names[i],range:ranges[i],scale:1});
  const target=path.join(directory,`${i+1}.png`);
  await fs.writeFile(target,new Uint8Array(await blob.arrayBuffer()));
  qa.push({sheet:names[i],range:ranges[i],path:target});
}
const inspect=await book.inspect({kind:'table',range:'07_口径与运行摘要!A6:C18',include:'values,formulas',tableMaxRows:13,tableMaxCols:3,maxChars:4500});
await fs.writeFile(path.join(directory,'inspection.txt'),inspect.ndjson??JSON.stringify(inspect));
await fs.writeFile(path.join(directory,'render.json'),JSON.stringify({at:new Date().toISOString(),before,recalculate_called:true,previews:qa},null,2));
console.log(JSON.stringify({before,rendered_sheets:qa.length}));
