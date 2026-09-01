const fileInput = document.getElementById("file");
const drop = document.getElementById("drop");
const fileName = document.getElementById("file-name");
const run = document.getElementById("run");
const sample = document.getElementById("sample");
const form = document.getElementById("upload-form");
const uploadPanel = document.getElementById("upload-panel");
const progressPanel = document.getElementById("progress-panel");
const errorPanel = document.getElementById("error-panel");
const resultPanel = document.getElementById("result-panel");
const progressTitle = document.getElementById("progress-title");
const progressCopy = document.getElementById("progress-copy");
const barFill = document.getElementById("bar-fill");
const errorCopy = document.getElementById("error-copy");

const STAGE_COPY = {
  upload: "Saving the original file…",
  qa: "Data QA Agent is mapping, validating, and standardising the extract…",
  report: "Report Agent is writing the PDF presentation…",
  done: "Done.",
  error: "Stopped.",
};

function show(panel) {
  for (const node of [uploadPanel, progressPanel, errorPanel, resultPanel]) {
    node.classList.toggle("hidden", node !== panel);
  }
}

function setSteps(stage) {
  const order = ["upload", "qa", "report", "done"];
  const current = order.includes(stage) ? stage : "upload";
  const idx = order.indexOf(current);
  document.querySelectorAll(".steps li").forEach((li) => {
    const step = li.getAttribute("data-step");
    const i = order.indexOf(step);
    li.classList.toggle("is-active", step === current);
    li.classList.toggle("is-done", i < idx);
  });
  barFill.style.width = `${Math.max(12, ((idx + 1) / order.length) * 100)}%`;
}

function reset() {
  fileInput.value = "";
  fileName.hidden = true;
  run.disabled = true;
  show(uploadPanel);
  setSteps("upload");
}

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  run.disabled = !file;
  if (file) {
    fileName.hidden = false;
    fileName.textContent = file.name;
  }
});

["dragenter", "dragover"].forEach((eventName) => {
  drop.addEventListener(eventName, (event) => {
    event.preventDefault();
    drop.classList.add("is-over");
  });
});
["dragleave", "drop"].forEach((eventName) => {
  drop.addEventListener(eventName, (event) => {
    event.preventDefault();
    drop.classList.remove("is-over");
  });
});
drop.addEventListener("drop", (event) => {
  const file = event.dataTransfer.files[0];
  if (!file) return;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  fileInput.files = transfer.files;
  fileInput.dispatchEvent(new Event("change"));
});

async function startJob(request) {
  show(progressPanel);
  setSteps("upload");
  progressTitle.textContent = "Working";
  progressCopy.textContent = STAGE_COPY.upload;
  const response = await fetch(request.url, request.init);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Upload failed");
  }
  await poll(payload.job_id);
}

async function poll(jobId) {
  for (;;) {
    const response = await fetch(`/api/jobs/${jobId}`);
    const job = await response.json();
    if (!response.ok) throw new Error(job.detail || "Lost the job");
    setSteps(job.stage || "qa");
    progressCopy.textContent = STAGE_COPY[job.stage] || "Working…";
    if (job.state === "done") {
      renderResult(job);
      return;
    }
    if (job.state === "error") {
      throw new Error(job.error || "The agents could not finish this file");
    }
    await new Promise((resolve) => setTimeout(resolve, 800));
  }
}

function money(value) {
  if (value >= 1e9) return `R${(value / 1e9).toFixed(1)}bn`;
  if (value >= 1e6) return `R${(value / 1e6).toFixed(1)}m`;
  if (value >= 1e3) return `R${(value / 1e3).toFixed(0)}k`;
  return `R${Math.round(value).toLocaleString()}`;
}

function renderResult(job) {
  const result = job.result || {};
  show(resultPanel);
  setSteps("done");
  document.getElementById("result-file").textContent = result.source_name || job.filename || "";
  document.getElementById("result-status").textContent = (result.status || "").replaceAll("_", " ");
  document.getElementById("score-value").textContent = result.quality_score ?? "—";
  const snap = result.snapshot || {};
  const metrics = [
    ["Clean rows", (result.row_count_clean || 0).toLocaleString()],
    ["Dropped", (result.rows_dropped || 0).toLocaleString()],
    ["Dates", String(result.distinct_dates || 0)],
    ["Value", snap.has_data ? money(snap.total_value || 0) : "—"],
    ["Products", snap.has_data ? String(snap.n_products || 0) : "—"],
    ["Retailers", snap.has_data ? String(snap.n_retailers || 0) : "—"],
  ];
  document.getElementById("metrics").innerHTML = metrics
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`)
    .join("");
  const caps = result.capabilities || {};
  document.getElementById("caps").innerHTML = Object.entries(caps)
    .map(([name, on]) => `<li class="${on ? "ready" : "blocked"}">${name.replaceAll("_", " ")} · ${on ? "ready" : "blocked"}</li>`)
    .join("");
  const issues = [...(result.critical_issues || []), ...(result.warnings || []), ...(result.info || [])];
  document.getElementById("issues").innerHTML = issues.length
    ? issues
        .slice(0, 8)
        .map((issue) => `<li><span class="sev">${issue.severity}</span>${issue.message}</li>`)
        .join("")
    : "<li>No issues recorded.</li>";
  const jobId = job.job_id;
  const links = [`<a href="/api/jobs/${jobId}/pdf">Download PDF</a>`];
  if (result.has_clean) links.push(`<a class="secondary" href="/api/jobs/${jobId}/clean">Clean CSV</a>`);
  links.push(`<a class="secondary" href="/api/jobs/${jobId}/qa">QA JSON</a>`);
  document.getElementById("downloads").innerHTML = links.join("");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file) return;
  run.disabled = true;
  try {
    const body = new FormData();
    body.append("file", file);
    await startJob({ url: "/api/jobs", init: { method: "POST", body } });
  } catch (err) {
    errorCopy.textContent = err.message;
    show(errorPanel);
  } finally {
    run.disabled = !fileInput.files[0];
  }
});

sample.addEventListener("click", async () => {
  try {
    await startJob({ url: "/api/jobs/sample", init: { method: "POST" } });
  } catch (err) {
    errorCopy.textContent = err.message;
    show(errorPanel);
  }
});

document.getElementById("retry").addEventListener("click", reset);
document.getElementById("again").addEventListener("click", reset);
