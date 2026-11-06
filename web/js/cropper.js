// Interactive crop window (Windows Photos style): drag the box, pick an aspect, optionally an exact output size.
import { api } from "./api.js";
import { h, btn, toast, toastError, confirmBox } from "./dom.js";
import { icon } from "./icons.js";
import { fileUrl } from "./media.js";

const ASPECTS = [["free", "Free"], ["orig", "Original"], ["1:1", "1:1"], ["2:3", "2:3"], ["3:2", "3:2"],
  ["3:4", "3:4"], ["4:3", "4:3"], ["9:16", "9:16"], ["16:9", "16:9"]];
const SIZES = [[1024, 1024], [832, 1216], [1216, 832], [896, 1152], [1152, 896], [2048, 2048]];

/** item: {path, name, w, h, backup}. Resolves true when the image was changed. */
export function openCropper(item) {
  return new Promise((resolve) => {
    let natW = item.w || 1, natH = item.h || 1;
    let rect = { x: 0, y: 0, w: natW, h: natH };
    let aspect = "free";
    let exact = false;
    let outW = 1024, outH = 1024;
    let changed = false;

    const img = h("img", { draggable: false });
    const box = h("div.crop-box", h("div.crop-grid"),
      ["nw", "n", "ne", "e", "se", "s", "sw", "w"].map((d) => h(`div.crop-h.h-${d}`, { "data-d": d })));
    const stage = h("div.crop-stage", img, box);
    const sizeLbl = h("div.crop-size");
    box.append(sizeLbl);
    const info = h("div.small.muted");

    // ---- geometry ----
    let view = { s: 1, ox: 0, oy: 0 };
    const layout = () => {
      const r = stage.getBoundingClientRect();
      const s = Math.min(r.width / natW, r.height / natH);
      view = { s, ox: (r.width - natW * s) / 2, oy: (r.height - natH * s) / 2 };
      Object.assign(img.style, { width: natW * s + "px", height: natH * s + "px", left: view.ox + "px", top: view.oy + "px" });
      draw();
    };
    const ratio = () => {
      if (exact) return outW / outH;
      if (aspect === "free") return null;
      if (aspect === "orig") return natW / natH;
      const [a, b] = aspect.split(":").map(Number);
      return a / b;
    };
    function clamp() {
      rect.w = Math.max(16, Math.min(rect.w, natW));
      rect.h = Math.max(16, Math.min(rect.h, natH));
      rect.x = Math.max(0, Math.min(rect.x, natW - rect.w));
      rect.y = Math.max(0, Math.min(rect.y, natH - rect.h));
    }
    function fitRatio() {
      // Like Photos: picking a ratio gives the biggest box of that shape, centred where the crop was.
      const r = ratio();
      if (!r) return;
      const cx = rect.x + rect.w / 2, cy = rect.y + rect.h / 2;
      const w = Math.min(natW, natH * r), hh = w / r;
      rect = { x: cx - w / 2, y: cy - hh / 2, w, h: hh };
      clamp();
    }
    function draw() {
      Object.assign(box.style, {
        left: view.ox + rect.x * view.s + "px", top: view.oy + rect.y * view.s + "px",
        width: rect.w * view.s + "px", height: rect.h * view.s + "px",
      });
      const cw = Math.round(rect.w), ch = Math.round(rect.h);
      sizeLbl.textContent = `${cw} × ${ch}`;
      info.textContent = exact ? `Crop ${cw}×${ch} px → saved as ${outW}×${outH}` : `Saved as ${cw}×${ch} px`;
      if (exact && (cw < outW || ch < outH)) info.textContent += " (upscaled)";
    }

    // ---- dragging ----
    let drag = null;
    stage.addEventListener("pointerdown", (e) => {
      const d = e.target.dataset?.d || (box.contains(e.target) ? "move" : "new");
      const r = stage.getBoundingClientRect();
      const px = (e.clientX - r.left - view.ox) / view.s, py = (e.clientY - r.top - view.oy) / view.s;
      drag = { d, sx: e.clientX, sy: e.clientY, start: { ...rect }, px, py };
      if (d === "new") { rect = { x: px, y: py, w: 16, h: 16 }; drag.d = "se"; drag.start = { ...rect }; }
      stage.setPointerCapture(e.pointerId);
      e.preventDefault();
    });
    stage.addEventListener("pointermove", (e) => {
      if (!drag) return;
      const dx = (e.clientX - drag.sx) / view.s, dy = (e.clientY - drag.sy) / view.s;
      const s0 = drag.start, r = ratio();
      if (drag.d === "move") {
        rect = { ...s0, x: s0.x + dx, y: s0.y + dy };
      } else {
        let { x, y, w, h: hh } = s0;
        const d = drag.d;
        if (d.includes("e")) w = s0.w + dx;
        if (d.includes("s")) hh = s0.h + dy;
        if (d.includes("w")) { w = s0.w - dx; x = s0.x + dx; }
        if (d.includes("n")) { hh = s0.h - dy; y = s0.y + dy; }
        if (r) {
          if (d === "n" || d === "s") w = hh * r; else hh = w / r;
          if (d.includes("n")) y = s0.y + s0.h - hh;
          if (d.includes("w")) x = s0.x + s0.w - w;
          if (d === "n" || d === "s") x = s0.x + (s0.w - w) / 2;
          if (d === "e" || d === "w") y = s0.y + (s0.h - hh) / 2;
        }
        if (w < 16 || hh < 16) return;
        // keep inside the image without breaking the ratio
        if (x < 0) { if (r) { w += x; hh = w / r; } else w += x; x = 0; }
        if (y < 0) { if (r) { hh += y; w = hh * r; } else hh += y; y = 0; }
        if (x + w > natW) { w = natW - x; if (r) hh = w / r; }
        if (y + hh > natH) { hh = natH - y; if (r) w = hh * r; }
        rect = { x, y, w, h: hh };
      }
      clamp();
      draw();
    });
    stage.addEventListener("pointerup", () => { drag = null; });

    // ---- side panel ----
    const aspectChips = h("div.chip-grid");
    const renderAspects = () => aspectChips.replaceChildren(...ASPECTS.map(([id, label]) =>
      h("button.pick", { class: !exact && aspect === id ? "on" : "", disabled: exact, onclick: () => { aspect = id; fitRatio(); draw(); renderAspects(); } }, label)));
    renderAspects();

    const wIn = h("input.input.nums", { value: outW, oninput: (e) => { outW = Number(e.target.value) || 1; if (exact) { fitRatio(); draw(); } } });
    const hIn = h("input.input.nums", { value: outH, oninput: (e) => { outH = Number(e.target.value) || 1; if (exact) { fitRatio(); draw(); } } });
    const sizeChips = h("div.chip-grid", SIZES.map(([w, hh]) => h("button.pick", { onclick: () => {
      outW = w; outH = hh; wIn.value = w; hIn.value = hh; setExact(true);
    } }, `${w}×${hh}`)));
    const exactBox = h("div.stack.sm", h("div.row.nowrap", wIn, h("span.faint", "×"), hIn), sizeChips);
    const exactSwitch = h("input", { type: "checkbox", onchange: (e) => setExact(e.target.checked) });
    function setExact(v) {
      exact = v;
      exactSwitch.checked = v;
      exactBox.classList.toggle("dim", !v);
      if (v) fitRatio();
      renderAspects();
      draw();
    }

    const save = async () => {
      try {
        await api.ds_crop(item.path, [rect.x, rect.y, rect.w, rect.h], exact ? outW : null, exact ? outH : null);
        changed = true;
        toast("Cropped", item.name, "good", "crop", 2500);
        close();
      } catch (e) { toastError(e); }
    };
    const close = () => { scrim.remove(); window.removeEventListener("keydown", key); window.removeEventListener("resize", layout); resolve(changed); };
    const key = (e) => { if (e.key === "Escape") close(); if (e.key === "Enter" && e.target.tagName !== "INPUT") save(); };

    const panel = h("div.crop-panel",
      h("div.field", h("label", "Aspect ratio"), aspectChips),
      h("div.field", h("label.switch", exactSwitch, h("span.track"), h("span.txt", "Exact output size")), exactBox),
      info,
      h("div.spacer"),
      item.backup ? btn("Restore original", { icon: "rollback", kind: "ghost", size: "sm", onclick: async () => {
        if (!(await confirmBox("Restore the original?", "Undo every crop/resize made to this image."))) return;
        try { await api.ds_restore_original(item.path); changed = true; toast("Original restored", item.name, "good", "rollback"); close(); } catch (e) { toastError(e); }
      } }) : null,
      h("div.row.nowrap", btn("Reset", { kind: "ghost", onclick: () => { rect = { x: 0, y: 0, w: natW, h: natH }; aspect = "free"; setExact(false); } }),
        h("div.spacer"), btn("Cancel", { onclick: close }), btn("Save crop", { icon: "check", kind: "primary", onclick: save })),
      h("p.tiny.faint", { style: { margin: 0 } }, "The original is kept in _originals/ the first time you edit an image."));

    const scrim = h("div.scrim", h("div.modal.crop-modal",
      h("div.m-head", h("div.chip-icon.sm", icon("crop")), h("h3", item.name), h("span.small.faint", `${natW}×${natH}`), h("div.spacer"),
        btn("", { icon: "x", kind: "ghost", size: "sm", onclick: close })),
      h("div.crop-body", stage, panel)));
    setExact(false);
    document.body.append(scrim);
    window.addEventListener("keydown", key);
    window.addEventListener("resize", layout);
    img.onload = () => {
      natW = img.naturalWidth; natH = img.naturalHeight;
      rect = { x: 0, y: 0, w: natW, h: natH };
      layout();
    };
    img.src = fileUrl(item.path, Date.now());
    requestAnimationFrame(layout);
  });
}
