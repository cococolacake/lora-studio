// Extra cards on a run's page: sample grid, LoRA metadata editor, SwarmUI send + test grid.
import { api } from "./api.js";
import { h, btn, card, chip, kv, modal, toast, toastError, clear, store } from "./dom.js";
import { icon } from "./icons.js";
import { thumbUrl, fileUrl, lightbox } from "./media.js";
import { taskProgress, watchTask } from "./tools/common.js";

// ---- sd-scripts sample previews: prompts × epochs -------------------------------
/** The saved LoRA file that belongs to a sample column like "Epoch 3". */
export function fileForColumn(r, col) {
  const m = /^Epoch (\d+)$/.exec(col);
  if (!m) return null;
  const ep = Number(m[1]);
  const name = r.config?.output_name || "";
  const lastEpoch = r.progress?.epochs;
  const want = ep === lastEpoch ? `${name}.safetensors` : `${name}-${String(ep).padStart(6, "0")}.safetensors`;
  return (r.outputs || []).find((o) => o.name === want) || null;
}

export function starButton(r, file, onChange) {
  const on = r.best?.source === file.name;
  return h("button.star-btn", { class: on ? "on" : "", title: on ? "This is your best epoch" : "Mark as the best epoch (saved as …-best.safetensors)",
    onclick: async (e) => {
      e.stopPropagation();
      try {
        r.best = await api.run_set_best(r.id, file.path);
        toast("Best epoch saved", `${file.name} → ${r.best.path.split("/").pop()}`, "good", "star");
        onChange?.();
      } catch (err) { toastError(err); }
    } }, icon("star"));
}

export function samplesCard(r, onChange) {
  const g = r.sample_grid;
  const rows = Math.max(g.prompts.length, ...g.cells.map((c) => c.row + 1));
  const cols = g.columns;
  const at = {};
  for (const c of g.cells) at[`${c.row}|${c.col}`] = c;   // later files win (newest)
  const order = [];
  for (let ri = 0; ri < rows; ri++) for (const col of cols) if (at[`${ri}|${col}`]) order.push({ ...at[`${ri}|${col}`], title: `${col} · prompt ${ri + 1}`, sub: g.prompts[ri] || "" });
  const grid = h("div.sgrid", { style: { gridTemplateColumns: `minmax(160px, 220px) repeat(${cols.length}, minmax(96px, 180px))` } },
    h("div"), cols.map((c) => { const f = fileForColumn(r, c); return h("div.sh", c, f ? starButton(r, f, onChange) : null); }),
    Array.from({ length: rows }, (_, ri) => [
      h("div.sp", { title: g.prompts[ri] || "" }, h("span.sp-text", g.prompts[ri] || `Prompt ${ri + 1}`),
        cols.filter((col) => at[`${ri}|${col}`]).length > 1
          ? h("button.chip-btn", { title: "Animate this prompt's samples, epoch by epoch", onclick: () => makeGif(r, ri) }, icon("play"), "GIF") : null),
      cols.map((col) => {
        const c = at[`${ri}|${col}`];
        const isBest = r.best && fileForColumn(r, col)?.name === r.best.source;
        return c ? h("button.sc", { class: isBest ? "best" : "", onclick: () => lightbox(order, order.findIndex((o) => o.path === c.path)) }, h("img", { src: thumbUrl(c.path, 320), loading: "lazy" })) : h("div");
      }),
    ]));
  return card({ title: "Samples", actions: h("div.row", { style: { gap: "10px" } },
      h("span.small.faint", `${g.cells.length} images · ☆ marks your best epoch`),
      order.length > 1 ? btn("Compare", { icon: "columns", size: "sm", onclick: () => compareModal(order) }) : null) },
    h("div", { style: { overflowX: "auto" } }, grid));
}

