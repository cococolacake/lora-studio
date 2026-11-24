// CSS themes: drop a .css file anywhere on Settings > Appearance (or click the drop zone to pick one)
// and it's installed into the data folder and switched on. The theme engine loads it in theme.js.
import { api } from "./api.js";
import { h, btn, toast, toastError, clear } from "./dom.js";
import { icon } from "./icons.js";
import { forgetCssTheme } from "./theme.js";

const isCss = (f) => /\.css$/i.test(f.name) || f.type === "text/css";
const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
const kb = (n) => (n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);

/**
 * The drop zone and the list of installed CSS themes.
 * getCurrent(): name of the CSS theme in use ("" = none). use(name): switch to it ("" = off).
 * Returns { el, refresh }; call refresh() when the theme in use changes elsewhere.
 */
export function cssThemes(ctx, { getCurrent, use }) {
  let list = ctx.boot.css_themes || [];
  const fileInput = h("input", { type: "file", accept: ".css,text/css", multiple: true, hidden: true,
    onchange: (e) => { addFiles([...e.target.files]); e.target.value = ""; } });
  const zone = h("div.css-drop", {
    role: "button", tabindex: "0", title: "Add a CSS theme",
    onclick: pick, onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } },
  }, h("span.css-drop-ic", icon("upload")),
    h("div", h("b", "Drop a .css theme here"), h("div.small.muted", "or click to choose a file. You can drop it anywhere on this page.")),
    fileInput);
  const rows = h("div.css-rows");
  const el = h("div.stack", zone, rows);

  async function pick() {
    if (ctx.boot.native) {   // the app window: the system file picker
      try { const r = await api.import_css_theme(); if (r) done(r); } catch (e) { toastError(e); }
    } else fileInput.click();
  }

  async function addFiles(files) {
    const css = files.filter(isCss);
    if (!css.length) { toast("Not a CSS file", "Drop a file that ends in .css.", "warn", "alert"); return; }
    let last = null;
    for (const f of css) {
      try { last = await api.add_css_theme(f.name, await f.text()); } catch (e) { toastError(e); }
    }
    if (last) done(last, css.length);
  }

  function done(r, n = 1) {
    list = ctx.boot.css_themes = r.themes;
    forgetCssTheme(r.name);   // a theme dropped again with the same name replaces the old one
    use(r.name);
    toast(n > 1 ? `${n} CSS themes added` : "CSS theme added", `Now using ${r.name}.`, "good", "palette");
    refresh();
  }

  async function remove(name) {
    try {
      list = ctx.boot.css_themes = await api.delete_css_theme(name);
      forgetCssTheme(name);
      if (getCurrent() === name) use("");
      refresh();
    } catch (e) { toastError(e); }
  }

  function refresh() {
    const cur = getCurrent() || "";
    clear(rows, list.map((t) => h("div.list-row",
      h("div.ic", { class: t.name === cur ? "accent" : "" }, icon("palette")),
      h("div", { style: { flex: 1, minWidth: 0 } }, h("div", { style: { fontWeight: 500 } }, t.name), h("div.small.faint", kb(t.size))),
      t.name === cur
        ? [h("span.chip.accent", h("span.dot"), "In use"), btn("Turn off", { kind: "ghost", size: "sm", onclick: () => { use(""); refresh(); } })]
        : btn("Use", { size: "sm", icon: "check", onclick: () => { use(t.name); refresh(); } }),
      btn("", { kind: "ghost", size: "sm", icon: "trash", title: `Delete ${t.name}`, onclick: () => remove(t.name) }))));
  }

  // Drop anywhere on the page: the zone lights up while a file is held over the window.
  let depth = 0;
  const on = {
    dragenter: (e) => { if (!hasFiles(e)) return; depth++; zone.classList.add("over"); },
    dragleave: (e) => { if (!hasFiles(e)) return; if (--depth <= 0) { depth = 0; zone.classList.remove("over"); } },
    dragover: (e) => { if (hasFiles(e)) { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; } },
    drop: (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault(); depth = 0; zone.classList.remove("over");
      addFiles([...e.dataTransfer.files]);
    },
  };
  for (const [ev, fn] of Object.entries(on)) document.addEventListener(ev, fn);
  ctx.onLeave(() => { for (const [ev, fn] of Object.entries(on)) document.removeEventListener(ev, fn); });

  refresh();
  return { el, refresh };
}
