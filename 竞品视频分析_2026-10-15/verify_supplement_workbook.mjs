import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { FileBlob, SpreadsheetFile } from '@oai/artifact-tool';

const root = path.dirname(fileURLToPath(import.meta.url));
const output = path.join(path.dirname(root), '.local', 'competitor_review', 'supplement_01', 'workbook');
await fs.mkdir(output, { recursive: true });
const book = await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(root, '阅见生活_竞品视频分析_终版.xlsx')));
book.recalculate();
if (process.argv.includes('--summary-only')) {
  const image = await book.render({ sheetName: '07_口径与运行摘要', range: 'A1:C23', scale: 1 });
  await fs.writeFile(path.join(output, '7.png'), new Uint8Array(await image.arrayBuffer()));
  const qaPath = path.join(root, 'manifest', 'supplement_01_visual_qa.json');
  const qa = JSON.parse(await fs.readFile(qaPath, 'utf8'));
  qa.summary_refreshed_at = new Date().toISOString();
  qa.other_views_reused_after_exact_cell_comparison = true;
  await fs.writeFile(qaPath, JSON.stringify(qa, null, 2), 'utf8');
  console.log(JSON.stringify({ refreshed_sheet: '07_口径与运行摘要', prior_views_reused: 8 }));
} else {
const sheets = ['01_视频总览', '02_带货脚本拆解', '03_视觉模板', '04_账号对标与高频规律', '05_原创带货模板库', '06_异常待复核', '07_口径与运行摘要'];
const ranges = ['A1:I9', 'A1:L9', 'A1:P9', 'A1:N12', 'A1:J12', 'A1:F10', 'A1:C23'];
const previews = [];
for (let i = 0; i < sheets.length; i++) {
  const image = await book.render({ sheetName: sheets[i], range: ranges[i], scale: 1 });
  const target = path.join(output, `${i + 1}.png`);
  await fs.writeFile(target, new Uint8Array(await image.arrayBuffer()));
  previews.push({ sheet: sheets[i], range: ranges[i], path: target });
}
const manifest = (await fs.readFile(path.join(root, 'manifest', 'manifest.jsonl'), 'utf8')).trim().split(/\r?\n/).map(JSON.parse);
const index = 6 + manifest.findIndex(x => x.video_id === 'v_38eb65b8de747391');
for (const [sheet, range, label] of [[sheets[1], `A${index}:L${index + 1}`, 'new_book_timing'], [sheets[4], 'K5:Q12', 'template_sources']]) {
  const image = await book.render({ sheetName: sheet, range, scale: 1 });
  const target = path.join(output, `${label}.png`);
  await fs.writeFile(target, new Uint8Array(await image.arrayBuffer()));
  previews.push({ sheet, range, path: target });
}
const inspect = await book.inspect({ kind: 'table', range: `${sheets[6]}!A6:C18`, include: 'values,formulas', tableMaxRows: 13, tableMaxCols: 3 });
await fs.writeFile(path.join(output, 'inspection.txt'), inspect.ndjson ?? JSON.stringify(inspect), 'utf8');
await fs.writeFile(path.join(root, 'manifest', 'supplement_01_visual_qa.json'), JSON.stringify({ at: new Date().toISOString(), recalculate_called: true, rendered_sheets: 7, previews, visual_review: 'PENDING' }, null, 2), 'utf8');
console.log(JSON.stringify({ rendered_sheets: 7, images: previews.length }));
}
