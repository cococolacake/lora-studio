// Rename: DATA_1, DATA_2… (images and their captions together), with a preview first.
import { api } from "../api.js";
import { h, btn, card, empty, toast, toastError, confirmBox, clear, store } from "../dom.js";
import { icon } from "../icons.js";
import { checkEl } from "../components.js";
import { folderBar, getFolder } from "./common.js";

export function rename(ctx, params, root) {
  let folder = getFolder(ctx);
  const o = { prefix: "DATA_", start: 1, recursive: false, ...store.get("rename", {}) };
  const save = () => store.set("rename", o);
  const preview = h("div");

  root.append(ctx.header({ title: "Rename", subtitle: "Give every image a clean, numbered name. Captions follow their images.", icon: "rename" }),
    h("div.stack",
      card({ title: "Settings" },
        folderBar(ctx, folder, (f) => { folder = f; show(); }, { button: "Preview", icon: "eye" }),
        h("div.grid.c3", { style: { marginTop: "16px", alignItems: "end" } },
          h("div.field", h("label", "Name prefix"), h("input.input.mono", { value: o.prefix, oninput: (e) => { o.prefix = e.target.value; save(); } })),
          h("div.field", h("label", "Start at"), h("input.input.nums", { type: "number", min: 0, value: o.start, oninput: (e) => { o.start = Number(e.target.value) || 0; save(); } })),
          h("div.field", checkEl(o.recursive, (v) => { o.recursive = v; save(); }, "Include subfolders")))),
      preview));

  async function show() {
    folder = getFolder(ctx) || folder;
    if (!folder) return;
    try {
      const plans = await api.ds_rename_plan(folder, o.prefix, o.start, o.recursive);
      const total = plans.reduce((n, p) => n + p.items.length, 0);
      if (!total) return clear(preview, card(null, empty("image", "No images here", "Pick a folder that has images in it.")));
      const conflicts = plans.filter((p) => p.conflicts.length);
      clear(preview, card({ title: `Preview · ${total} images`, actions: btn(`Rename ${total} images`, { icon: "rename", kind: "primary", onclick: apply }) },
        conflicts.length ? h("div.notice.warn", { style: { marginBottom: "12px" } }, icon("alert"),
          h("div", "These folders will be skipped because a file already uses a target name: ",
            h("span.mono", conflicts.map((c) => `${c.folder} (${c.conflicts.slice(0, 3).join(", ")}…)`).join("; ")))) : null,
        h("div.rename-list", plans.flatMap((p) => p.items.slice(0, 60).map((it) =>
          h("div.rename-row", h("span.mono.ellipsis", it.from.split(/[\\/]/).pop()), icon("right"),
            h("b.mono", it.to.split(/[\\/]/).pop()), it.cap_from ? h("span.chip", "+ caption") : h("span.chip.warn", "no caption"))))),
        total > 60 ? h("p.tiny.faint", `…and ${total - 60} more`) : null));
    } catch (e) { toastError(e); }
  }

  async function apply() {
    if (!(await confirmBox("Rename images?", "Images and their captions are renamed in place. Nothing is overwritten. Folders with name clashes are skipped."))) return;
    try {
      const r = await api.ds_rename(folder, o.prefix, o.start, o.recursive);
      toast("Renamed", `${r.renamed} images${r.skipped_folders.length ? `, ${r.skipped_folders.length} folder(s) skipped` : ""}`, "good", "rename");
      show();
    } catch (e) { toastError(e); }
  }

  if (folder) show();
}
