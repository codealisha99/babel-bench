// Landing page: hero re-roll and rules matrix (static data built by babel_bench.showcase), and the
// playground, which calls the babel-bench API. Everything is written with textContent, never innerHTML.
const API_BASE = "https://babel-bench-api.vercel.app";
const MAX_SEED = 99999;
const LINE_PX = 22;          // must match --lh in styles.css
const EDITOR_PAD_PX = 12;    // vertical padding of the editor, matches styles.css
const COLD_START_MS = 2500;  // after this, tell the visitor the grader may be waking up
const REQUEST_TIMEOUT_MS = 30000;
const NARROW = window.matchMedia("(max-width: 759px)");

const $ = (id) => document.getElementById(id);
const el = {
  specimen: $("specimen"), specimenTitle: $("specimen-title"), reroll: $("reroll"),
  heroProgram: $("hero-program"), heroOutput: $("hero-output"), heroChips: $("hero-chips"), heroOpen: $("hero-open"),
  featureBody: $("feature-body"), probeBody: $("probe-body"),
  seed: $("seed"), roll: $("roll"), load: $("load"), langName: $("lang-name"), status: $("api-status"),
  manualWrap: $("manual-wrap"), manual: $("manual"), manualIndex: $("manual-index"), manualMeta: $("manual-meta"),
  task: $("task"), taskKind: $("task-kind"), statement: $("task-statement"),
  predictView: $("predict-view"), predictProgram: $("predict-program").querySelector("code"),
  editorHead: $("editor-head"), editor: $("editor"), starter: $("starter"), starterNote: $("starter-note"),
  gutterInner: $("gutter-inner"), program: $("program"), band: $("err-band"),
  runRow: document.querySelector(".run-row"), run: $("run"), errorLine: $("error-line"), result: $("result"),
};

let showcase = null;
let heroIndex = 0;
let tasksById = {};

// ---------- small helpers