// ---- compare two samples: a slider that wipes between them, or a fade ------------------
export function compareModal(items) {
  // default: the same prompt, first vs last epoch
  const first = items[0];
  const samePrompt = items.filter((x) => x.row === first.row);
  let A = 0, B = items.indexOf(samePrompt[samePrompt.length - 1] || items[items.length - 1]);
  let mode = "slider", pos = 50;
  const imgA = h("img.cmp-a", { alt: "" }), imgB = h("img.cmp-b", { alt: "" });
  const handle = h("div.cmp-handle", h("span", icon("columns")));
  const tagA = h("span.cmp-tag.left"), tagB = h("span.cmp-tag.right");
  const stage = h("div.cmp-stage", imgB, imgA, handle, tagA, tagB);
  const range = h("input.cmp-range", { type: "range", min: 0, max: 100, value: pos, "aria-label": "Compare position",
    oninput: (e) => { pos = Number(e.target.value); paint(); } });
  const pick = (cur, set) => h("select.select", { onchange: (e) => { set(Number(e.target.value)); load(); } },
    items.map((it, i) => h("option", { value: i, selected: i === cur }, it.title)));
  const modeSeg = h("div");
  function paint() {
    if (mode === "slider") {
      imgA.style.clipPath = `inset(0 ${100 - pos}% 0 0)`; imgA.style.opacity = "1";
      handle.style.display = ""; handle.style.left = `${pos}%`;
    } else {
      imgA.style.clipPath = "none"; imgA.style.opacity = String(1 - pos / 100);
      handle.style.display = "none";
    }
  }
  function load() {
    imgA.src = fileUrl(items[A].path); imgB.src = fileUrl(items[B].path);
    tagA.textContent = items[A].title.split(" · ")[0]; tagB.textContent = items[B].title.split(" · ")[0];
    paint();
  }
  function drawMode() {
    clear(modeSeg, h("div.seg", ["slider", "fade"].map((m) => h("button", { type: "button", class: m === mode ? "on" : "",
      onclick: () => { mode = m; drawMode(); paint(); } }, icon(m === "slider" ? "columns" : "layers"), m === "slider" ? "Slider" : "Fade"))));
  }
  // drag directly on the picture too
  const dragTo = (e) => { const r = stage.getBoundingClientRect(); pos = Math.max(0, Math.min(100, ((e.clientX - r.left) / r.width) * 100)); range.value = pos; paint(); };
  stage.addEventListener("pointerdown", (e) => { stage.setPointerCapture(e.pointerId); dragTo(e); });
  stage.addEventListener("pointermove", (e) => { if (e.buttons) dragTo(e); });
  drawMode(); load();
  return modal("Compare samples", h("div.stack.sm",
    h("div.grid.c2", h("div.field", h("label", "Left / first"), pick(A, (v) => { A = v; })), h("div.field", h("label", "Right / second"), pick(B, (v) => { B = v; }))),
    stage,
    h("div.row", { style: { gap: "14px" } }, modeSeg, range)),
    [{ label: "Close", kind: "ghost" }], { wide: true });
}

async function makeGif(r, row) {
  try {
    toast("Making the animation…", "", "", "play", 2500);
    const path = await api.samples_gif(r.id, row);
    const v = await modal(`Prompt ${row + 1}, epoch by epoch`, h("div.stack.sm",
      h("img", { src: fileUrl(path, Date.now()), alt: "Animated samples", style: { maxWidth: "100%", maxHeight: "60vh", borderRadius: "14px", display: "block", margin: "0 auto" } }),
      h("p.small.muted", { style: { margin: 0 } }, `Saved as ${path.split("/").pop()} in the samples folder.`)),
      [{ label: "Open folder", value: "open" }, { label: "Close", kind: "primary" }]);
    if (v === "open") api.open_folder(path.replace(/\/[^/]*$/, ""));
  } catch (e) { toastError(e); }
}

