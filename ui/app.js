/* Pinky - Form Reader: the page's behaviour.

   Everything it does goes through window.pywebview.api (pdf_form_reader_app.py,
   class Api): this page never touches a file itself and makes no network
   request. */
"use strict";

const $ = (id) => document.getElementById(id);
let api = null;
let names = [];
let types = [];
let polling = null;
let saveTimer = null;

function el(tag, attrs, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") node.className = v; else node.setAttribute(k, v);
  }
  for (const kid of kids) node.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return node;
}

const ICON_OK = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
const ICON_WARN = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>';

function banner(kind, icon, text) {
  const b = el("div", { class: "banner " + kind });
  b.innerHTML = icon;
  b.append(el("span", {}, text));
  return b;
}

/* ------------------------------------------------------------ settings */
function radio(name) {
  const on = document.querySelector(`input[name="${name}"]:checked`);
  return on ? on.value : "";
}
function setRadio(name, value) {
  const it = document.querySelector(`input[name="${name}"][value="${value}"]`);
  if (it) it.checked = true;
}
function current() {
  return {
    folder: $("folder").value.trim(),
    start: radio("start"),
    look_in: radio("look_in"),
    zips: $("zips").checked,
    names: names.slice(),
    types: types.slice(),
    form: radio("form"),
    match: radio("match"),
    out: $("out").value.trim(),
  };
}
function fill(s) {
  $("folder").value = s.folder || "";
  setRadio("start", s.start || "year");
  setRadio("look_in", s.look_in || "main");
  $("zips").checked = !!s.zips;
  names = (s.names || []).slice();
  types = (s.types || []).slice();
  setRadio("form", s.form || "any");
  drawFormNote();
  setRadio("match", s.match || "partial");
  $("out").value = s.out || "";
  drawNames();
  drawTypes();
  drawExample();
}
function remember() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => api && api.save(current()), 400);
}

/* ------------------------------------------------------------ file names */
function drawNames() {
  const box = $("names");
  box.replaceChildren();
  if (!names.length) {
    box.append(el("span", { class: "empty" }, "No names: every file will be looked at."));
    return;
  }
  names.forEach((n, i) => {
    const x = el("button", { type: "button", title: "Remove " + n, "aria-label": "Remove " + n }, "×");
    x.addEventListener("click", () => { names.splice(i, 1); drawNames(); drawExample(); remember(); });
    box.append(el("span", { class: "chip" }, n, x));
  });
}
function addName() {
  const typed = $("new-name").value.split(/\s+/).join(" ").trim();
  if (!typed) return;
  if (!names.some((n) => n.toLowerCase() === typed.toLowerCase())) names.push(typed);
  $("new-name").value = "";
  drawNames(); drawExample(); remember();
}
/* ------------------------------------------------------------ file types */
function drawTypes() {
  const box = $("types");
  box.replaceChildren(el("span", { class: "chip locked", title: "PDF forms are always read" },
    "PDF", el("span", { class: "lock-note" }, "always read")));
  types.forEach((t, i) => {
    const label = t.toUpperCase();
    const x = el("button", { type: "button", title: "Remove " + label, "aria-label": "Remove " + label }, "\u00d7");
    x.addEventListener("click", () => { types.splice(i, 1); drawTypes(); remember(); });
    box.append(el("span", { class: "chip" }, label, x));
  });
}
function typeNote(text, isError) {
  const err = $("type-error");
  err.textContent = isError ? text : "";
  err.hidden = !isError;
}
async function addType() {
  const typed = $("new-type").value.trim();
  if (!typed) return true;
  const answer = await api.check_type(typed);
  if (!answer.ok) { typeNote(answer.error, true); return false; }
  if (!types.includes(answer.type)) types.push(answer.type);
  $("new-type").value = "";
  typeNote("", false);
  drawTypes(); remember();
  return true;
}

const FORM_NOTES = {
  any: "Lists every field of every PDF read, in fields.csv (and the Excel workbook).",
  pink: "Reads the Pink Sheet's chosen values into pink-sheets.csv (and the Excel workbook), one row per job: Job Number, Witness A to F each with R&S and R&S Sent To, Original +, Notes, Initial QC, the YES/NO flags, Production (Printed by), Originals, Copies, USB, and Final QC By. Checklist ticks and Billing are left out. Tip: add \u201cpink sheet\u201d as a file name.",
};
function drawFormNote() { $("form-note").textContent = FORM_NOTES[radio("form")] || ""; }