function el_(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function requestJSON(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal, headers: { Accept: "application/json", ...(options.headers || {}) } });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.detail || `request failed (${res.status})`);
    return body;
  } catch (err) {
    if (err.name === "AbortError") throw new Error(`no answer within ${REQUEST_TIMEOUT_MS / 1000} seconds`);
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

const getJSON = (path) => requestJSON(API_BASE + path);
const postJSON = (path, body) => requestJSON(API_BASE + path, {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

function setStatus(text) {
  el.status.hidden = !text;
  el.status.textContent = text || "";
}

function currentSeed() {
  const value = Number(el.seed.value);
  return Number.isInteger(value) && value >= 0 && value <= MAX_SEED ? value : null;
}

function seedFromURL() {
  const raw = new URLSearchParams(location.search).get("seed");
  const value = Number(raw);
  return raw !== null && Number.isInteger(value) && value >= 0 && value <= MAX_SEED ? value : null;
}

// ---------- hero: the same program in another generated language

const HERO_CHIPS = ["index base", "integer division", "zero is", "and/or result", "precedence", "blocks"];

function renderChips(features) {
  el.heroChips.replaceChildren(...HERO_CHIPS.map((key) => {
    const li = el_("li");
    li.append(el_("span", "", `${key}: `), document.createTextNode(features[key]));
    return li;
  }));
}

function showHero(index) {
  const lang = showcase.languages[index];
  heroIndex = index;
  el.specimen.classList.remove("swap");
  void el.specimen.offsetWidth; // restart the fade
  el.specimen.classList.add("swap");
  el.specimenTitle.replaceChildren(el_("span", "lang-name", lang.name), document.createTextNode(" "), el_("span", "meta", `seed ${lang.seed}`));
  el.heroProgram.querySelector("code").textContent = lang.program;
  el.heroOutput.querySelector("code").textContent = lang.output;
  renderChips(lang.features);
  el.heroOpen.href = `?seed=${lang.seed}#playground`;
  el.reroll.textContent = "New language";
  el.reroll.setAttribute("aria-label", `New language. Showing language ${index + 1} of ${showcase.languages.length}`);
}

function rerollHero() {
  const n = showcase.languages.length;
  let next = Math.floor(Math.random() * (n - 1));
  if (next >= heroIndex) next += 1; // never repeat the current language
  showHero(next);
}

// ---------- rules matrix: seeds side by side

function renderFeatureMatrix(seeds) {
  const langs = seeds.map((s) => showcase.languages.find((l) => l.seed === s));
  seeds.forEach((s, i) => {
    const head = $(`fm-s${i + 1}`);
    head.textContent = langs[i] ? `${langs[i].name}, seed ${s}` : `Seed ${s}`;
  });
  const keys = Object.keys(langs[0].features);
  el.featureBody.replaceChildren(...keys.map((key) => {
    const values = langs.map((l) => (l ? l.features[key] : "n/a"));
    const differs = new Set(values).size > 1;
    const tr = el_("tr");
    tr.append(el_("th", "", key));
    values.forEach((v) => {
      const td = el_("td", differs ? "diff" : "");
      td.append(el_("span", "val", v));
      tr.append(td);
    });
    return tr;
  }));
}

function renderProbeMatrix(seeds) {
  const langs = seeds.map((s) => showcase.languages.find((l) => l.seed === s));
  const probes = langs[0].probes;
  el.probeBody.replaceChildren(...probes.map((probe, row) => {
    const cells = langs.map((l) => l && l.probes[row]);
    const outputs = new Set(cells.map((c) => (c ? c.output : "")));
    const tr = el_("tr");
    tr.append(el_("th", "", probe.label));
    cells.forEach((c) => {
      const td = el_("td", outputs.size > 1 ? "diff" : "");
      if (!c) { td.textContent = "n/a"; tr.append(td); return; }
      td.append(el_("span", "src", c.source));
      const out = el_("span", "out", "prints ");
      out.append(el_("b", "", c.output));
      td.append(out);
      tr.append(td);
    });
    return tr;
  }));
}

async function loadShowcase() {
  try {
    const res = await fetch("data/showcase.json");
    if (!res.ok) throw new Error(`status ${res.status}`);
    showcase = await res.json();
  } catch (err) {
    el.reroll.hidden = true;
    const failed = "The generated rules could not be loaded. The evidence below still stands.";
    el.featureBody.replaceChildren(el_("tr", "", ""));
    el.featureBody.firstChild.append(el_("td", "loading", failed));
    el.probeBody.replaceChildren();
    return; // the static specimen stays
  }
  const seeds = showcase.feature_seeds;
  renderFeatureMatrix(seeds);
  renderProbeMatrix(seeds);
  el.reroll.disabled = false;
  const requested = seedFromURL();
  const start = showcase.languages.findIndex((l) => l.seed === requested);
  showHero(start >= 0 ? start : 0);
}

// ---------- manual: sections with a jump index

// Inline `code` spans in manual prose become <code> elements; everything else stays text.
function prose(tag, text) {
  const node = el_(tag);
  text.split("`").forEach((part, i) => {
    if (!part) return;
    node.append(i % 2 ? el_("code", "", part) : document.createTextNode(part));
  });
  return node;
}

function slug(text) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "section";
}

function renderManual(text) {
  const nodes = [];
  const chips = [];
  let code = null;
  let list = null;
  const lines = text.split("\n");
  for (const line of lines) {
    if (line.startsWith("```")) {
      if (code) { code = null; continue; }
      code = el_("pre");
      code.append(el_("code"));
      nodes.push(code);
      list = null;
      continue;
    }
    if (code) { code.firstChild.textContent += (code.firstChild.textContent ? "\n" : "") + line; continue; }
    if (!line.trim()) { list = null; continue; }
    if (line.startsWith("## ") || line.startsWith("# ")) {
      const title = line.replace(/^#+ /, "");
      const heading = el_("h3", "", title);
      heading.id = `sec-${slug(title)}`;
      nodes.push(heading);
      chips.push([title, heading.id]);
      list = null;
    } else if (line.startsWith("### ")) {
      nodes.push(el_("h4", "", line.slice(4)));
      list = null;
    } else if (line.startsWith("- ")) {
      if (!list) { list = el_("ul"); nodes.push(list); }
      list.append(prose("li", line.slice(2)));
    } else {
      nodes.push(prose("p", line));
      list = null;
    }
  }
  el.manual.replaceChildren(...nodes);
  el.manual.scrollTop = 0;
  el.manualIndex.replaceChildren(...(chips.length
    ? chips.map(([title, id]) => { const a = el_("a", "", title); a.href = `#${id}`; return a; })
    : [el_("span", "meta", "No sections in this manual.")]));
  el.manualMeta.textContent = `${lines.length} lines`;
}

// ---------- language and tasks

function renderTasks(tasks) {
  el.task.replaceChildren(...tasks.map((t) => {
    const opt = el_("option", "", t.runnable ? t.id : `${t.id} (read only)`);
    opt.value = t.id;
    return opt;
  }));
  const first = tasks.find((t) => t.runnable) || tasks[0];
  el.task.value = first.id;
  el.task.disabled = false;
  showTask();
}

function showTask() {
  const t = tasksById[el.task.value];
  if (!t) return;
  let text = t.statement;
  if (t.visible && t.visible.length) {
    text += " Visible examples: " + t.visible.map((v) => `solve(${v.args.join(", ")}) returns ${v.expected}`).join("; ") + ".";
  }
  el.statement.textContent = text;
  el.taskKind.textContent = `${t.tier}, ${t.runnable ? `graded here against ${t.hidden_tests} hidden tests` : "read only, not graded"}`;
  clearResult();
  const writing = t.runnable;
  el.predictView.hidden = writing;
  el.predictProgram.textContent = writing ? "" : (t.shown || "");
  el.editorHead.hidden = !writing;
  el.editor.hidden = !writing;
  el.runRow.hidden = !writing;
  el.starterNote.hidden = true;
  el.starter.disabled = !writing;
  el.program.disabled = !writing;
  el.run.disabled = !writing;
  el.program.placeholder = writing ? "Write your program here, or press Show me a starter." : "";
  updateGutter();
}

async function loadLanguage() {
  const seed = currentSeed();
  if (seed === null) {
    el.langName.textContent = `Enter a whole number from 0 to ${MAX_SEED}.`;
    return;
  }
  setStatus("");
  el.langName.textContent = `Loading seed ${seed}...`;
  el.load.disabled = true;
  el.roll.disabled = true;
  const slow = setTimeout(() => setStatus("The grader is waking up. The first request after a quiet spell can take up to 10 seconds."), COLD_START_MS);
  try {
    const [lang, listing] = await Promise.all([
      getJSON(`/api/languages/${seed}`),
      getJSON(`/api/languages/${seed}/tasks`),
    ]);
    el.langName.textContent = `${lang.name}, seed ${lang.seed}`;
    renderManual(lang.manual);
    tasksById = Object.fromEntries(listing.tasks.map((t) => [t.id, t]));
    renderTasks(listing.tasks);
    history.replaceState(null, "", `?seed=${seed}#playground`);
  } catch (err) {
    el.langName.textContent = "";
    setStatus(`Could not load seed ${seed}: ${err.message}. Run it locally with babel-bench show --seed ${seed} --manual.`);
  } finally {
    clearTimeout(slow);
    el.load.disabled = false;
    el.roll.disabled = false;
  }
}

// ---------- editor: line numbers, error band, starter

function updateGutter() {
  const count = Math.max(1, el.program.value.split("\n").length);
  el.gutterInner.replaceChildren(...Array.from({ length: count }, (_, i) => el_("span", "", String(i + 1))));
  syncScroll();
}

function syncScroll() {
  const top = el.program.scrollTop;
  el.gutterInner.style.transform = `translateY(${-top}px)`;
  const line = el.band.dataset.line ? Number(el.band.dataset.line) : 0;
  if (line) {
    const y = EDITOR_PAD_PX + (line - 1) * LINE_PX - top;
    el.band.style.top = `${y}px`;
    el.band.hidden = y < 0 || y > el.program.clientHeight;
  }
}

function markLine(line) {
  clearLineMark();
  if (!line) return;
  el.band.dataset.line = String(line);
  el.band.hidden = false;
  const span = el.gutterInner.children[line - 1];
  if (span) span.classList.add("err");
  syncScroll();
}

function clearLineMark() {
  delete el.band.dataset.line;
  el.band.hidden = true;
  el.gutterInner.querySelectorAll(".err").forEach((n) => n.classList.remove("err"));
}

function goToLine(line) {
  const lines = el.program.value.split("\n");
  const offset = lines.slice(0, line - 1).reduce((sum, l) => sum + l.length + 1, 0);
  el.program.focus();
  el.program.setSelectionRange(offset, offset + (lines[line - 1] || "").length);
  el.program.scrollTop = Math.max(0, (line - 4) * LINE_PX);
  syncScroll();
}

async function insertStarter() {
  const t = tasksById[el.task.value];
  const seed = currentSeed();
  if (!t || !t.runnable || seed === null) return;
  if (el.program.value.trim() && !window.confirm("Replace your program with a starter?")) return;
  el.starter.disabled = true;
  try {
    const data = await getJSON(`/api/languages/${seed}/tasks/${encodeURIComponent(t.id)}/starter`);
    el.program.value = data.program;
    updateGutter();
    clearResult();
    el.starterNote.textContent = t.tier === "fix"
      ? "This is the buggy program from the task. Find the bug and reply with the whole corrected program."
      : "A skeleton: every function header is in place and each body returns 0. Fill in the body; it does not solve the task.";
    el.starterNote.hidden = false;
    el.program.focus();
  } catch (err) {
    setStatus(`Could not get a starter: ${err.message}`);
  } finally {
    el.starter.disabled = false;
  }
}

// ---------- running a program

function setRunning(busy) {
  el.run.disabled = busy;
  el.run.textContent = busy ? "Running..." : "Run against hidden tests";
  el.result.setAttribute("aria-busy", String(busy));
}

function showRunning() {
  el.result.replaceChildren();
  const verdict = el_("p", "verdict busy");
  verdict.append(el_("span", "pill", "Running"), el_("span", "", "Parsing and running your program in the interpreter."));
  el.result.append(verdict);
}

function showColdStart() {
  const note = el_("p", "coldstart", "Still running. If the grader was idle, its first start can take up to 10 seconds.");
  el.result.append(note);
}

function clearResult() {
  el.result.replaceChildren();
  el.errorLine.hidden = true;
  el.errorLine.replaceChildren();
  clearLineMark();
}

function testDetail(t) {
  if (t.passed) return null;
  if (t.error) return t.error;
  if (t.visible) return `returned ${t.got || "nothing"}, expected ${t.expected}`;
  return "returned a wrong answer";
}

function renderTests(tests) {
  const list = el_("ol", "tests");
  list.setAttribute("aria-label", "Per-test results");
  for (const t of tests) {
    const li = el_("li");
    li.append(el_("span", `st ${t.passed ? "pass" : "fail"}`, t.passed ? "Pass" : "Fail"));
    const body = el_("span", "");
    body.append(el_("span", "test-name", t.label));
    const detail = testDetail(t);
    if (detail) body.append(el_("span", "detail", detail));
    li.append(body);
    list.append(li);
  }
  return list;
}

function renderResult(data) {
  el.result.replaceChildren();
  const passed = Boolean(data.passed);
  const verdict = el_("p", `verdict ${passed ? "pass" : "fail"}`);
  verdict.append(
    el_("span", "pill", passed ? "Pass" : "Fail"),
    el_("span", "", `${data.tests_passed} of ${data.tests_total} tests passed`),
  );
  el.result.append(verdict);
  if (data.tests && data.tests.length) el.result.append(renderTests(data.tests));
  if (!passed && data.feedback) {
    el.result.append(el_("p", "label", "Grader feedback, the message a model would get"), el_("pre", "", data.feedback));
  }
  if (data.output) {
    el.result.append(el_("p", "label", "Your program printed"), el_("pre", "", data.output));
  }
  markErrors(data);
}

function markErrors(data) {
  if (!data.error_line) return;
  const firstError = (data.tests || []).find((t) => t.error);
  const message = data.error || (firstError && firstError.error) || data.feedback || "Error";
  markLine(data.error_line);
  el.errorLine.hidden = false;
  el.errorLine.replaceChildren(el_("span", "", `Line ${data.error_line}: ${message}`));
  const go = el_("button", "btn btn-quiet btn-sm", "Go to line");
  go.type = "button";
  go.addEventListener("click", () => goToLine(data.error_line));
  el.errorLine.append(go);
}

async function runProgram() {
  const t = tasksById[el.task.value];
  const seed = currentSeed();
  if (!t || !t.runnable || seed === null) return;
  if (!el.program.value.trim()) {
    el.result.replaceChildren(el_("p", "note", "Write a program first, or press Show me a starter."));
    return;
  }
  clearResult();
  setRunning(true);
  showRunning();
  const slow = setTimeout(showColdStart, COLD_START_MS);
  try {
    const data = await postJSON("/api/run", { seed, task_id: t.id, program: el.program.value });
    renderResult(data);
  } catch (err) {
    el.result.replaceChildren(el_("p", "notice", `Not graded: ${err.message}. Your program is kept, so you can try again.`));
  } finally {
    clearTimeout(slow);
    setRunning(false);
  }
}

// ---------- wiring

el.reroll.addEventListener("click", rerollHero);
el.roll.addEventListener("click", () => {
  el.seed.value = String(Math.floor(Math.random() * (MAX_SEED + 1)));
  loadLanguage();
});
el.load.addEventListener("click", loadLanguage);
el.seed.addEventListener("keydown", (e) => { if (e.key === "Enter") loadLanguage(); });
el.task.addEventListener("change", showTask);
el.run.addEventListener("click", runProgram);
el.starter.addEventListener("click", insertStarter);
el.program.addEventListener("input", () => { updateGutter(); });
el.program.addEventListener("scroll", syncScroll);
el.program.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    runProgram();
  }
});
window.addEventListener("resize", syncScroll);

if (NARROW.matches) el.manualWrap.open = false;

const requested = seedFromURL();
if (requested !== null) el.seed.value = String(requested);
loadShowcase();
if (requested !== null) loadLanguage();
