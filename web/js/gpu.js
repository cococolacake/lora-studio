// GPU monitor card (nvidia-smi): VRAM, load, temperature, power, plus a small VRAM history line.
import { api } from "./api.js";
import { h, card, clear } from "./dom.js";

export function gpuCard(ctx, { compact = false } = {}) {
  const body = h("div", h("div.small.faint", "Reading GPU…"));
  const el = card({ title: "GPU" }, body);
  const history = [];
  let timer = null, alive = true;

  const bar = (pct, warn) => h("div.progress.idle" + (warn ? ".warn" : ""), { style: { height: "8px" } }, h("i", { style: { width: `${Math.min(100, pct || 0)}%`, animation: "none" } }));
  const spark = (vals, max) => {
    if (vals.length < 2) return h("div");
    const W = 300, H = 40;
    const pts = vals.map((v, i) => `${(i / (vals.length - 1)) * W},${H - (v / max) * H}`).join(" ");
    const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", `0 0 ${W} ${H}`); s.setAttribute("preserveAspectRatio", "none");
    s.classList.add("gpu-spark");
    s.innerHTML = `<polyline points="0,${H} ${pts} ${W},${H}" fill="var(--accent-soft)" stroke="none"/><polyline points="${pts}" fill="none" stroke="var(--accent)" stroke-width="2" vector-effect="non-scaling-stroke"/>`;
    return s;
  };

  async function tick() {
    if (!alive) return;
    let st;
    try { st = await api.gpu_stats(); } catch { st = { available: false, reason: "Couldn't read GPU stats." }; }
    if (!st.available) {
      clear(body, h("p.small.muted", { style: { margin: 0 } }, st.reason || "No NVIDIA GPU found."));
      return;   // don't keep polling a machine without nvidia-smi
    }
    const g = st.gpus[0];
    const memPct = g.mem_total ? (g.mem_used / g.mem_total) * 100 : 0;
    history.push(g.mem_used); if (history.length > 90) history.shift();
    const gb = (mb) => (mb / 1024).toFixed(1);
    const tile = (k, v, sub, pct, warn) => h("div.stat", h("div.k", k), h("div.v", { style: { fontSize: "19px" } }, v, sub ? h("small", " " + sub) : null), pct != null ? h("div", { style: { marginTop: "8px" } }, bar(pct, warn)) : null);
    clear(body,
      h("div.row", { style: { marginBottom: "10px" } }, h("b.small", g.name), st.gpus.length > 1 ? h("span.small.faint", `+${st.gpus.length - 1} more`) : null),
      h(compact ? "div.grid.c2" : "div.grid.c4",
        tile("VRAM", gb(g.mem_used), `/ ${gb(g.mem_total)} GB`, memPct, memPct > 95),
        tile("Load", g.util != null ? `${g.util}%` : "—", "", g.util),
        compact ? null : tile("Temperature", g.temp != null ? `${g.temp}°` : "—", "C", g.temp, g.temp > 83),
        compact ? null : tile("Power", g.power != null ? `${Math.round(g.power)}` : "—", g.power_limit ? `/ ${Math.round(g.power_limit)} W` : "W", g.power_limit ? (g.power / g.power_limit) * 100 : null)),
      compact ? null : h("div", { style: { marginTop: "12px" } }, h("div.tiny.faint", { style: { marginBottom: "4px" } }, "VRAM over the last few minutes"), spark(history, g.mem_total || 1)),
      memPct > 97 ? h("div.notice.warn", { style: { marginTop: "12px" } }, "VRAM is almost full. If training crashes with “out of memory”, try a smaller batch, gradient checkpointing, or block swap.") : null);
    timer = setTimeout(tick, 2000);
  }
  tick();
  ctx.onLeave(() => { alive = false; clearTimeout(timer); });
  return el;
}