function drawExample() {
  const word = names[0] || "worksheet";
  const cap = word.replace(/\.pdf$/i, "");
  const title = cap.charAt(0).toUpperCase() + cap.slice(1);
  const box = $("example");
  box.replaceChildren();
  if (radio("match") === "complete") {
    box.append("With ", el("b", {}, "Complete"), `, “${word}” finds `,
      el("b", {}, `${title}.pdf`), ` but not “Smith ${title} FINAL.pdf”.`);
  } else {
    box.append("With ", el("b", {}, "Partial"), `, “${word}” finds `,
      el("b", {}, `${title}.pdf`), " and ", el("b", {}, `Smith ${title} FINAL.pdf`), ".");
  }
  box.append(el("br"), "Capital letters, extra spaces and the file’s ending (.pdf, .docx) never matter.");
}

/* ------------------------------------------------------------ results */
function drawIdle() {
  const body = $("results-body");
  body.replaceChildren(el("div", { class: "empty-state" },
    el("div", { class: "big" }, "Nothing read yet"),
    "Choose a folder and the file names to look for, then press ", el("b", {}, "Read PDFs"), "."));
}
function drawRunning(st) {
  const body = $("results-body");
  const bar = el("div", { class: "progress" }, el("div"));
  body.replaceChildren(
    el("div", { class: "row" }, el("b", {}, `${st.files_read} file${st.files_read === 1 ? "" : "s"} read`)),
    bar,
    el("div", { class: "now" }, st.now ? "Now: " + st.now : "Looking for PDFs…"),
  );
}
function drawDone(st) {
  const body = $("results-body");
  const c = st.counts;
  const parts = [];
  if (st.state === "stopped") parts.push(banner("stopped", ICON_WARN, "Stopped. These results cover only what was read before Stop."));
  const pink = st.form === "pink";
  const tile = (n, t, warn) => el("div", { class: "tile" + (warn ? " warn" : "") }, el("div", { class: "n" }, n), el("div", { class: "t" }, t));
  if (st.state !== "stopped") parts.push(banner("ok", ICON_OK, pink
    ? `Finished. ${c.sheets} Pink Sheet${c.sheets === 1 ? "" : "s"} read.`
    : `Finished. ${c.fields} form field${c.fields === 1 ? "" : "s"} listed.`));
  parts.push(pink
    ? el("div", { class: "tiles" }, tile(c.pdfs, "PDFs read"), tile(c.sheets, "Pink Sheets"),
        tile(c.witnesses, "witnesses listed"), tile(c.problems, "needing a look (files.csv)", c.problems))
    : el("div", { class: "tiles" }, tile(c.pdfs, "PDFs read"), tile(c.with_fields, "with form fields"),
        tile(c.fields, "form fields listed"), tile(c.problems, "needing a look (files.csv)", c.problems)));
  if (pink && c.set_aside) parts.push(el("ul", { class: "lines" }, el("li", {},
    "Blank Pink Sheets not used: a filled-in one in the same job folder was used (see files.csv)", el("b", {}, c.set_aside))));
  if (st.types && st.types.length) parts.push(el("ul", { class: "lines" }, el("li", {},
    `Other files found (${st.types.join(", ")}): listed, not read`, el("b", {}, c.other_found))));
  if (st.main_only) parts.push(el("div", { class: "muted" }, "Subfolders inside job folders were not opened (main job folder only)."));
  parts.push(el("div", { class: "label" }, "Saved in"), el("div", { class: "where" }, st.results));
  parts.push(el("div", { class: "files-list" },
    el("b", {}, pink ? "pink-sheets.csv" : "fields.csv"), pink ? " one row per job" : " one row per form field", el("br"),
    el("b", {}, "files.csv"), " one row per file found, and any problems", el("br"),
    el("b", {}, "pinky-results.xlsx"), " the same tables in one Excel workbook", el("br"),
    el("b", {}, "settings-used.txt"), " the choices that made these results"));
  parts.push(el("div", { class: "privacy" }, "These files hold real client data. Keep them on this computer and delete them when done."));
  body.replaceChildren(el("div", { style: "display:flex;flex-direction:column;gap:10px" }, ...parts));
}
function drawError(text) {
  $("results-body").replaceChildren(banner("error", ICON_WARN, text));
}

