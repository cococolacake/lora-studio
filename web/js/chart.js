// Loss chart: faint raw line + smoothed line + soft area, epoch markers, hover readout.
import { h } from "./dom.js";

const NS = "http://www.w3.org/2000/svg";
const s = (tag, attrs = {}) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };

export function lossChart({ height = 220, smoothing = 0.9 } = {}) {
  const root = h("div.chart", { style: { height: height + "px" } });
  const tip = h("div.tooltip.hidden");
  const emptyMsg = h("div.empty-chart", "Loss will appear here once training starts");
  root.append(tip, emptyMsg);
  let points = [];
  let svg = null;
  let geo = null;

  function ema(arr) {
    const out = [];
    let v = null;
    for (const p of arr) { v = v == null ? p.loss : v * smoothing + p.loss * (1 - smoothing); out.push(v); }
    return out;
  }

  function draw() {
    if (svg) svg.remove();
    emptyMsg.classList.toggle("hidden", points.length > 1);
    if (points.length < 2) return;
    const W = root.clientWidth || 600, H = height;
    const pad = { l: 46, r: 10, t: 10, b: 24 };
    const sm = ema(points);
    const xs = points.map((p) => p.step);
    const minX = xs[0], maxX = xs[xs.length - 1] || 1;
    // y range from smoothed values with a little headroom; raw spikes may clip
    let lo = Math.min(...sm), hi = Math.max(...sm);
    const rawLo = Math.min(...points.map((p) => p.loss)), rawHi = Math.max(...points.map((p) => p.loss));
    lo = Math.min(lo, (lo + rawLo) / 2); hi = Math.max(hi, (hi + rawHi) / 2);
    const span = hi - lo || hi || 1;
    lo -= span * 0.08; hi += span * 0.08;
    const X = (v) => pad.l + ((v - minX) / (maxX - minX || 1)) * (W - pad.l - pad.r);
    const Y = (v) => pad.t + (1 - (v - lo) / (hi - lo)) * (H - pad.t - pad.b);
    geo = { X, Y, pad, W, H, sm };

    svg = s("svg", { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none" });
    const defs = s("defs");
    const grad = s("linearGradient", { id: "chartfill", x1: 0, y1: 0, x2: 0, y2: 1 });
    grad.append(s("stop", { offset: "0%", "stop-color": "var(--accent)", "stop-opacity": ".22" }),
      s("stop", { offset: "100%", "stop-color": "var(--accent)", "stop-opacity": "0" }));
    defs.append(grad);
    svg.append(defs);

    for (let i = 0; i <= 4; i++) {
      const v = lo + ((hi - lo) * i) / 4;
      const y = Y(v);
      svg.append(s("line", { class: "axis", x1: pad.l, x2: W - pad.r, y1: y, y2: y }));
      const t = s("text", { class: "lbl", x: pad.l - 8, y: y + 4, "text-anchor": "end" });
      t.textContent = v.toFixed(v < 0.1 ? 4 : 3);
      svg.append(t);
    }
    // epoch boundaries
    let lastEp = points[0].epoch;
    for (const p of points) {
      if (p.epoch !== lastEp && p.epoch) {
        const x = X(p.step);
        svg.append(s("line", { class: "epoch", x1: x, x2: x, y1: pad.t, y2: H - pad.b }));
        const nearEnd = x > W - pad.r - 40;
        const t = s("text", { class: "lbl", x: nearEnd ? x - 4 : x + 4, y: pad.t + 10, "text-anchor": nearEnd ? "end" : "start" });
        t.textContent = `ep ${p.epoch}`;
        svg.append(t);
        lastEp = p.epoch;
      }
    }
    for (const v of [minX, Math.round((minX + maxX) / 2), maxX]) {
      const t = s("text", { class: "lbl", x: X(v), y: H - 6, "text-anchor": v === minX ? "start" : v === maxX ? "end" : "middle" });
      t.textContent = `step ${v}`;
      svg.append(t);
    }
    const raw = points.map((p, i) => `${i ? "L" : "M"}${X(p.step).toFixed(1)},${Y(p.loss).toFixed(1)}`).join("");
    const smooth = points.map((p, i) => `${i ? "L" : "M"}${X(p.step).toFixed(1)},${Y(sm[i]).toFixed(1)}`).join("");
    svg.append(s("path", { class: "area", d: `${smooth}L${X(maxX)},${H - pad.b}L${X(minX)},${H - pad.b}Z` }));
    svg.append(s("path", { class: "raw", d: raw }));
    svg.append(s("path", { class: "smooth", d: smooth }));
    const tl = s("line", { class: "tipline", y1: pad.t, y2: H - pad.b, visibility: "hidden" });
    const td = s("circle", { class: "tipdot", r: 5, visibility: "hidden" });
    svg.append(tl, td);
    svg.addEventListener("mousemove", (e) => {
      const r = svg.getBoundingClientRect();
      const mx = ((e.clientX - r.left) / r.width) * W;
      let best = 0, bd = Infinity;
      points.forEach((p, i) => { const d = Math.abs(X(p.step) - mx); if (d < bd) { bd = d; best = i; } });
      const p = points[best];
      const x = X(p.step), y = Y(sm[best]);
      tl.setAttribute("x1", x); tl.setAttribute("x2", x); tl.setAttribute("visibility", "visible");
      td.setAttribute("cx", x); td.setAttribute("cy", y); td.setAttribute("visibility", "visible");
      tip.classList.remove("hidden");
      tip.style.left = (x / W) * r.width + "px";
      tip.style.top = (y / H) * r.height + "px";
      tip.innerHTML = `<b>${sm[best].toFixed(4)}</b> <span class="faint">avg · step ${p.step}${p.epoch ? " · ep " + p.epoch : ""}</span>`;
    });
    svg.addEventListener("mouseleave", () => { tip.classList.add("hidden"); tl.setAttribute("visibility", "hidden"); td.setAttribute("visibility", "hidden"); });
    root.insertBefore(svg, tip);
  }

  const ro = new ResizeObserver(() => draw());
  ro.observe(root);

  return {
    el: root,
    set(pts) { points = pts.slice(); draw(); },
    add(pts) { if (pts.length) { points.push(...pts); draw(); } },
    get count() { return points.length; },
  };
}
