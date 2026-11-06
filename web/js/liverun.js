// Live view of one run: stat tiles, progress, loss chart and log. Used by Queue and Runs.
import { api } from "./api.js";
import { h, stat, fmtDuration, fmtLoss, clear } from "./dom.js";
import { lossChart } from "./chart.js";
import { logView } from "./components.js";

export function progressStats(p) {
  p = p || {};
  const speed = p.speed == null ? "—" : `${p.speed}`;
  return [
    stat("Step", p.total ? `${p.step}` : "—", p.total ? `/ ${p.total}` : ""),
    stat("Epoch", p.epochs ? `${p.epoch}` : "—", p.epochs ? `/ ${p.epochs}` : ""),
    stat("Loss", fmtLoss(p.loss)),
    stat("Speed", speed, p.speed == null ? "" : p.speed_unit),
    stat("Time left", p.eta == null ? "—" : fmtDuration(p.eta)),
  ];
}

export function liveRun(runId, { chartHeight = 240, logHeight = 300, live = true } = {}) {
  const stats = h("div.grid.c5");
  const bar = h("div.progress", h("i"));
  const chart = lossChart({ height: chartHeight });
  const log = logView(logHeight);
  let logSince = 0, ptsSince = 0, timer = null, alive = true;

  async function tick() {
    if (!alive) return;
    try {
      const [m, l] = await Promise.all([api.run_metrics(runId, ptsSince), api.run_log(runId, logSince)]);
      if (ptsSince === 0) chart.set(m.points); else chart.add(m.points);
      ptsSince = m.total;
      log.append(l.lines);
      logSince = l.total;
      log.progress(l.progress_line);
      if (live && (m.live || l.live)) timer = setTimeout(tick, 1000);
    } catch (e) {
      console.warn(e);
      if (live) timer = setTimeout(tick, 3000);
    }
  }

  function update(p) {
    clear(stats, progressStats(p));
    const pct = p?.total ? (p.step / p.total) * 100 : 0;
    bar.firstChild.style.width = `${pct}%`;
    bar.classList.toggle("idle", !live);
  }

  update(null);
  tick();
  return {
    stats, bar, chart: chart.el, log: log.el, update,
    stop() { alive = false; clearTimeout(timer); },
  };
}