function setRunning(on) {
  $("run").disabled = on;
  $("stop").disabled = !on;
  for (const id of ["folder", "out", "new-name", "add-name", "new-type", "add-type", "browse-folder", "browse-out", "zips"]) $(id).disabled = on;
  document.querySelectorAll(".chip button").forEach((b) => { b.disabled = on; });
  document.querySelectorAll('input[type="radio"]').forEach((r) => { r.disabled = on; });
}

async function poll() {
  const st = await api.status();
  if (st.state === "running") {
    drawRunning(st);
    $("status").textContent = `Reading… ${st.files_read} file${st.files_read === 1 ? "" : "s"} read`;
    return;
  }
  clearInterval(polling); polling = null;
  setRunning(false);
  if (st.state === "error") {
    drawError(st.error); $("status").textContent = "Something went wrong.";
  } else {
    drawDone(st);
    $("status").textContent = st.state === "stopped" ? "Stopped." : "Finished.";
    $("open-results").disabled = !st.can_open;
  }
}

async function run() {
  if ($("new-name").value.trim()) addName();
  if (!(await addType())) return;
  const answer = await api.start(current());
  if (!answer.ok) { drawError(answer.error); $("status").textContent = "Not started."; return; }
  $("open-results").disabled = true;
  setRunning(true);
  drawRunning({ files_read: 0, now: "" });
  $("status").textContent = "Reading…";
  polling = setInterval(poll, 250);
}

/* ------------------------------------------------------------ steps */
function markStep(cardId) {
  document.querySelectorAll(".step").forEach((s) => s.classList.toggle("active", s.dataset.card === cardId));
  document.querySelectorAll("#form-panel .card").forEach((c) => c.classList.toggle("current", c.id === cardId));
}

async function start() {
  api = window.pywebview.api;
  fill(await api.load());
  drawIdle();

  $("browse-folder").addEventListener("click", async () => {
    const picked = await api.pick_folder($("folder").value, "Choose the folder to read");
    if (picked) { $("folder").value = picked; remember(); }
  });
  $("browse-out").addEventListener("click", async () => {
    const picked = await api.pick_folder($("out").value, "Choose where to save results");
    if (picked) { $("out").value = picked; remember(); }
  });
  $("add-name").addEventListener("click", addName);
  $("add-type").addEventListener("click", addType);
  $("new-type").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); addType(); } });
  $("new-type").addEventListener("input", () => typeNote("", false));
  $("new-name").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); addName(); } });
  document.querySelectorAll('input[name="match"]').forEach((r) => r.addEventListener("change", drawExample));
  document.querySelectorAll('input[name="form"]').forEach((r) => r.addEventListener("change", drawFormNote));

  // The "i" buttons: hover shows the explanation; a click pins it open until
  // the next click anywhere else, or Escape.
  document.querySelectorAll(".info").forEach((btn) => btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const wrap = btn.parentElement;
    const open = !wrap.classList.contains("open");
    document.querySelectorAll(".info-wrap.open").forEach((w) => { w.classList.remove("open"); w.firstChild.setAttribute("aria-expanded", "false"); });
    wrap.classList.toggle("open", open);
    btn.setAttribute("aria-expanded", String(open));
  }));
  const closeTips = () => document.querySelectorAll(".info-wrap.open").forEach((w) => {
    w.classList.remove("open"); w.firstChild.setAttribute("aria-expanded", "false"); });
  document.addEventListener("click", (e) => { if (!e.target.closest(".tip")) closeTips(); });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    closeTips();
    const focused = document.activeElement;
    if (focused && focused.classList.contains("info")) focused.blur();
  });
  document.querySelectorAll("#form-panel input").forEach((i) => i.addEventListener("change", remember));
  $("run").addEventListener("click", run);
  $("stop").addEventListener("click", () => { api.stop(); $("status").textContent = "Stopping after the current file…"; });
  $("open-results").addEventListener("click", () => api.open_results());
  document.querySelectorAll(".step").forEach((s) => s.addEventListener("click", () => {
    $(s.dataset.card).scrollIntoView({ behavior: "smooth", block: "nearest" });
    markStep(s.dataset.card);
  }));
  document.querySelectorAll("#form-panel .card").forEach((c) =>
    c.addEventListener("focusin", () => markStep(c.id)));
  markStep("card-folder");
  $("folder").focus();
}

if (window.pywebview && window.pywebview.api) start();
else window.addEventListener("pywebviewready", start);
