// Tiny DOM helpers: h("div.card.row", {onclick}, child, "text", [more])
import { icon } from "./icons.js";

export function h(sel, props, ...kids) {
  if (props instanceof Node || typeof props !== "object" || Array.isArray(props) || props == null) {
    if (props != null) kids.unshift(props);
    props = {};
  }
  const [tag, ...classes] = sel.split(".");
  let id = null;
  let t = tag || "div";
  if (t.includes("#")) [t, id] = t.split("#");
  const el = document.createElement(t || "div");
  if (id) el.id = id;
  if (classes.length) el.className = classes.join(" ");
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "class") el.className += " " + v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k === "html") el.innerHTML = v;
    else if (k === "value") el.value = v;
    else if (k in el && k !== "list" && typeof v !== "string") el[k] = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  append(el, kids);
  return el;
}

function append(el, kids) {
  for (const k of kids.flat(Infinity)) {
    if (k == null || k === false) continue;
    el.append(k instanceof Node ? k : document.createTextNode(String(k)));
  }
}

export const clear = (el, ...kids) => { el.replaceChildren(); append(el, kids); return el; };

export function btn(label, opts = {}) {
  const { icon: ic, kind = "", onclick, title, disabled, size = "" } = opts;
  const b = h(`button.btn${kind ? "." + kind.split(" ").join(".") : ""}${size ? "." + size : ""}`,
    { onclick, title, disabled, type: "button" }, ic ? icon(ic) : null, label || null);
  if (!label) b.classList.add("icon");
  return b;
}

export function card(title, ...kids) {
  let actions = null;
  if (title && typeof title === "object" && !(title instanceof Node)) ({ title, actions } = title);
  return h("section.card",
    title ? h("div.card-head", h("h3.card-title", title), h("div.spacer"), actions) : null, ...kids);
}

export function chip(text, kind = "", ic = null) {
  return h(`span.chip${kind ? "." + kind : ""}`, ic === "dot" ? h("span.dot") : ic ? icon(ic) : null, text);
}

export function empty(ic, title, text, ...actions) {
  return h("div.empty", h("div.art", icon(ic)), h("h3", title), h("p", text), h("div.row", { style: { justifyContent: "center" } }, actions));
}

export function kv(rows) {
  return h("div.kv", rows.filter(Boolean).map(([k, v]) => h("div.kv-row", h("span.faint", k), h("span", v ?? "—"))));
}

export function stat(k, v, small) {
  return h("div.stat", h("div.k", k), h("div.v", v ?? "—", small ? h("small", " " + small) : null));
}

// ---- toasts ----
export function toast(title, text = "", kind = "", ic = "bell", ms = 5000) {
  let host = document.querySelector(".toasts");
  if (!host) document.body.append(host = h("div.toasts"));
  const t = h(`div.toast${kind ? "." + kind : ""}`, h("div.ic", icon(ic)), h("div", h("b", title), text ? h("span", text) : null),
    btn("", { icon: "x", kind: "ghost", size: "sm", onclick: () => t.remove() }));
  t.querySelector(".btn").classList.add("x");
  host.append(t);
  if (ms) setTimeout(() => t.remove(), ms);
  return t;
}

export const toastError = (e) => toast("Something went wrong", e?.message || String(e), "bad", "alert", 9000);

// ---- modal ----
export function modal(title, body, actions = [], opts = {}) {
  return new Promise((resolve) => {
    const close = (v) => { scrim.remove(); resolve(v); };
    const scrim = h("div.scrim", { onmousedown: (e) => e.target === scrim && close(null) },
      h("div.modal", { class: opts.wide ? "wide" : "" },
        h("div.m-head", h("h3", title), h("div.spacer"), btn("", { icon: "x", kind: "ghost", size: "sm", onclick: () => close(null) })),
        h("div.m-body", body),
        h("div.m-foot", actions.map((a) => btn(a.label, { kind: a.kind, icon: a.icon, onclick: () => close(a.value ?? a.label) })))));
    document.body.append(scrim);
  });
}

export async function confirmBox(title, text, okLabel = "Continue", danger = false) {
  const r = await modal(title, h("p.muted", { style: { margin: "0 0 6px" } }, text),
    [{ label: "Cancel", kind: "ghost", value: false }, { label: okLabel, kind: danger ? "danger solid" : "primary", value: true }]);
  return r === true;
}

export async function promptBox(title, label, value = "") {
  const inp = h("input.input", { value });
  setTimeout(() => inp.focus(), 50);
  const r = await modal(title, h("div.field", h("label", label), inp),
    [{ label: "Cancel", kind: "ghost", value: false }, { label: "Save", kind: "primary", value: true }]);
  return r ? inp.value.trim() : null;
}

// ---- formatting ----
export function fmtDuration(s) {
  if (s == null || isNaN(s)) return "—";
  s = Math.round(s);
  const hh = Math.floor(s / 3600), mm = Math.floor((s % 3600) / 60), ss = s % 60;
  if (hh) return `${hh}h ${String(mm).padStart(2, "0")}m`;
  if (mm) return `${mm}m ${String(ss).padStart(2, "0")}s`;
  return `${ss}s`;
}

export function fmtAgo(ts) {
  if (!ts) return "";
  const d = Date.now() / 1000 - ts;
  if (d < 60) return "just now";
  if (d < 3600) return `${Math.floor(d / 60)} min ago`;
  if (d < 86400) return `${Math.floor(d / 3600)} h ago`;
  if (d < 86400 * 7) return `${Math.floor(d / 86400)} d ago`;
  return new Date(ts * 1000).toLocaleDateString();
}

export const fmtLoss = (v) => (v == null ? "—" : Number(v).toFixed(4));

export function fmtSize(b) {
  if (b == null) return "";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
  return `${b.toFixed(i ? 1 : 0)} ${u[i]}`;
}

export const STATUS = {
  queued: ["Queued", "info", "clock"],
  running: ["Training", "accent live", "dot"],
  done: ["Done", "good", "circleCheck"],
  failed: ["Failed", "bad", "circleX"],
  stopped: ["Stopped", "warn", "stop"],
  interrupted: ["Interrupted", "warn", "alert"],
  cancelled: ["Cancelled", "", "x"],
};

export function statusChip(s) {
  const [label, kind, ic] = STATUS[s] || [s, "", null];
  return chip(label, kind, ic);
}

// localStorage that never throws
export const store = {
  get(k, d = null) { try { const v = localStorage.getItem("ls:" + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("ls:" + k, JSON.stringify(v)); } catch { /* storage unavailable */ } },
};
