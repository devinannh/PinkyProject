/* PDF Form Reader - the page's behaviour.

   Everything it does goes through window.pywebview.api (pdf_form_reader_app.py,
   class Api): this page never touches a file itself and makes no network
   request. */
"use strict";

const $ = (id) => document.getElementById(id);
let api = null;
let names = [];
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
  setRadio("match", s.match || "partial");
  $("out").value = s.out || "";
  drawNames();
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
    box.append(el("span", { class: "empty" }, "No names: every PDF will be read."));
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
  box.append(el("br"), "Capital letters, extra spaces and “.pdf” never matter.");
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
  else parts.push(banner("ok", ICON_OK, `Finished. ${c.fields} form field${c.fields === 1 ? "" : "s"} listed.`));
  parts.push(el("div", { class: "tiles" },
    el("div", { class: "tile" }, el("div", { class: "n" }, c.pdfs), el("div", { class: "t" }, "PDFs read")),
    el("div", { class: "tile" }, el("div", { class: "n" }, c.with_fields), el("div", { class: "t" }, "with form fields")),
    el("div", { class: "tile" }, el("div", { class: "n" }, c.fields), el("div", { class: "t" }, "form fields listed")),
    el("div", { class: "tile" + (c.problems ? " warn" : "") }, el("div", { class: "n" }, c.problems),
      el("div", { class: "t" }, "needing a look (files.csv)")),
  ));
  const lines = el("ul", { class: "lines" },
    el("li", {}, "Passed over: name did not match", el("b", {}, c.name_skipped)),
    el("li", {}, "Passed over: outside any job folder", el("b", {}, c.place_skipped)));
  if (c.zips_not_opened) lines.append(el("li", {}, "Zip files not opened", el("b", {}, c.zips_not_opened)));
  parts.push(lines);
  if (st.main_only) parts.push(el("div", { class: "muted" }, "Subfolders inside job folders were not opened (main job folder only)."));
  parts.push(el("div", { class: "label" }, "Saved in"), el("div", { class: "where" }, st.results));
  parts.push(el("div", { class: "files-list" },
    el("b", {}, "fields.csv"), " one row per form field", el("br"),
    el("b", {}, "files.csv"), " one row per PDF, and any problems", el("br"),
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
  for (const id of ["folder", "out", "new-name", "add-name", "browse-folder", "browse-out", "zips"]) $(id).disabled = on;
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
  $("new-name").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); addName(); } });
  document.querySelectorAll('input[name="match"]').forEach((r) => r.addEventListener("change", drawExample));
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
