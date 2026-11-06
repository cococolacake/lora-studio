// Duplicates: CLIP similarity scan, then review groups before moving anything.
import { api } from "../api.js";
import { h, btn, card, empty, toast, toastError, confirmBox, clear, store } from "../dom.js";
import { icon } from "../icons.js";
import { rangeEl, checkEl } from "../components.js";
import { thumbUrl, lightbox } from "../media.js";
import { folderBar, getFolder, taskProgress, watchTask, missingNotice } from "./common.js";

export function dupes(ctx, params, root) {
  let folder = getFolder(ctx);
  const o = { threshold: 0.92, recursive: false, ...store.get("dupes", {}) };
  const prog = taskProgress();
  const results = h("div.stack");
  const binSlot = h("div");
  const thrLbl = h("b.nums", o.threshold.toFixed(2));
  const runBtn = btn("Find duplicates", { icon: "search", kind: "primary", onclick: run });

  root.append(ctx.header({ title: "Duplicates", subtitle: "Finds near-identical images with CLIP. Nothing moves until you say so.", icon: "dup" }),
    h("div.stack",
      card({ title: "Scan" },
        folderBar(ctx, folder, (f) => { folder = f; drawBin(); }, { button: "Use", icon: "check" }),
        h("div.grid.c3", { style: { marginTop: "16px", alignItems: "end" } },
          h("div.field", h("label", "Similarity ", thrLbl, h("span.faint.small", " higher = stricter")),
            rangeEl(o.threshold, 0.8, 0.99, 0.01, (v) => { o.threshold = v; thrLbl.textContent = v.toFixed(2); store.set("dupes", o); })),
          h("div.field", checkEl(o.recursive, (v) => { o.recursive = v; store.set("dupes", o); }, "Include subfolders")),
          h("div.row", h("div.spacer"), runBtn)),
        h("div", { style: { marginTop: "14px" } }, prog.el)),
      binSlot,
      results));

  async function drawBin() {
    const f = folder;
    if (!f) return clear(binSlot);
    const b = await api.ds_bins(f).catch(() => null);
    if (!b?._duplicates) return clear(binSlot);
    clear(binSlot, card(null, h("div.row",
      h("div.ic", { style: { width: "40px", height: "40px", borderRadius: "12px", display: "grid", placeItems: "center", background: "var(--warn-soft)", color: "var(--warn)" } }, icon("dup")),
      h("div", { style: { flex: 1 } }, h("b", `${b._duplicates} image${b._duplicates === 1 ? "" : "s"} in _duplicates`),
        h("div.small.muted", "Moved there earlier. Happy with them gone? Delete the folder for good.")),
      btn("Open folder", { icon: "folder", kind: "ghost", onclick: () => api.open_folder(`${f}/_duplicates`) }),
      btn("Delete permanently", { icon: "trash", kind: "danger solid", onclick: () => emptyDupes(f, b._duplicates) }))));
  }

  async function emptyDupes(f, n) {
    if (!(await confirmBox(`Delete ${n} duplicate images for good?`, "This removes the _duplicates folder and the captions inside it. It can't be undone.", "Delete permanently", true))) return;
    try {
      const r = await api.ds_empty_bin(f, "_duplicates");
      toast("Deleted", `${r.deleted} duplicate images removed`, "good", "trash");
      drawBin();
    } catch (e) { toastError(e); }
  }

  drawBin();
  if (params.autorun && folder) setTimeout(run, 50);

  async function run() {
    folder = getFolder(ctx) || folder;
    if (!folder) return toast("Pick a folder first", "", "", "folder");
    runBtn.disabled = true;
    clear(results);
    try {
      const id = await api.find_dupes({ folder, threshold: o.threshold, recursive: o.recursive });
      const t = await watchTask(id, (s) => prog.set(s));
      if (t?.missing) results.append(missingNotice(t.missing, run));
      else if (t?.status === "done") show(t.result);
      else if (t) results.append(h("pre.code", t.lines.slice(-12).join("\n")));
    } catch (e) { toastError(e); }
    runBtn.disabled = false;
  }

  function show(res) {
    const groups = res.groups;
    if (!groups.length) {
      clear(results, card(null, empty("circleCheck", "No duplicates found", `Scanned ${res.scanned} images at ${o.threshold.toFixed(2)} similarity.`)));
      return;
    }
    const picked = new Set(groups.flatMap((g) => g.dupes.map((d) => d.path)));
    const countLbl = h("b");
    const moveBtn = btn("Move", { icon: "folder", kind: "primary", onclick: async () => {
      try {
        const r = await api.ds_move([...picked], "_duplicates");
        toast("Moved to _duplicates", `${r.moved} images (with captions)`, "good", "folder");
        clear(results, card(null, empty("circleCheck", "Moved to _duplicates", `${r.moved} look-alikes are out of your dataset. Delete them for good now, or keep the folder for a while.`,
          btn("Delete permanently", { icon: "trash", kind: "danger solid", onclick: () => emptyDupes(folder, r.moved).then(() => clear(results)) }),
          btn("Open folder", { icon: "folder", onclick: () => api.open_folder(`${folder}/_duplicates`) }))));
        drawBin();
      } catch (e) { toastError(e); }
    } });
    const update = () => { countLbl.textContent = `${picked.size} selected`; moveBtn.lastChild.textContent = `Move ${picked.size} to _duplicates`; moveBtn.disabled = !picked.size; };
    const all = groups.flatMap((g) => [g.keep, ...g.dupes.map((d) => d.path)]).map((p) => ({ path: p }));
    const tile = (path, label, isKeep) => {
      const t = h("div.dtile", { class: isKeep ? "keep" : picked.has(path) ? "on" : "" },
        h("img", { src: thumbUrl(path, 256), loading: "lazy", onclick: () => lightbox(all, all.findIndex((x) => x.path === path)) }),
        h("div.dcap", isKeep ? h("span.chip.good", icon("check"), "Keep") : h("label.check", { onclick: (e) => e.stopPropagation() },
          h("input", { type: "checkbox", checked: picked.has(path), onchange: (e) => { e.target.checked ? picked.add(path) : picked.delete(path); t.classList.toggle("on", e.target.checked); update(); } }), "Move"),
        h("span.small.faint", label)));
      return t;
    };
    clear(results,
      card({ title: `${groups.length} group${groups.length === 1 ? "" : "s"} of look-alikes`, actions: h("div.row", countLbl, moveBtn) },
        h("p.small.muted", { style: { marginTop: 0 } }, "The first image in each row is kept. Click a picture to see it big; untick anything you want to leave alone."),
        h("div.stack", groups.map((g) => h("div.dgroup",
          tile(g.keep, g.keep.split("/").pop(), true),
          g.dupes.map((d) => tile(d.path, `${d.path.split("/").pop()} · ${(d.score * 100).toFixed(1)}%`, false)))))));
    update();
  }
}