// ---- LoRA metadata ----------------------------------------------------------------
export async function metaModal(path, run) {
  let m;
  try { m = await api.lora_meta(path); } catch (e) { toastError(e); return; }
  const ed = { ...m.editable };
  let thumbImage = null;
  const thumbEl = h("img.meta-thumb", { src: ed["modelspec.thumbnail"] || "", style: ed["modelspec.thumbnail"] ? null : { visibility: "hidden" } });
  const field = (key, label, ph, area = false) => h("div.field", h("label", label),
    h(area ? "textarea.input" : "input.input", { value: ed[key] || "", placeholder: ph, rows: area ? 3 : null, oninput: (e) => { ed[key] = e.target.value; } }));
  const cells = run?.sample_grid?.cells || [];
  const picks = h("div.thumb-pick", cells.slice(-16).reverse().map((c) => h("button", { title: c.name, onclick: (e) => {
    thumbImage = c.path; ed["modelspec.thumbnail"] = undefined;
    thumbEl.src = thumbUrl(c.path, 256); thumbEl.style.visibility = "visible";
    picks.querySelectorAll("button").forEach((b) => b.classList.remove("on")); e.currentTarget.classList.add("on");
  } }, h("img", { src: thumbUrl(c.path, 128), loading: "lazy" }))));
  const upload = h("input", { type: "file", accept: "image/*", style: { display: "none" }, onchange: async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    ed["modelspec.thumbnail"] = await smallJpeg(f);
    thumbImage = null;
    thumbEl.src = ed["modelspec.thumbnail"]; thumbEl.style.visibility = "visible";
  } });

  const body = h("div.stack",
    h("div.row", { style: { alignItems: "flex-start", gap: "18px" } },
      h("div.stack.sm", thumbEl, upload, btn("Upload", { icon: "upload", size: "sm", kind: "ghost", onclick: () => upload.click() }),
        ed["modelspec.thumbnail"] ? btn("Remove", { size: "sm", kind: "ghost", onclick: () => { ed["modelspec.thumbnail"] = ""; thumbImage = null; thumbEl.style.visibility = "hidden"; } }) : null),
      h("div.stack.sm", { style: { flex: 1 } },
        h("div.grid.c2", field("modelspec.title", "Title", m.name.replace(".safetensors", "")), field("modelspec.trigger_phrase", "Trigger phrase", "mychar")),
        h("div.grid.c2", field("modelspec.author", "Author", "you"), field("modelspec.tags", "Tags", "character, anime")),
        field("modelspec.description", "Description", "Recommended strength, notes…", true),
        field("modelspec.usage_hint", "Usage hint", "e.g. use at 0.8 strength"))),
    cells.length ? h("div.field", h("label", "Use a sample as the thumbnail"), picks) : null,
    h("div.grid.c2",
      h("div", h("div.card-title", { style: { marginBottom: "8px" } }, "Training info"), kv(Object.entries(m.summary))),
      h("div", h("div.card-title", { style: { marginBottom: "8px" } }, "Most common training tags"),
        h("div.row", { style: { gap: "6px" } }, m.top_tags.slice(0, 24).map(([t, n]) => h("span.tag", t, h("b", String(n))))))),
    h("p.tiny.faint", { style: { margin: 0 } }, `${m.name} · ${m.tensors} tensors. Only the header is rewritten; the weights aren't touched.`));

  const res = await modal("LoRA info", body, [{ label: "Cancel", kind: "ghost", value: false }, { label: "Save into file", kind: "primary", icon: "save", value: true }]);
  if (!res) return;
  const updates = {};
  for (const [k, v] of Object.entries(ed)) if (v !== undefined && v !== m.editable[k]) updates[k] = v === "" ? null : v;
  try {
    await api.lora_meta_save(path, updates, thumbImage);
    toast("Saved", `Metadata written to ${m.name}`, "good", "save");
  } catch (e) { toastError(e); }
}

async function smallJpeg(file, size = 256) {
  const url = await new Promise((res) => { const r = new FileReader(); r.onload = () => res(r.result); r.readAsDataURL(file); });
  const img = await new Promise((res) => { const i = new Image(); i.onload = () => res(i); i.src = url; });
  const s = Math.min(1, size / Math.max(img.width, img.height));
  const c = document.createElement("canvas");
  c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
  c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
  return c.toDataURL("image/jpeg", 0.88);
}

