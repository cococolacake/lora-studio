// Reusable form pieces: switches, segmented controls, schema-driven fields, dataset editor, log view.
import { api } from "./api.js";
import { h, btn, clear, toastError } from "./dom.js";
import { icon } from "./icons.js";

let NATIVE = false;
export const setNative = (v) => { NATIVE = !!v; };

export function prettyKey(key) {
  const words = key.replace(/_/g, " ").replace(/\bn\b/g, "N").replace(/\blr\b/g, "LR")
    .replace(/\bte\b/g, "TE").replace(/\bunet\b/g, "U-Net").replace(/\bvae\b/g, "VAE").replace(/\bae\b/g, "AE")
    .replace(/\bfp8\b/g, "FP8").replace(/\bclip\b/g, "CLIP").replace(/\bt5xxl\b/g, "T5-XXL").replace(/\breso\b/g, "res")
    .replace(/\bsdpa\b/g, "SDPA").replace(/\bsnr\b/g, "SNR").replace(/\bema\b/g, "EMA");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function switchEl(checked, onchange, label = "") {
  const inp = h("input", { type: "checkbox", checked: !!checked, onchange: (e) => onchange(e.target.checked) });
  return h("label.switch", inp, h("span.track"), label ? h("span.txt", label) : null);
}

export function checkEl(checked, onchange, label) {
  return h("label.check", h("input", { type: "checkbox", checked: !!checked, onchange: (e) => onchange(e.target.checked) }), label);
}

export function seg(options, value, onchange) {
  const wrap = h("div.seg");
  const render = (v) => {
    wrap.replaceChildren(...options.map(([val, label, ic]) =>
      h("button", { class: val === v ? "on" : "", type: "button", onclick: () => { render(val); onchange(val); } }, ic ? icon(ic) : null, label)));
  };
  render(value);
  return wrap;
}

export function rangeEl(value, min, max, step, oninput) {
  const r = h("input", { type: "range", min, max, step, value });
  const paint = () => r.style.setProperty("--fill", `${((r.value - min) / (max - min)) * 100}%`);
  r.addEventListener("input", () => { paint(); oninput(Number(r.value)); });
  paint();
  return r;
}

// Example paths are written Windows-style; show Linux-style ones on Linux.
export function examplePath(p) {
  if (document.documentElement.dataset.platform === "windows" || !p.startsWith("C:/")) return p;
  return p.replace(/^C:\/Users\/you\//, "/home/you/").replace(/^C:\/(AI|datasets)\//, "/home/you/$1/").replace(/^C:\//, "/home/you/");
}

export function pathInput(value, onchange, { folder = false, kind = "any", placeholder = "" } = {}) {
  const inp = h("input.input.mono", { value: value ?? "", placeholder: examplePath(placeholder || (folder ? "C:/path/to/folder" : "C:/path/to/file")),
    onchange: (e) => onchange(e.target.value.trim()) });
  const browse = btn("", { icon: "folder", title: "Browse", onclick: async () => {
    try {
      const p = folder ? await api.pick_folder() : await api.pick_file(kind);
      if (p) { inp.value = p; onchange(p); }
    } catch (e) { toastError(e); }
  } });
  return h("div.input-wrap", inp, NATIVE ? browse : null);
}

const PATH_RE = /(_dir$|_path$|^vae$|^ae$|clip_l|clip_g|t5xxl|qwen3|gemma2|_weights$|^resume$|_file$|^text_encoder$|^pretrained_model_name_or_path$|^dit$|^llm$)/;
const FOLDER_RE = /(_dir$|^resume$)/;

/** One option from a script's argparse schema. */
export function argField(arg, value, onchange, { showHelp = true } = {}) {
  const changed = value !== undefined && value !== null && value !== "" &&
    JSON.stringify(value) !== JSON.stringify(arg.default) && !(arg.kind === "bool" && value === false);
  const label = h("label", prettyKey(arg.key), h("span.key", arg.flag));
  let control;
  if (arg.kind === "bool" || arg.kind === "bool_false") {
    const on = value === undefined ? (arg.kind === "bool_false") : !!value;
    control = switchEl(on, onchange, on ? "On" : "Off");
    control.querySelector("input").addEventListener("change", (e) => { control.querySelector(".txt").textContent = e.target.checked ? "On" : "Off"; });
  } else if (arg.choices && arg.choices.length) {
    const cur = value ?? arg.default;
    control = h("select.select", { onchange: (e) => onchange(e.target.value === "__none__" ? null : e.target.value) },
      arg.choices.map((c) => h("option", { value: c ?? "__none__", selected: String(c) === String(cur) }, c == null ? "(not set)" : String(c))));
  } else if (arg.kind === "list") {
    const txt = Array.isArray(value) ? value.join(" ") : (value ?? "");
    control = h("input.input.mono", { value: txt, placeholder: Array.isArray(arg.default) ? arg.default.join(" ") : "space-separated values",
      onchange: (e) => onchange(listValue(e.target.value)) });
  } else if (arg.kind === "str" && PATH_RE.test(arg.key)) {
    control = pathInput(value, onchange, { folder: FOLDER_RE.test(arg.key), kind: "model",
      placeholder: arg.default != null ? String(arg.default) : "" });
  } else {
    const isNum = arg.kind === "int" || arg.kind === "float";
    control = h("input.input" + (isNum ? ".nums" : ""), {
      value: value ?? "", placeholder: arg.default != null ? String(arg.default) : "",
      inputmode: isNum ? "decimal" : null,
      onchange: (e) => onchange(e.target.value.trim() === "" ? null : e.target.value.trim()),
    });
  }
  return h("div.field" + (changed ? ".changed" : ""), { "data-key": arg.key }, label, control,
    showHelp && arg.help ? h("div.help", { title: arg.help }, arg.help) : null);
}

function listValue(s) {
  s = s.trim();
  if (!s) return null;
  if (s.startsWith("[")) { try { return JSON.parse(s); } catch { /* fall through */ } }
  const out = [];
  let cur = "", q = null;
  for (const ch of s) {
    if (q) { if (ch === q) q = null; else cur += ch; }
    else if (ch === '"' || ch === "'") q = ch;
    else if (/\s/.test(ch)) { if (cur) out.push(cur); cur = ""; }
    else cur += ch;
  }
  if (cur) out.push(cur);
  return out;
}

/** Dataset folders + resolution / buckets / batch. Mutates `ds` and calls onchange(). */
export function datasetEditor(ds, onchange, { compact = false } = {}) {
  const wrap = h("div.stack");
  const set = (k, v) => { ds[k] = v; onchange(ds); };
  const num = (k, ph, w) => h("input.input.nums", { value: ds[k] ?? "", placeholder: ph, style: w ? { width: w } : null,
    onchange: (e) => set(k, e.target.value === "" ? null : Number(e.target.value)) });

  function render() {
    const subsets = h("div.stack.sm",
      (ds.subsets || []).map((s, i) => h("div.subset",
        h("div.field", i === 0 ? h("label", "Image folder") : null,
          pathInput(s.image_dir, (v) => { s.image_dir = v; onchange(ds); }, { folder: true, placeholder: "C:/datasets/my_character" })),
        h("div.field", i === 0 ? h("label", "Repeats") : null,
          h("input.input.nums", { value: s.num_repeats ?? 1, type: "number", min: 1,
            onchange: (e) => { s.num_repeats = Number(e.target.value) || 1; onchange(ds); } })),
        btn("", { icon: "trash", kind: "ghost", title: "Remove folder", disabled: ds.subsets.length < 2,
          onclick: () => { ds.subsets.splice(i, 1); onchange(ds); render(); } }))),
      h("div", btn("Add another folder", { icon: "plus", kind: "ghost", size: "sm",
        onclick: () => { ds.subsets.push({ image_dir: "", num_repeats: 1 }); onchange(ds); render(); } })));

    const res = ds.resolution || [1024, 1024];
    const opts = h("div.grid.c4",
      h("div.field", h("label", "Resolution"), h("div.row.nowrap",
        h("input.input.nums", { value: res[0], onchange: (e) => { ds.resolution = [Number(e.target.value), ds.resolution[1]]; onchange(ds); } }),
        h("span.faint", "×"),
        h("input.input.nums", { value: res[1], onchange: (e) => { ds.resolution = [ds.resolution[0], Number(e.target.value)]; onchange(ds); } }))),
      h("div.field", h("label", "Batch size"), num("batch_size", "1")),
      h("div.field", h("label", "Caption extension"), h("input.input", { value: ds.caption_extension || ".txt", onchange: (e) => set("caption_extension", e.target.value) })),
      h("div.field", h("label", "Keep tokens"), num("keep_tokens", "0")));
    const bucket = h("div.grid.c4",
      h("div.field", h("label", "Aspect-ratio buckets"), switchEl(ds.enable_bucket !== false, (v) => { set("enable_bucket", v); render(); }, ds.enable_bucket !== false ? "On" : "Off")),
      ds.enable_bucket !== false ? [
        h("div.field", h("label", "Min bucket"), num("min_bucket_reso", "256")),
        h("div.field", h("label", "Max bucket"), num("max_bucket_reso", "2048")),
        h("div.field", h("label", "Bucket step"), num("bucket_reso_steps", "64")),
      ] : null);
    const flags = h("div.row", { style: { gap: "22px" } },
      checkEl(ds.shuffle_caption, (v) => set("shuffle_caption", v), "Shuffle captions"),
      checkEl(ds.flip_aug, (v) => set("flip_aug", v), "Flip augmentation"));
    clear(wrap, subsets, compact ? null : h("hr.soft"), opts, compact ? null : bucket, compact ? null : flags);
  }
  render();
  return wrap;
}

/** Scrolling log with a pinned progress line. */
export function logView(height = 320) {
  const el = h("div.log", { style: { height: height + "px" } });
  const body = h("div");
  const prog = h("div.prog.hidden");
  el.append(body, prog);
  let stick = true;
  el.addEventListener("scroll", () => { stick = el.scrollTop + el.clientHeight >= el.scrollHeight - 30; });
  const cls = (l) => (/^(>>|\$ )/.test(l) ? "ln-cmd" : /(error|traceback|exception|failed)/i.test(l) ? "ln-err" : /(saved|finished with exit code 0|up to date|all set)/i.test(l) ? "ln-ok" : "");
  return {
    el,
    append(lines) {
      if (!lines?.length) return;
      const frag = document.createDocumentFragment();
      for (const l of lines) frag.append(h("div", { class: cls(l) }, l || " "));
      body.append(frag);
      while (body.childNodes.length > 4000) body.firstChild.remove();
      if (stick) el.scrollTop = el.scrollHeight;
    },
    progress(line) {
      prog.classList.toggle("hidden", !line);
      prog.textContent = line || "";
      if (stick) el.scrollTop = el.scrollHeight;
    },
    clear() { body.replaceChildren(); prog.classList.add("hidden"); },
  };
}

/** Follow a backend Task (update, install...) into a log view. Resolves with the final snapshot. */
export function followTask(taskId, log, onDone) {
  let since = 0;
  let stopped = false;
  const tick = async () => {
    if (stopped) return;
    try {
      const t = await api.task(taskId, since);
      if (!t) return;
      log.append(t.lines);
      since = t.total;
      if (t.status === "running") setTimeout(tick, 600);
      else onDone?.(t);
    } catch (e) { toastError(e); }
  };
  tick();
  return () => { stopped = true; };
}
