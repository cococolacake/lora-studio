// Images & tags: browse a dataset, edit captions with autocomplete, auto-tag, bulk edit, crop, delete.
import { api } from "../api.js";
import { h, btn, card, chip, empty, toast, toastError, modal, confirmBox, promptBox, clear, store } from "../dom.js";
import { icon } from "../icons.js";
import { seg, switchEl, checkEl } from "../components.js";
import { thumbUrl, fileUrl, bucketFor } from "../media.js";
import { openCropper } from "../cropper.js";
import { folderBar, getFolder, taskProgress, watchTask, missingNotice } from "./common.js";

const tagKey = (t) => t.trim().toLowerCase().replace(/_/g, " ").split(/\s+/).join(" ");
const parseTags = (s) => (s || "").replace(/\n/g, ",").split(",").map((t) => t.trim()).filter(Boolean);

export function viewer(ctx, params, root) {
  let folder = getFolder(ctx);
  let data = null;
  let view = "dataset";            // dataset | _deleted
  let shown = [];
  let sel = 0;
  let filter = { q: "", mode: "any", special: "" };
  let tags = [];                   // tags of the selected image (editor state)
  let dirty = false;
  let raw = store.get("tagRaw", false);
  let autosave = store.get("tagAutosave", true);
  const bust = {};                 // path -> version, to refresh thumbnails after a crop
  let panel = null;                // "autotag" | "bulk" | null

  const headSlot = h("div");
  const panelSlot = h("div");
  const gridEl = h("div.vgrid");
  const listInfo = h("span.small.faint");
  const editor = h("div.stack.sm");
  const binBtn = h("div");
  const filterRow = h("div.row");

  root.append(headSlot,
    h("div.stack",
      card(null, folderBar(ctx, folder, (f) => { folder = f; view = "dataset"; load(); })),
      panelSlot,
      h("div.viewer",
        card(null, filterRow, h("div.vgrid-wrap", gridEl)),
        h("div.viewer-side", card(null, editor)))));

  // ---- header ----
  function header() {
    const n = data?.images.length ?? 0;
    clear(headSlot, ctx.header({
      title: view === "_deleted" ? "Deleted images" : "Images & tags",
      subtitle: data ? `${folder.split(/[\\/]/).pop()} · ${n} image${n === 1 ? "" : "s"}` : "Pick a dataset folder to start.",
      icon: view === "_deleted" ? "trash" : "tag",
      actions: data && view === "dataset" ? [
        btn("Auto-tag", { icon: "sparkle", kind: panel === "autotag" ? "primary" : "", onclick: () => togglePanel("autotag") }),
        btn("Bulk edit", { icon: "list", kind: panel === "bulk" ? "primary" : "", onclick: () => togglePanel("bulk") }),
        btn("Tags", { icon: "chart", title: "Tag overview: every tag and how often it\u2019s used", onclick: showStats }),
        btn("", { icon: "rollback", title: "Undo last bulk edit", onclick: undo }),
      ] : data ? [btn("Back to dataset", { icon: "left", onclick: () => { view = "dataset"; load(); } })] : [],
    }));
  }

  // ---- loading & filtering ----
  async function load(keepPath) {
    if (!folder) { header(); clear(gridEl, empty("folder", "No folder yet", "Choose the folder with your training images.")); clear(editor); return; }
    try {
      data = await api.ds_list(folder, view === "_deleted" ? "_deleted" : null);
    } catch (e) { data = null; header(); clear(gridEl, empty("alert", "Couldn't open that folder", e.message)); clear(editor); return; }
    header();
    applyFilter(keepPath);
  }

  function matches(img) {
    if (filter.special === "nocap" && img.caption) return false;
    if (filter.special === "cropped" && !img.backup) return false;
    const want = parseTags(filter.q).map(tagKey);
    if (!want.length) return true;
    const have = new Set(parseTags(img.caption).map(tagKey));
    const hits = want.map((w) => have.has(w));
    return filter.mode === "all" ? hits.every(Boolean) : filter.mode === "none" ? !hits.some(Boolean) : hits.some(Boolean);
  }

  function applyFilter(keepPath) {
    const cur = keepPath || shown[sel]?.path;
    shown = data.images.filter(matches);
    sel = Math.max(0, shown.findIndex((i) => i.path === cur));
    if (sel < 0) sel = 0;
    drawFilter();
    drawGrid();
    select(sel, true);
  }

  function drawFilter() {
    const filtering = filter.q || filter.special;
    listInfo.textContent = filtering ? `${shown.length} of ${data.images.length}` : `${data.images.length} images`;
    const q = h("input.input", { placeholder: "Filter by tags, e.g. smile, hat", value: filter.q,
      onkeydown: (e) => { if (e.key === "Enter") { filter.q = e.target.value; applyFilter(); } },
      onchange: (e) => { filter.q = e.target.value; applyFilter(); } });
    const deleted = data.bins?._deleted || 0;
    clear(filterRow,
      view === "dataset" ? [
        h("div.search", { style: { flex: 1, minWidth: "200px" } }, icon("search"), q),
        h("select.select", { style: { width: "130px" }, onchange: (e) => { filter.mode = e.target.value; applyFilter(); } },
          [["any", "Has any"], ["all", "Has all"], ["none", "Has none"]].map(([v, l]) => h("option", { value: v, selected: filter.mode === v }, l))),
        seg([["", "All"], ["nocap", "No caption"], ["cropped", "Edited"]], filter.special, (v) => { filter.special = v; applyFilter(); }),
      ] : h("div.small.muted", { style: { flex: 1 } }, "Deleted images live in the _deleted folder inside your dataset. Restore any you want back."),
      h("div.spacer"), listInfo,
      view === "dataset" && deleted ? btn(`Deleted (${deleted})`, { icon: "trash", size: "sm", kind: "ghost", onclick: () => { view = "_deleted"; load(); } }) : null,
      view === "_deleted" && data.images.length ? btn("Restore all", { icon: "rollback", size: "sm", onclick: async () => {
        await api.ds_restore(data.images.map((i) => i.path)); toast("Restored", `${data.images.length} images`, "good", "rollback"); view = "dataset"; load();
      } }) : null,
      view === "_deleted" && data.images.length ? btn("Delete permanently", { icon: "trash", size: "sm", kind: "danger", onclick: async () => {
        if (!(await confirmBox(`Delete ${data.images.length} images for good?`, "This empties the _deleted folder, captions included. It can't be undone.", "Delete permanently", true))) return;
        const r = await api.ds_empty_bin(folder, "_deleted"); toast("Deleted", `${r.deleted} images removed for good`, "good", "trash"); view = "dataset"; load();
      } }) : null);
  }

  function drawGrid() {
    if (!shown.length) {
      clear(gridEl, empty(view === "_deleted" ? "trash" : "search", view === "_deleted" ? "Nothing deleted" : "No images match", view === "_deleted" ? "Images you delete show up here." : "Try a different filter."));
      return;
    }
    clear(gridEl, shown.map((img, i) => {
      const tile = h("button.vtile", { onclick: () => select(i), title: img.caption || "(no caption)" },
        h("img", { src: thumbUrl(img.path, 256, bust[img.path]), loading: "lazy", draggable: false }),
        img.caption == null ? h("span.vbadge.warn", { title: "No caption" }, icon("alert")) : null,
        img.backup ? h("span.vbadge.info", { title: "Edited (original kept)" }, icon("crop")) : null);
      return tile;
    }));
    markSel();
  }

  function markSel() {
    gridEl.querySelectorAll(".vtile").forEach((t, i) => t.classList.toggle("on", i === sel));
    gridEl.children[sel]?.scrollIntoView?.({ block: "nearest" });
  }

  // ---- editor ----
  async function select(i, force = false) {
    if (!shown.length) { clear(editor, h("p.muted.small", "No image selected.")); return; }
    if (!force && i === sel && editor.childNodes.length) return;
    if (dirty && autosave) await saveTags(true);
    sel = Math.max(0, Math.min(shown.length - 1, i));
    const img = shown[sel];
    tags = parseTags(img.caption);
    dirty = false;
    markSel();
    drawEditor();
  }

  function drawEditor() {
    const img = shown[sel];
    if (!img) return;
    const inBin = view === "_deleted";
    const preview = h("div.vpreview", { ondblclick: () => !inBin && crop() },
      h("img", { src: fileUrl(img.path, bust[img.path]), draggable: false }));
    const meta = h("div.row.small", h("b.ellipsis", { style: { flex: 1 } }, img.name),
      img.w ? h("span.faint", `${img.w}×${img.h}`) : null,
      img.w ? chip(`bucket ~${bucketFor(img.w, img.h, ctx.draft?.dataset?.resolution?.[0] || 1024)}`, "") : null);
    const tools = h("div.row.nowrap",
      btn("", { icon: "left", size: "sm", title: "Previous (←)", onclick: () => select(sel - 1) }),
      btn("", { icon: "right", size: "sm", title: "Next (→)", onclick: () => select(sel + 1) }),
      h("span.small.faint", `${sel + 1} / ${shown.length}`),
      h("div.spacer"),
      inBin ? btn("Restore", { icon: "rollback", size: "sm", kind: "primary", onclick: () => restore([img.path]) }) : [
        btn("Crop", { icon: "crop", size: "sm", title: "Crop & resize (C)", onclick: crop }),
        btn("", { icon: "trash", size: "sm", kind: "ghost danger", title: "Delete (Del) - moves to _deleted", onclick: del }),
      ]);
    clear(editor, preview, meta, tools, inBin ? null : tagEditor());
  }

  function tagEditor() {
    const saveBtn = btn("Save", { icon: "save", size: "sm", kind: "primary", onclick: () => saveTags(false) });
    const markDirty = () => { dirty = true; saveBtn.classList.add("pulse"); };
    let body;
    if (raw) {
      body = h("textarea.input.mono", { rows: 7, value: tags.join(", "), oninput: (e) => { tags = parseTags(e.target.value); markDirty(); } });
    } else {
      const chips = h("div.tagchips");
      const input = h("input.tag-input", { placeholder: tags.length ? "Add a tag…" : "Type a tag and press Enter" });
      const sug = h("div.suggest.hidden");
      let sugIdx = -1, sugItems = [], timer = null;
      const drawChips = () => {
        clear(chips, tags.map((t, i) => h("span.tagchip", { class: i === 0 && trigger() && tagKey(t) === tagKey(trigger()) ? "trig" : "" }, t,
          h("button", { title: "Remove", onclick: () => { tags.splice(i, 1); markDirty(); drawChips(); } }, icon("x")))), input);
      };
      const add = (t) => {
        t = t.trim().replace(/,$/, "");
        if (!t) return;
        if (!tags.some((x) => tagKey(x) === tagKey(t))) tags.push(t);
        input.value = ""; markDirty(); drawChips(); hideSug(); input.focus();
      };
      const hideSug = () => { sug.classList.add("hidden"); sugIdx = -1; };
      const drawSug = () => {
        clear(sug, sugItems.map((t, i) => h("button", { class: i === sugIdx ? "on" : "", onmousedown: (e) => { e.preventDefault(); add(t); } }, t)));
        sug.classList.toggle("hidden", !sugItems.length);
      };
      input.addEventListener("input", () => {
        clearTimeout(timer);
        const v = input.value;
        if (v.includes(",")) { v.split(",").slice(0, -1).forEach(add); input.value = v.split(",").pop(); }
        timer = setTimeout(async () => {
          if (!input.value.trim()) return hideSug();
          try { sugItems = await api.autocomplete(input.value); } catch { sugItems = []; }
          sugIdx = -1; drawSug();
        }, 120);
      });
      input.addEventListener("keydown", (e) => {
        if (e.key === "ArrowDown" && sugItems.length) { sugIdx = (sugIdx + 1) % sugItems.length; drawSug(); e.preventDefault(); }
        else if (e.key === "ArrowUp" && sugItems.length) { sugIdx = (sugIdx - 1 + sugItems.length) % sugItems.length; drawSug(); e.preventDefault(); }
        else if (e.key === "Enter" || e.key === "Tab") { if (sugIdx >= 0) { add(sugItems[sugIdx]); e.preventDefault(); } else if (input.value.trim()) { add(input.value); e.preventDefault(); } }
        else if (e.key === "Backspace" && !input.value && tags.length) { tags.pop(); markDirty(); drawChips(); }
        else if (e.key === "Escape") hideSug();
      });
      input.addEventListener("blur", () => setTimeout(hideSug, 150));
      drawChips();
      body = h("div.tag-wrap", h("div.tagbox", { onclick: (e) => { if (e.target === e.currentTarget || e.target === chips) input.focus(); } }, chips), sug);
    }
    return h("div.stack.sm",
      h("div.row", h("span.label", "Tags"), h("span.small.faint", `${tags.length}`), h("div.spacer"),
        switchEl(raw, (v) => { raw = v; store.set("tagRaw", v); drawEditor(); }, "Text")),
      body,
      h("div.row", checkEl(autosave, (v) => { autosave = v; store.set("tagAutosave", v); }, "Save when switching images"), h("div.spacer"), saveBtn),
      h("div.tiny.faint", "← → to move · Del to delete · C to crop · Ctrl+S to save"));
  }

  const trigger = () => (ctx.draft?.lora_info?.trigger || ctx.draft?.trigger || "").trim();

  async function saveTags(quiet) {
    const img = shown[sel];
    if (!img) return;
    try {
      const text = tags.join(", ");
      await api.ds_save_caption(img.path, text);
      img.caption = text;
      dirty = false;
      editor.querySelector(".pulse")?.classList.remove("pulse");
      const tile = gridEl.children[sel];
      tile?.querySelector(".vbadge.warn")?.remove();
      if (!quiet) toast("Saved", img.name, "good", "check", 1500);
    } catch (e) { toastError(e); }
  }

  async function crop() {
    const img = shown[sel];
    if (!img) return;
    if (dirty) await saveTags(true);
    if (await openCropper(img)) {
      bust[img.path] = Date.now();
      await load(img.path);
    }
  }

  async function del() {
    const img = shown[sel];
    if (!img) return;
    try {
      const r = await api.ds_move([img.path], "_deleted");
      const t = toast("Moved to _deleted", img.name, "", "trash", 6000);
      t.querySelector(":scope > div:nth-child(2)").append(h("div", btn("Undo", { size: "sm", kind: "ghost", onclick: async () => { t.remove(); await api.ds_restore(r.dest); load(img.path); } })));
      data.images = data.images.filter((x) => x.path !== img.path);
      data.bins._deleted = (data.bins._deleted || 0) + 1;
      header();
      applyFilter(shown[sel + 1]?.path || shown[sel - 1]?.path);
    } catch (e) { toastError(e); }
  }

  async function restore(paths) {
    await api.ds_restore(paths);
    toast("Restored", "", "good", "rollback", 2000);
    load();
  }

  async function undo() {
    try {
      const r = await api.ds_undo(folder);
      toast("Undone", `${r.description} (${r.restored} captions)`, "good", "rollback");
      load();
    } catch (e) { toast(e.message, "", "", "info", 2500); }
  }

  // ---- auto-tag & bulk panels ----
  function togglePanel(p) { panel = panel === p ? null : p; header(); drawPanel(); }

  function drawPanel() {
    if (!panel) return clear(panelSlot);
    if (panel === "autotag") return clear(panelSlot, autotagPanel());
    clear(panelSlot, bulkPanel());
  }

  function autotagPanel() {
    const o = { gen_threshold: 0.35, char_threshold: 0.75, trigger: trigger(), mode: "overwrite", blacklist: "", scope: "all", ...store.get("autotag", {}) };
    const saveO = () => store.set("autotag", o);
    const prog = taskProgress();
    const notes = h("div");
    const num = (k, step) => h("input.input.nums", { value: o[k], type: "number", step, min: 0, max: 1, onchange: (e) => { o[k] = Number(e.target.value); saveO(); } });
    const run = btn("Tag images", { icon: "sparkle", kind: "primary", onclick: go });
    async function go() {
      const imgs = (o.scope === "filtered" ? shown : data.images).map((i) => i.path);
      if (o.mode === "overwrite" && data.images.some((i) => i.caption) &&
        !(await confirmBox("Replace existing captions?", `Captions for ${imgs.length} images will be overwritten. You can't undo this one. Pick “Add to existing” to keep your tags.`, "Overwrite", true))) return;
      run.disabled = true;
      clear(notes);
      try {
        const id = await api.tag_images({ images: imgs, gen_threshold: o.gen_threshold, char_threshold: o.char_threshold,
          trigger: o.trigger, mode: o.mode, blacklist: parseTags(o.blacklist), batch_size: 4 });
        const t = await watchTask(id, (s) => prog.set(s));
        if (t?.missing) notes.append(missingNotice(t.missing, go));
        else if (t?.status === "done") { toast("Tagging finished", `${t.result.tagged} images tagged`, "good", "sparkle"); load(); }
        else if (t) notes.append(h("pre.code", t.lines.slice(-12).join("\n")));
      } catch (e) { toastError(e); }
      run.disabled = false;
    }
    return card({ title: "Auto-tag with WD EVA02 Canary", actions: btn("", { icon: "x", kind: "ghost", size: "sm", onclick: () => togglePanel("autotag") }) },
      h("div.grid.c4",
        h("div.field", h("label", "General threshold"), num("gen_threshold", 0.01)),
        h("div.field", h("label", "Character threshold"), num("char_threshold", 0.01)),
        h("div.field", h("label", "Trigger word (put first)"), h("input.input", { value: o.trigger, placeholder: "optional", onchange: (e) => { o.trigger = e.target.value; saveO(); } })),
        h("div.field", h("label", "Never add these tags"), h("input.input", { value: o.blacklist, placeholder: "e.g. simple background", onchange: (e) => { o.blacklist = e.target.value; saveO(); } }))),
      h("div.row", { style: { marginTop: "14px", gap: "18px" } },
        h("div.field", h("label", "Existing captions"), seg([["overwrite", "Replace"], ["merge", "Add to existing"], ["skip", "Only untagged"]], o.mode, (v) => { o.mode = v; saveO(); })),
        h("div.field", h("label", "Images"), seg([["all", "All"], ["filtered", `Filtered (${shown.length})`]], o.scope, (v) => { o.scope = v; saveO(); })),
        h("div.spacer"), run),
      h("div", { style: { marginTop: "12px" } }, prog.el), notes,
      h("p.tiny.faint", { style: { marginBottom: 0 } }, "Runs in your sd-scripts venv on the GPU. The model (~1 GB) downloads from Hugging Face the first time."));
  }

  function bulkPanel() {
    let onlyFiltered = !!(filter.q || filter.special);
    const v = { trigger: trigger(), tags: "", replace_with: "" };
    const run = async (op) => {
      const paths = onlyFiltered ? shown.map((i) => i.path) : null;
      const label = { trigger: `Put “${v.trigger}” first in`, add: `Add “${v.tags}” to`, delete: `Remove “${v.tags}” from`, replace: `Replace “${v.tags}” with “${v.replace_with}” in` }[op];
      if (!(await confirmBox("Bulk edit", `${label} ${onlyFiltered ? shown.length : data.images.length} captions? You can undo it.`))) return;
      try {
        const r = await api.ds_bulk(folder, op, v, paths);
        toast(r.description, `${r.changed} captions changed`, "good", "list");
        load();
      } catch (e) { toastError(e); }
    };
    const inp = (k, ph) => h("input.input", { placeholder: ph, value: v[k], oninput: (e) => { v[k] = e.target.value; } });
    return card({ title: "Bulk edit captions", actions: btn("", { icon: "x", kind: "ghost", size: "sm", onclick: () => togglePanel("bulk") }) },
      h("div.grid.c3",
        h("div.field", h("label", "Trigger word"), h("div.row.nowrap", inp("trigger", "mychar"), btn("Put first", { onclick: () => run("trigger") }))),
        h("div.field", h("label", "Tags (comma separated)"), h("div.row.nowrap", inp("tags", "smile, hat"),
          btn("Add", { onclick: () => run("add") }), btn("Remove", { kind: "danger", onclick: () => run("delete") }))),
        h("div.field", h("label", "Replace those tags with"), h("div.row.nowrap", inp("replace_with", "grin"), btn("Replace", { onclick: () => run("replace") })))),
      h("div.row", { style: { marginTop: "12px" } },
        checkEl(onlyFiltered, (x) => { onlyFiltered = x; }, `Only the filtered images (${shown.length})`), h("div.spacer"),
        h("span.small.faint", "Undo with the ↺ button in the header.")));
  }

  // Tag overview: every tag with how many images use it. Click a tag to see those images;
  // rename (or merge) and remove act on all captions and can be undone.
  async function showStats() {
    const counts = new Map();
    let nocap = 0;
    for (const img of data.images) {
      if (img.caption == null) { nocap++; continue; }
      for (const k of new Set(parseTags(img.caption).map(tagKey))) counts.set(k, (counts.get(k) || 0) + 1);
    }
    const all = [...counts];
    const total = data.images.length || 1;
    const max = Math.max(1, ...all.map((x) => x[1]));
    let q = "", sort = "most";
    const sorters = {
      most: (a, b) => b[1] - a[1] || a[0].localeCompare(b[0]),
      rare: (a, b) => a[1] - b[1] || a[0].localeCompare(b[0]),
      az: (a, b) => a[0].localeCompare(b[0]),
    };
    let close;
    const list = h("div.bars", { style: { maxHeight: "52vh", overflow: "auto", paddingRight: "6px" } });
    const act = async (fn) => { try { await fn(); close(); load(); } catch (e) { if (!e.quiet) toastError(e); } };
    const draw = () => clear(list, all.filter(([t]) => t.includes(q)).sort(sorters[sort]).slice(0, 500).map(([t, n]) =>
      h("div.bar-row.stat-row", { style: { gridTemplateColumns: "1fr 110px 74px auto auto" } },
        h("button.linkish", { title: "Show the images with this tag", onclick: () => { filter.q = t; filter.mode = "any"; filter.special = ""; applyFilter(); close(); } }, t),
        h("div.b", h("i", { style: { width: `${(n / max) * 100}%` } })),
        h("span.nums.small.muted", `${n} · ${Math.round((n / total) * 100)}%`),
        h("button.linkish", { onclick: () => act(async () => {
          const to = await promptBox(`Rename “${t}”`, "New tag (an existing tag merges them)", t);
          if (!to || tagKey(to) === tagKey(t)) throw Object.assign(new Error(""), { quiet: true });
          await api.ds_bulk(folder, "replace", { tags: t, replace_with: to });
          toast("Tag renamed", `${t} → ${to} in ${n} captions`, "good", "check");
        }) }, "rename"),
        h("button.linkish.danger", { onclick: () => act(async () => {
          if (!(await confirmBox(`Remove “${t}”?`, `It's removed from ${n} captions. You can undo it.`, "Remove", true))) throw Object.assign(new Error(""), { quiet: true });
          await api.ds_bulk(folder, "delete", { tags: t });
        }) }, "remove"))));
    draw();
    const p = modal(`Tag overview · ${all.length} tags`, h("div.stack.sm",
      h("p.small.muted", { style: { margin: 0 } }, `${data.images.length} images${nocap ? `, ${nocap} without a caption` : ""}. Click a tag to see its images; “Rarest” is handy for spotting typos and junk tags.`),
      h("div.row", { style: { gap: "10px", flexWrap: "wrap" } },
        h("div.search", { style: { flex: 1, minWidth: "200px" } }, icon("search"), h("input.input", { placeholder: "Search tags", oninput: (e) => { q = e.target.value.toLowerCase(); draw(); } })),
        seg([["most", "Most used"], ["rare", "Rarest"], ["az", "A–Z"]], sort, (v) => { sort = v; draw(); })),
      list),
      [{ label: "Close", kind: "ghost" }]);
    close = () => document.querySelector(".scrim")?.remove();
    await p;
  }

  // ---- keyboard ----
  const onKey = (e) => {
    if (!data || document.querySelector(".scrim, .lightbox")) return;
    const typing = /INPUT|TEXTAREA|SELECT/.test(e.target.tagName);
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); saveTags(false); return; }
    if (typing) return;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") { select(sel + 1); e.preventDefault(); }
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") { select(sel - 1); e.preventDefault(); }
    else if (e.key === "Delete" && view === "dataset") del();
    else if (e.key.toLowerCase() === "c" && view === "dataset") crop();
  };
  window.addEventListener("keydown", onKey);
  ctx.onLeave(() => window.removeEventListener("keydown", onKey));
  ctx.onLeave(() => { if (dirty && autosave) saveTags(true); });

  header();
  load();
}
