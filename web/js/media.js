// Image URLs for files on disk (served by the local media server), plus a lightbox.
import { h, btn } from "./dom.js";

let MEDIA = { base: "", token: "" };
export const setMedia = (m) => { MEDIA = m || MEDIA; };

const q = (p) => encodeURIComponent(p);
export const thumbUrl = (path, size = 256, bust = "") => `${MEDIA.base}/media/thumb?p=${q(path)}&s=${size}&k=${MEDIA.token}${bust ? "&v=" + bust : ""}`;
export const fileUrl = (path, bust = "") => `${MEDIA.base}/media/file?p=${q(path)}&k=${MEDIA.token}${bust ? "&v=" + bust : ""}`;

/** Full-screen viewer. items: [{path, title, sub}], start index. */
export function lightbox(items, start = 0) {
  let i = start;
  const img = h("img");
  const title = h("b");
  const sub = h("div.small.muted");
  const count = h("span.small.faint");
  const show = () => {
    const it = items[i];
    img.src = fileUrl(it.path);
    title.textContent = it.title || it.path.split("/").pop();
    sub.textContent = it.sub || "";
    count.textContent = `${i + 1} / ${items.length}`;
  };
  const go = (d) => { i = (i + d + items.length) % items.length; show(); };
  const close = () => { el.remove(); window.removeEventListener("keydown", key); };
  const key = (e) => {
    if (e.key === "Escape") close();
    else if (e.key === "ArrowRight") go(1);
    else if (e.key === "ArrowLeft") go(-1);
  };
  const el = h("div.lightbox", { onmousedown: (e) => { if (e.target === el || e.target.classList.contains("lb-stage")) close(); } },
    h("div.lb-stage", img),
    items.length > 1 ? btn("", { icon: "left", kind: "lb-nav lb-prev", onclick: () => go(-1) }) : null,
    items.length > 1 ? btn("", { icon: "right", kind: "lb-nav lb-next", onclick: () => go(1) }) : null,
    h("div.lb-bar", h("div", title, sub), h("div.spacer"), count, btn("", { icon: "x", kind: "ghost", onclick: close })));
  window.addEventListener("keydown", key);
  document.body.append(el);
  show();
  return el;
}

export const bucketFor = (w, h, res = 1024, step = 64) => {
  // quick estimate: same area as res², aspect closest, rounded to step
  const ar = w / h;
  const area = res * res;
  const bw = Math.round(Math.sqrt(area * ar) / step) * step;
  const bh = Math.round(Math.sqrt(area / ar) / step) * step;
  return `${bw}×${bh}`;
};

