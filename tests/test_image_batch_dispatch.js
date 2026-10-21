const assert = require('node:assert/strict');
const { runImageBatch, imageBatchPowerShellQuote } = require('../scripts/image_batch_dispatch.js');
const fs = require('node:fs');
const path = require('node:path');
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  const events = [];
  let active = 0, peak = 0, failCount = 0, finalized = false;
  const prompts = ['p1', 'p2', 'p3', 'p4', 'p5', 'p6'];
  const local = async (command, args) => {
    if (command === 'plan') return { pending: prompts.map((p, i) => ({id:`shot_0${i+1}`,prompt:p})),
      active: [], failed: [], concurrency: 3, finalized: false };
    if (command === 'start') return {claimed:true,id:args.shotId,attempt:1};
    if (command === 'ingest') { await sleep(15); events.push(`archive:${args.shotId}`); return {}; }
    if (command === 'fail') { failCount++; return {}; }
    if (command === 'finalize') { finalized=true; return {done:true}; }
    throw new Error(command);
  };
  const generate = async ({id,prompt}) => {
    assert.equal(prompt, prompts[Number(id.slice(-2))-1]);
    events.push(`start:${id}`); active++; peak=Math.max(peak,active);
    await sleep(id==='shot_01' ? 80 : 5);
    active--; events.push(`returned:${id}`);
    return {source:`${id}.png`};
  };
  await runImageBatch({local,generate});
  assert.equal(peak,3); assert(finalized); assert.equal(failCount,0);
  assert(events.indexOf('start:shot_04') < events.indexOf('returned:shot_01'), 'must not wait for slow batch peer');
  assert(events.indexOf('start:shot_04') < events.indexOf('archive:shot_02'), 'archive must not hold generation slot');
  let zipAttempted=false;
  const failedLocal=async (command,args) => {
    if(command==='finalize') zipAttempted=true;
    return local(command,args);
  };
  await assert.rejects(runImageBatch({local:failedLocal, generate:async ({id}) => {
    if(id==='shot_03') throw Error('simulated failure'); return {source:id+'.png'};
  }}), /incomplete/);
  assert.equal(zipAttempted,false); assert.equal(failCount,1);
  assert.equal(imageBatchPowerShellQuote("a'b $() `x`"), "'a''b $() `x`'");
  assert.throws(()=>imageBatchPowerShellQuote('a\nb'));
  // Exercise the actual session adapter offline, including the tool's path hint.
  const submitted=[];
  const mockTools={
    exec_command:async ({cmd})=>{
      let value;
      if(cmd.includes("'plan'")) value={execution_mode:'live',pending:[{id:'shot_01',prompt:'EXACT SINGLE PROMPT'}],active:[],failed:[],concurrency:3,finalized:false};
      else if(cmd.includes("'start'")) value={claimed:true,id:'shot_01',attempt:1};
      else if(cmd.includes("'ingest'")) { assert(cmd.includes("'--received-at'")); value={}; }
      else if(cmd.includes("'finalize'")) value={T1:{elapsed_seconds:1},T2:{elapsed_seconds:0},T3:{elapsed_seconds:2}};
      else throw new Error('Unexpected command');
      return {exit_code:0,output:JSON.stringify(value)};
    },
    image_gen__imagegen:async args=>{submitted.push(args);return {output_hint:'Saved as relative/generated.png by default.'};}
  };
  const adapterSource=fs.readFileSync(path.join(__dirname,'../scripts/image_batch_dispatch.js'),'utf8');
  const adapter=new Function('tools','generatedImage',adapterSource+';return runImageBatchInCodex;')(mockTools,()=>{});
  await adapter({repoRoot:'.',runDir:'relative/run'});
  assert.deepEqual(submitted,[{prompt:'EXACT SINGLE PROMPT',transparent_background:false}]);
  console.log('PASS: window bound, immediate refill, archive overlap, prompt identity, failed-run gate, quoting');
}
main().catch(e=>{console.error(e); process.exitCode=1;});
