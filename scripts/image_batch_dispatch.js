/* Session-side sliding window. No API keys, SDK runner, or prompt rewriting. */
async function runImageBatch({ local, generate, concurrency, phase = "initial" }) {
  if (phase !== "initial") throw new Error("Repair submissions use the explicit per-shot repair flow");
  const plan = await local("plan", {});
  if (Number.isInteger(plan.total) &&
      plan.pending.length + plan.active.length + plan.failed.length + plan.archived.length !== plan.total) {
    throw new Error("Incomplete plan response; refusing to dispatch a truncated shot list");
  }
  if (plan.finalized) return await local("finalize", {});
  if (plan.active.length || plan.failed.length) {
    throw new Error("Resolve interrupted or failed shots before dispatching (resume/retry-repair)");
  }
  const width = concurrency ?? plan.concurrency ?? 3;
  if (!Number.isInteger(width) || width < 1 || width > 4) throw new Error("Concurrency must be 1..4");
  const jobs = plan.pending;
  let cursor = 0;
  let archiveQueue = Promise.resolve();
  const errors = [];
  const fail = async (claim, code) => {
    try {
      await local("fail", { shotId: claim.id, attempt: claim.attempt, error: code });
    } catch (_) {
      errors.push({ id: claim.id, stage: "failure_recording" });
    }
  };
  const worker = async () => {
    while (cursor < jobs.length) {
      const job = jobs[cursor++];
      let claim;
      try {
        claim = await local("start", { shotId: job.id });
        if (!claim.claimed) continue;
        // Submission identity is bound before generation, never by completion order.
        const result = await generate({ id: job.id, prompt: job.prompt, claim });
        const receivedAt = result.receivedAt || new Date().toISOString();
        if (!result.source) throw new Error("No generated source path");
        // Archive jobs serialize DB/file writes but never block window replenishment.
        archiveQueue = archiveQueue.then(async () => {
          try {
            await local("ingest", { shotId: job.id, attempt: claim.attempt,
              source: result.source, receivedAt });
          } catch (_) {
            errors.push({ id: job.id, stage: "archive" });
            await fail(claim, "archive_failed");
          }
        });
      } catch (_) {
        errors.push({ id: job.id, stage: "generation_or_claim" });
        if (claim?.claimed) await fail(claim, "generation_failed");
      }
    }
  };
  await Promise.all(Array.from({ length: Math.min(width, jobs.length) }, worker));
  await archiveQueue;
  if (errors.length) {
    const error = new Error("Batch incomplete; successful shots preserved; no final ZIP created");
    error.failures = errors;
    throw error;
  }
  return await local("finalize", {});
}

function imageBatchPowerShellQuote(value) {
  const text = String(value);
  if (/[\0\r\n]/.test(text)) throw new Error("Invalid shell argument");
  return "'" + text.replace(/'/g, "''") + "'";
}

async function runImageBatchInCodex({ repoRoot, runDir, concurrency,
  pythonExecutable = ".venv/Scripts/python.exe", emitImages = true }) {
  if (typeof tools === "undefined") throw new Error("Load this adapter inside functions.exec");
  const local = async (command, args) => {
    const words = [pythonExecutable, "scripts/image_batch_pipeline.py", command, "--run-dir", runDir];
    for (const [key, value] of Object.entries(args)) {
      const flag = "--" + key.replace(/[A-Z]/g, x => "-" + x.toLowerCase());
      words.push(flag, String(value));
    }
    const result = await tools.exec_command({
      cmd: "& " + words.map(imageBatchPowerShellQuote).join(" "), workdir: repoRoot,
      max_output_tokens: command === "plan" ? 32000 : 2500, yield_time_ms: 1000
    });
    let output = result.output || "";
    let status = result;
    while (status.session_id && status.exit_code == null) {
      status = await tools.write_stdin({ session_id: status.session_id, chars: "",
        yield_time_ms: 1000, max_output_tokens: command === "plan" ? 32000 : 2500 });
      output += status.output || "";
    }
    if (/Warning: truncated output|bytes omitted|tokens truncated/.test(output)) {
      throw new Error("Truncated local response; refusing partial plan or prompt");
    }
    const lines = output.split(/\r?\n/).filter(s => s.trim().startsWith("{"));
    let parsed;
    try { parsed = JSON.parse(lines.at(-1)); } catch (_) { throw new Error("Local pipeline returned no JSON"); }
    if (status.exit_code !== 0 || parsed.error) throw new Error("Local pipeline rejected " + command);
    return parsed;
  };
  const plan = await local("plan", {});
  if (plan.execution_mode !== "live") throw new Error("Live tools cannot run a replay batch");
  const generate = async ({ prompt }) => {
    // The single-shot prompt is passed verbatim; no family/global prompt is appended.
    const result = await tools.image_gen__imagegen({ prompt, transparent_background: false });
    const receivedAt = new Date().toISOString();
    const match = result.output_hint?.match(/ as (.+?\.png) by default/);
    if (!match) throw new Error("Tool returned no recognized saved path; do not guess the newest file");
    if (emitImages && typeof generatedImage === "function") generatedImage(result);
    return { source: match[1], receivedAt };
  };
  const report = await runImageBatch({ local, generate, concurrency });
  if (typeof text === "function") {
    for (const [key, label] of [["T1", "初版出齐耗时"], ["T2", "修图耗时"], ["T3", "归档打包耗时"]]) {
      const phase = report[key];
      text(`[${key}: ${label}] ${phase.elapsed_seconds}秒 | ${phase.started_at} → ${phase.finished_at}`);
    }
  }
  return report;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { runImageBatch, runImageBatchInCodex, imageBatchPowerShellQuote };
}