// ---- SwarmUI ------------------------------------------------------------------------
export function swarmCard(ctx, r) {
  const slot = h("div", h("div.loading", h("span.spin"), "Checking SwarmUI…"));
  const comfySlot = h("div");
  const el = card({ title: "SwarmUI & ComfyUI" }, slot, comfySlot);
  draw();
  drawComfy();
  return el;

  async function drawComfy() {
    // Only needed for a separate ComfyUI; the one inside SwarmUI shares SwarmUI's LoRA folder.
    const s = ctx.boot.settings;
    const own = s.comfy_mode === "standalone" || (!s.comfy_mode && s.comfy_dir);
    if (!own) return;
    const st = await api.comfy_status().catch(() => null);
    if (!st?.valid) return;
    const run = await api.run_detail(r.id);
    const sent = run.comfy?.sent || [];
    const send = (which) => async () => {
      try { const res = await api.comfy_send(r.id, which); toast("Copied to ComfyUI", `${res.copied.length} file(s). Refresh ComfyUI's LoRA list to see them.`, "good", "check"); drawComfy(); }
      catch (e) { toastError(e); }
    };
    clear(comfySlot, h("div.row", { style: { marginTop: "16px", paddingTop: "14px", borderTop: "1px solid var(--line)" } },
      h("b.small", "ComfyUI"),
      sent.length ? h("span.small", `${sent.length} file(s) copied`) : h("span.small.muted", "Not copied yet."),
      h("div.spacer"),
      run.best ? btn("Copy best epoch", { icon: "star", size: "sm", kind: "primary", onclick: send("best") }) : null,
      btn("Copy final LoRA", { icon: "download", size: "sm", onclick: send("final") }),
      btn("Copy every epoch", { icon: "layers", size: "sm", onclick: send("all") })));
  }

  async function draw() {
    let st;
    try { st = await api.swarm_status(); } catch (e) { st = { configured: false, error: e.message }; }
    if (!st.configured || !st.valid) {
      clear(slot, h("div.notice", icon("info"), h("div", { style: { flex: 1 } }, "Connect your SwarmUI install to copy LoRAs into it and render test grids. ",
        btn("Set it up", { size: "sm", kind: "ghost", onclick: () => ctx.go("swarm") }))));
      return;
    }
    const run = await api.run_detail(r.id);
    const sent = run.swarm?.sent || [];
    const statusRow = h("div.row",
      st.running ? chip(`Running${st.version ? " · " + st.version : ""}`, "good", "dot") : chip("Not running", "", "dot"),
      h("span.small.faint.mono.ellipsis", { style: { flex: 1 } }, st.lora_dir),
      st.running ? btn("Open SwarmUI", { icon: "external", size: "sm", kind: "ghost", onclick: () => api.swarm_open() })
        : btn("Start SwarmUI", { icon: "play", size: "sm", onclick: async (e) => {
          e.currentTarget.disabled = true;
          try { await api.swarm_launch(); toast("Starting SwarmUI", "This can take a minute.", "", "play"); waitForSwarm(); } catch (err) { toastError(err); }
        } }));
    const send = (which) => async () => {
      try {
        const res = await api.swarm_send(r.id, which);
        toast("Copied to SwarmUI", `${res.copied.length} file(s)${res.refreshed ? ", model list refreshed" : ""}`, "good", "check");
        draw();
      } catch (e) { toastError(e); }
    };
    const sendRow = h("div.row", { style: { marginTop: "12px" } },
      sent.length ? h("span.small", icon("circleCheck"), ` ${sent.length} file(s) in SwarmUI → `, h("span.mono.small", sent[0].split("/").slice(-2, -1)[0])) : h("span.small.muted", "Not copied to SwarmUI yet."),
      h("div.spacer"),
      run.best ? btn("Copy best epoch", { icon: "star", size: "sm", kind: "primary", onclick: send("best") }) : null,
      btn("Copy final LoRA", { icon: "download", size: "sm", onclick: send("final") }),
      btn("Copy every epoch", { icon: "layers", size: "sm", onclick: send("all") }));
    clear(slot, statusRow, sendRow,
      sent.length ? gridForm(st, run, sent) : null,
      run.swarm_grid?.cells?.length ? gridView(run.swarm_grid) : null);
  }

  function waitForSwarm(tries = 0) {
    setTimeout(async () => {
      const st = await api.swarm_status().catch(() => null);
      if (st?.running) { toast("SwarmUI is up", "", "good", "circleCheck"); draw(); }
      else if (tries < 40) waitForSwarm(tries + 1);
    }, 3000);
  }

  function gridForm(st, run, sent) {
    const saved = store.get("swarmGrid", {});
    const o = {
      model: saved.model || "", strengths: saved.strengths || "0.6, 0.8, 1.0",
      prompts: (run.sample_prompts || []).slice(0, 2).join("\n") || `${run.lora_info?.trigger || run.trigger || ""}, 1girl, smile`.replace(/^, /, ""),
      negative: saved.negative ?? (run.samples?.negative || ""), width: saved.width || 1024, height: saved.height || 1024,
      steps: saved.steps || 28, cfg: saved.cfg || 5, seed: saved.seed || 42,
    };
    const files = new Set(sent.slice(-3));
    const modelSel = h("select.select", h("option", { value: o.model }, o.model || (st.running ? "Loading models…" : "Start SwarmUI to list models")));
    if (st.running) api.swarm_models().then((ms) => {
      if (!o.model) o.model = ms.find((m) => /anima/i.test(m) && run.family === "Anima") || ms[0] || "";
      clear(modelSel, ms.map((m) => h("option", { value: m, selected: m === o.model }, m)));
    }).catch(() => {});
    modelSel.onchange = (e) => { o.model = e.target.value; };
    const prog = taskProgress();
    const inp = (k, w) => h("input.input" + (typeof o[k] === "number" ? ".nums" : ""), { value: o[k], style: w ? { width: w } : null, onchange: (e) => { o[k] = typeof o[k] === "number" ? Number(e.target.value) : e.target.value; } });
    const go = btn("Render grid", { icon: "sparkle", kind: "primary", disabled: !st.running, onclick: async () => {
      store.set("swarmGrid", { model: o.model, strengths: o.strengths, negative: o.negative, width: o.width, height: o.height, steps: o.steps, cfg: o.cfg, seed: o.seed });
      go.disabled = true;
      try {
        const id = await api.swarm_grid(r.id, { ...o, prompts: o.prompts.split("\n").filter((p) => p.trim()),
          strengths: o.strengths.split(/[,\s]+/).filter(Boolean).map(Number), files: sent.filter((f) => files.has(f)) });
        const t = await watchTask(id, (s) => prog.set(s));
        if (t?.status === "done") { toast("Grid ready", "", "good", "sparkle"); draw(); }
        else if (t) toast("Grid didn't finish", t.lines.at(-1) || "", "bad", "alert", 9000);
      } catch (e) { toastError(e); }
      go.disabled = false;
    } });
    return h("div.stack.sm", { style: { marginTop: "18px", paddingTop: "16px", borderTop: "1px solid var(--line)" } },
      h("div.row", h("b", "Test grid"), h("span.small.muted", "Each LoRA file × each strength, rendered by SwarmUI.")),
      h("div.grid.c2",
        h("div.field", h("label", "Base model"), modelSel),
        h("div.field", h("label", "Strengths"), inp("strengths"))),
      h("div.field", h("label", "LoRA files"), h("div.row", { style: { gap: "16px" } }, sent.map((f) => h("label.check",
        h("input", { type: "checkbox", checked: files.has(f), onchange: (e) => { e.target.checked ? files.add(f) : files.delete(f); } }), f.split("/").pop().replace(".safetensors", ""))))),
      h("div.grid.c2",
        h("div.field", h("label", "Prompts (one per line)"), h("textarea.input", { rows: 3, value: o.prompts, oninput: (e) => { o.prompts = e.target.value; } })),
        h("div.field", h("label", "Negative"), h("textarea.input", { rows: 3, value: o.negative, oninput: (e) => { o.negative = e.target.value; } }))),
      h("div.row", { style: { alignItems: "flex-end" } },
        ...[["width", "Width"], ["height", "Height"], ["steps", "Steps"], ["cfg", "CFG"], ["seed", "Seed"]].map(([k, l]) => h("div.field", h("label", l), inp(k, "88px"))),
        h("div.spacer"), go),
      prog.el);
  }

  function gridView(g) {
    const items = [];
    const at = {};
    for (const c of g.cells) if (c.path) at[`${c.p}|${c.l}|${c.s}`] = c;
    return h("div.stack", { style: { marginTop: "18px" } }, g.prompts.map((p, pi) => {
      const grid = h("div.sgrid", { style: { gridTemplateColumns: `minmax(140px, 200px) repeat(${g.strengths.length}, minmax(96px, 200px))` } },
        h("div.sp", h("b", "Prompt ", pi + 1), h("br"), p), g.strengths.map((s) => h("div.sh", `Strength ${s}`)),
        g.loras.map((l, li) => [
          h("div.sp.mono", l.split("/").pop()),
          g.strengths.map((s, si) => {
            const c = at[`${pi}|${li}|${si}`];
            if (!c) return h("div.sc.err", { title: "Failed" }, icon("alert"));
            const item = { path: c.path, title: `${l.split("/").pop()} @ ${s}`, sub: p };
            items.push(item);
            return h("button.sc", { onclick: () => lightbox(items, items.indexOf(item)) }, h("img", { src: thumbUrl(c.path, 320), loading: "lazy" }));
          }),
        ]));
      return h("div", { style: { overflowX: "auto" } }, grid);
    }));
  }
}
