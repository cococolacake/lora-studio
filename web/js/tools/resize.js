// Crop & resize: batch-resize to a target size (long side / short side / exact crop), or crop images one by one.
import { api } from "../api.js";
import { h, btn, card, empty, toast, toastError, confirmBox, clear, store } from "../dom.js";
import { icon } from "../icons.js";
import { seg, checkEl } from "../components.js";
import { thumbUrl } from "../media.js";
import { openCropper } from "../cropper.js";
import { folderBar, getFolder, taskProgress, watchTask } from "./common.js";

const SIDE_SIZES = [512, 768, 1024, 1536, 2048];
const EXACT_SIZES = [[1024, 1024], [832, 1216], [1216, 832], [896, 1152], [1152, 896], [768, 1344], [2048, 2048]];

export function resize(ctx, params, root) {
  let folder = getFolder(ctx);
  let images = [];
  const bust = {};
  const o = { mode: "long", width: 1024, height: 1024, anchor: "center", upscale: false, ...store.get("resize", {}) };
  const save = () => store.set("resize", o);
  const prog = taskProgress();
  const optsSlot = h("div");
  const summary = h("div.small.muted");
  const gridSlot = h("div");

  root.append(ctx.header({ title: "Crop & resize", subtitle: "Resize a whole folder to a set size, or click any image to crop it by hand.", icon: "crop" }),
    h("div.stack",
      card({ title: "Folder" }, folderBar(ctx, folder, (f) => { folder = f; load(); })),
      card({ title: "Batch resize" }, optsSlot, h("div", { style: { marginTop: "14px" } }, prog.el)),
      gridSlot));

  function wouldChange(img) {
    if (!img.w) return false;
    const { w, h: hh } = img;
    if (o.mode === "long") { const s = o.width / Math.max(w, hh); return s < 1 || (o.upscale && s > 1); }
    if (o.mode === "short") { const s = o.width / Math.min(w, hh); return s < 1 || (o.upscale && s > 1); }
    return w !== o.width || hh !== o.height;
  }

  function drawOpts() {
    const n = images.filter(wouldChange).length;
    const sizeChips = o.mode === "exact"
      ? EXACT_SIZES.map(([w, hh]) => h("button.pick", { class: o.width === w && o.height === hh ? "on" : "", onclick: () => { o.width = w; o.height = hh; save(); drawOpts(); } }, `${w}×${hh}`))
      : SIDE_SIZES.map((s) => h("button.pick", { class: o.width === s ? "on" : "", onclick: () => { o.width = s; save(); drawOpts(); } }, String(s)));
    const custom = o.mode === "exact"
      ? h("div.row.nowrap", h("input.input.nums", { value: o.width, style: { width: "90px" }, onchange: (e) => { o.width = Number(e.target.value) || 1024; save(); drawOpts(); } }), h("span.faint", "×"),
        h("input.input.nums", { value: o.height, style: { width: "90px" }, onchange: (e) => { o.height = Number(e.target.value) || 1024; save(); drawOpts(); } }))
      : h("input.input.nums", { value: o.width, style: { width: "100px" }, onchange: (e) => { o.width = Number(e.target.value) || 1024; save(); drawOpts(); } });
    const explain = {
      long: `The longer side becomes ${o.width}px; the other side scales to keep the shape.`,
      short: `The shorter side becomes ${o.width}px; the other side scales to keep the shape.`,
      exact: `Every image becomes exactly ${o.width}×${o.height}: scaled to fill, then cropped ${o.anchor === "top" ? "from the top (keeps faces in portraits)" : "around the centre"}.`,
    }[o.mode];
    clear(optsSlot, h("div.stack",
      h("div.row", { style: { gap: "22px", alignItems: "flex-end" } },
        h("div.field", h("label", "Mode"), seg([["long", "Long side"], ["short", "Short side"], ["exact", "Exact size (crop)"]], o.mode, (v) => {
          o.mode = v; if (v === "exact" && !o.height) o.height = o.width; save(); drawOpts(); })),
        h("div.field", h("label", o.mode === "exact" ? "Size" : "Pixels"), custom),
        o.mode === "exact" ? h("div.field", h("label", "Keep"), seg([["center", "Centre"], ["top", "Top"]], o.anchor, (v) => { o.anchor = v; save(); drawOpts(); }))
          : h("div.field", checkEl(o.upscale, (v) => { o.upscale = v; save(); drawOpts(); }, "Also enlarge smaller images"))),
      h("div.chip-grid", sizeChips),
      h("div.row", h("div.small.muted", { style: { flex: 1 } }, explain),
        images.length ? h("b.small", `${n} of ${images.length} images will change`) : null,
        btn("Resize", { icon: "crop", kind: "primary", disabled: !n, onclick: run }))));
  }

  async function run() {
    const n = images.filter(wouldChange).length;
    if (!(await confirmBox(`Resize ${n} images?`, "Each original is copied to an _originals folder the first time it's changed, so you can always restore it."))) return;
    try {
      const id = await api.ds_batch_resize({ folder, mode: o.mode, width: o.width, height: o.height, anchor: o.anchor, upscale: o.upscale });
      const t = await watchTask(id, (s) => prog.set(s));
      if (t?.status === "done") {
        toast("Resized", `${t.result.changed} images`, "good", "crop");
        images.forEach((i) => { bust[i.path] = Date.now(); });
      }
      load();
    } catch (e) { toastError(e); }
  }

  async function load() {
    if (!folder) { drawOpts(); clear(gridSlot); return; }
    try {
      images = (await api.ds_list(folder)).images;
    } catch (e) { images = []; clear(gridSlot, card(null, empty("alert", "Couldn't open that folder", e.message))); drawOpts(); return; }
    drawOpts();
    const sizes = {};
    for (const i of images) if (i.w) sizes[`${i.w}×${i.h}`] = (sizes[`${i.w}×${i.h}`] || 0) + 1;
    clear(gridSlot, card({ title: "Images", actions: h("span.small.faint", "Click to crop one image") },
      h("div.row", { style: { marginBottom: "12px", gap: "6px" } }, Object.entries(sizes).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([s, c]) => h("span.tag", s, h("b", String(c))))),
      images.length ? h("div.vgrid.small-tiles", images.map((img) => h("button.vtile", { onclick: async () => {
        if (await openCropper(img)) { bust[img.path] = Date.now(); load(); }
      }, title: `${img.name} · ${img.w}×${img.h}` },
      h("img", { src: thumbUrl(img.path, 256, bust[img.path]), loading: "lazy" }),
      h("span.vsize", `${img.w}×${img.h}`),
      img.backup ? h("span.vbadge.info", icon("crop")) : null,
      wouldChange(img) ? h("span.vbadge.accent", { title: "Will change" }, icon("sparkle")) : null)))
        : empty("image", "No images", "This folder has no images.")));
  }

  drawOpts();
  load();
}
