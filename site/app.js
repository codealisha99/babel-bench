// Playground. API_BASE is the babel-bench API, a Vercel Python function. Responses are written with
// textContent only. If the API cannot be reached, the playground says so and the evidence stays readable.
const API_BASE = "https://babel-bench-api.vercel.app";
const MAX_SEED = 99999;

const $ = (id) => document.getElementById(id);
const els = {
  seed: $("seed"), roll: $("roll"), load: $("load"), langName: $("lang-name"), manual: $("manual"),
  task: $("task"), statement: $("task-statement"), program: $("program"), run: $("run"),
  result: $("result"), status: $("api-status"),
};

function setStatus(text) {
  els.status.hidden = !text;
  els.status.textContent = text || "";
}

function apiAvailable() {
  return API_BASE !== "";
}

async function getJSON(path) {
  const res = await fetch(API_BASE + path, { headers: { Accept: "application/json" } });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `request failed (${res.status})`);
  return body;
}

function currentSeed() {
  const value = Number(els.seed.value);
  return Number.isInteger(value) && value >= 0 && value <= MAX_SEED ? value : null;
}

function renderTasks(tasks) {
  els.task.replaceChildren();
  for (const t of tasks) {
    const opt = document.createElement("option");
    opt.value = t.id;
    opt.textContent = t.runnable ? t.id : `${t.id} (not graded here)`;
    opt.disabled = !t.runnable;
    els.task.append(opt);
  }
  const first = tasks.find((t) => t.runnable);
  if (first) els.task.value = first.id;
  els.task.disabled = false;
  els.program.disabled = false;
  els.run.disabled = false;
  showTask();
}

let tasksById = {};

function showTask() {
  const t = tasksById[els.task.value];
  if (!t) return;
  let text = t.statement;
  if (t.visible && t.visible.length) {
    text += " Visible examples: " + t.visible.map((v) => `solve(${v.args.join(", ")}) returns ${v.expected}`).join("; ") + ".";
  }
  els.statement.textContent = text;
  els.program.placeholder = t.kind === "code" && t.shown ? t.shown : "";
}

async function loadLanguage() {
  const seed = currentSeed();
  if (seed === null) {
    els.langName.textContent = `Enter a whole number from 0 to ${MAX_SEED}.`;
    return;
  }
  if (!apiAvailable()) {
    els.langName.textContent = "";
    setStatus("The playground API is unavailable. Run the benchmark locally with babel-bench show --seed N --manual.");
    return;
  }
  try {
    const [lang, listing] = await Promise.all([
      getJSON(`/api/languages/${seed}`),
      getJSON(`/api/languages/${seed}/tasks`),
    ]);
    els.langName.textContent = `${lang.name} (seed ${lang.seed})`;
    els.manual.textContent = lang.manual;
    tasksById = Object.fromEntries(listing.tasks.map((t) => [t.id, t]));
    renderTasks(listing.tasks);
    setStatus("");
  } catch (err) {
    setStatus(`Could not load seed ${seed}: ${err.message}`);
  }
}

async function runProgram() {
  const seed = currentSeed();
  els.run.disabled = true;
  els.result.textContent = "Running...";
  try {
    const body = await fetch(API_BASE + "/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seed, task_id: els.task.value, program: els.program.value }),
    });
    const data = await body.json().catch(() => ({}));
    if (!body.ok) throw new Error(data.detail || `request failed (${body.status})`);
    renderResult(data);
  } catch (err) {
    els.result.textContent = `Not graded: ${err.message}`;
  } finally {
    els.run.disabled = false;
  }
}

function renderResult(data) {
  els.result.replaceChildren();
  const verdict = document.createElement("p");
  verdict.className = data.passed ? "pass" : "fail";
  verdict.textContent = `${data.passed ? "Passed" : "Failed"}: ${data.tests_passed} of ${data.tests_total} tests`;
  els.result.append(verdict);
  if (data.feedback) {
    const fb = document.createElement("pre");
    fb.textContent = data.feedback;
    els.result.append(fb);
  }
  if (data.output) {
    const label = document.createElement("p");
    label.className = "note";
    label.textContent = "Your program printed:";
    const out = document.createElement("pre");
    out.textContent = data.output;
    els.result.append(label, out);
  }
}

els.roll.addEventListener("click", () => {
  els.seed.value = String(Math.floor(Math.random() * (MAX_SEED + 1)));
  loadLanguage();
});
els.load.addEventListener("click", loadLanguage);
els.task.addEventListener("change", showTask);
els.run.addEventListener("click", runProgram);

if (!apiAvailable()) {
  els.load.disabled = true;
  els.roll.disabled = true;
  setStatus("The playground API is not configured on this page.");
}
