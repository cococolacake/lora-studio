// Home: what's training, what's next, recent results, sd-scripts status.
import { api } from "../api.js";
import { h, btn, card, chip, empty, statusChip, fmtAgo, fmtLoss, fmtDuration, clear, store } from "../dom.js";
import { icon } from "../icons.js";
import { liveRun } from "../liverun.js";
import { gpuCard } from "../gpu.js";
import { thumbUrl, lightbox } from "../media.js";

function greeting() {
  const hr = new Date().getHours();
  return hr < 5 ? "Up late?" : hr < 12 ? "Good morning" : hr < 18 ? "Good afternoon" : "Good evening";
}

export default {
  id: "home", label: "Home", icon: "home",

  async mount(ctx, params, root) {
    const headSlot = h("div");
    const nowSlot = h("div");
    const queueSlot = h("div");
    root.append(headSlot);

    const sd = ctx.boot.sd;
    const sdCard = card({ title: "sd-scripts", actions: btn("Manage", { size: "sm", kind: "ghost", onclick: () => ctx.go("sdscripts") }) },
      sd.valid ? h("div.stack.sm",
        h("div.row", h("div.ic", { style: { width: "42px", height: "42px", borderRadius: "var(--r-md)", background: "var(--accent-soft)", color: "var(--accent-text)", display: "grid", placeItems: "center" } }, icon("branch")),
          h("div", h("b", sd.branch || "—"), h("div.small.faint.mono", sd.commit || ""))),
        h("div.small.muted", sd.commit_subject || ""),
        h("div.row", sd.behind ? chip(`${sd.behind} update${sd.behind === 1 ? "" : "s"} available`, "accent", "download")
          : sd.behind === 0 ? chip("Up to date", "good", "check") : null,
          sd.venv ? null : chip("No venv", "bad", "alert"),
          h("span.tiny.faint", sd.commit_age ? `updated ${sd.commit_age}` : "")))
        : empty("branch", "Not connected", "Point LoRA Studio at your sd-scripts folder.", btn("Set up", { kind: "primary", onclick: () => ctx.go("sdscripts") })));

    let runs = [];
    try { runs = await api.runs(); } catch { /* shown as empty */ }
    const done = runs.filter((r) => r.status !== "queued");
    const recent = card({ title: "Recent runs", actions: btn("All runs", { size: "sm", kind: "ghost", onclick: () => ctx.go("runs") }) },
      done.length ? h("div.list", done.slice(0, 5).map((r) => h("div.list-row.click", { onclick: () => ctx.go("runs", { run: r.id }) },
        h("div.ic", icon("sparkle")),
        h("div.main-col", h("div.title", r.name), h("div.meta", `${r.family || r.script} · ${fmtAgo(r.started || r.created)}${r.duration ? " · " + fmtDuration(r.duration) : ""}`)),
        h("div.nums.small", { style: { minWidth: "64px", textAlign: "right" } }, fmtLoss(r.loss)),
        statusChip(r.status))))
        : h("p.muted.small", { style: { margin: 0 } }, "No finished trainings yet."));

    const tools = card({ title: "Shortcuts" }, h("div.stack.sm",
      [["wand", "New training", "train", {}], ["tag", "Tag & tidy a dataset", "dataset", {}], ["palette", "Change the look", "settings", { section: "appearance" }]].map(([ic, label, page, p]) =>
        h("div.list-row.click", { onclick: () => ctx.go(page, p) }, h("div.ic.accent", icon(ic)), h("div.main-col", h("div.title", label)), icon("right")))));

    // First time? A short guide that ticks itself off, then gets out of the way.
    const steps = [
      { done: !!sd.valid, title: "Connect sd-scripts", text: "Pick your sd-scripts folder or install a fresh copy.",
        action: btn("Set up", { size: "sm", onclick: () => ctx.go("sdscripts") }) },
      { done: !!store.get("dsFolder"), title: "Make a dataset", text: "Download images or pick a folder.",
        action: btn("New dataset", { size: "sm", onclick: () => ctx.go("dataset", { tool: "new" }) }) },
      { done: runs.some((r) => r.status === "done"), title: "Train your first LoRA", text: "Pick a script, check the settings, press Train now.",
        action: btn("Train", { size: "sm", onclick: () => ctx.go("train") }) },
    ];
    const guideSlot = h("div.home-guide");
    const drawGuide = () => {
      const left = steps.filter((x) => !x.done).length;
      if (!left || store.get("guideHidden")) return clear(guideSlot);
      const hide = btn("Hide", { size: "sm", kind: "ghost", onclick: () => { store.set("guideHidden", true); drawGuide(); } });
      if (left === 1) {
        const next = steps.find((x) => !x.done);
        return clear(guideSlot, card({ title: "" }, h("div.guide-line",
          h("div.guide-num", String(steps.indexOf(next) + 1)),
          h("div.main-col", h("div.title", `One step left: ${next.title.toLowerCase()}`), h("div.small.muted", next.text)),
          next.action, hide)));
      }
      clear(guideSlot, card({ title: "Getting started", actions: h("div.row",
          h("span.small.faint", `${steps.length - left} of ${steps.length} done`), hide) },
        h("div.guide", steps.map((x, i) => h("div.guide-step", { class: x.done ? "done" : "" },
          h("div.guide-num", x.done ? icon("check") : String(i + 1)),
          h("div.main-col", h("div.title", x.title), h("div.small.muted", x.text)),
          x.done ? chip("Done", "good", "check") : x.action)))));
    };
    drawGuide();
    root.append(guideSlot);

    const samplesSlot = h("div");
    const withSamples = done.find((r) => r.status === "done");
    if (withSamples) {
      api.run_detail(withSamples.id).then((r) => {
        const g = r.sample_grid;
        if (!g?.cells?.length) return;
        const cols = g.columns.slice(-4);
        const pick = cols.map((col) => [...g.cells].reverse().find((c) => c.col === col && c.row === 0)).filter(Boolean);
        if (!pick.length) return;
        const items = pick.map((c) => ({ ...c, title: `${c.col} · prompt 1`, sub: g.prompts[0] || "" }));
        clear(samplesSlot, card({ title: "Latest samples", actions: h("div.row",
            h("span.small.faint.ellipsis", { style: { maxWidth: "320px" } }, `${r.name}${g.prompts[0] ? ", " + g.prompts[0] : ""}`),
            btn("Open run", { size: "sm", kind: "ghost", onclick: () => ctx.go("runs", { run: r.id }) })) },
          h("div.sample-strip", items.map((c, i) => h("figure",
            h("button", { onclick: () => lightbox(items, i), title: c.col }, h("img", { src: thumbUrl(c.path, 320), loading: "lazy", alt: `${c.col} sample` })),
            h("figcaption", h("span", c.col)))))));
      }).catch(() => { /* no samples: the card stays hidden */ });
    }

    root.append(h("div.home-cols",
      h("div.home-col", nowSlot, recent, samplesSlot),
      h("div.home-col", sdCard, gpuCard(ctx, { compact: true }), queueSlot, tools)));

    let live = null, liveId = null, lastKey = "";
    ctx.onLeave(() => live?.stop());

    ctx.onState((st) => {
      const key = `${st.current?.id}|${st.queue.length}|${st.running}`;
      if (key !== lastKey) {
        lastKey = key;
        const n = st.queue.length;
        const banner = ctx.header({ title: st.current ? "Training in progress" : greeting(), icon: "sparkle",
          subtitle: st.current ? `Training “${st.current.name}”${n ? `, ${n} more waiting` : ""}` : n ? `${n} run${n === 1 ? "" : "s"} in the queue` : "Nothing training.",
          actions: [st.current
            ? btn("Add to queue", { icon: "layers", kind: "primary", onclick: () => ctx.go("train") })
            : btn("New training", { icon: "wand", kind: "primary", onclick: () => ctx.go("train") })] });
        banner.classList.add("hero");
        clear(headSlot, banner);
        clear(queueSlot, card({ title: "Queue", actions: btn("Open", { size: "sm", kind: "ghost", onclick: () => ctx.go("queue") }) },
          h("div.row", h("div", { style: { fontFamily: "var(--font-display)", fontSize: "34px", fontWeight: 600, lineHeight: 1 } }, String(n)),
            h("div.small.muted", n === 1 ? "run waiting" : "runs waiting", h("br"), st.running ? "Queue is on" : "Queue is paused")),
          n ? h("div.list", { style: { marginTop: "var(--s3)" } }, st.queue.slice(0, 3).map((q) => h("div.list-row", h("div.main-col", h("div.title.small", q.name), h("div.meta", q.script))))) : null));
      }
      const cur = st.current;
      if (!cur) {
        if (liveId !== null || !nowSlot.childNodes.length) {
          live?.stop(); live = null; liveId = null;
          clear(nowSlot, card({ title: "" }, h("div.guide-line",
            h("div.list-row", { style: { padding: 0, border: 0 } }, h("div.ic", icon("sparkle"))),
            h("div.main-col", h("div.title", "Nothing is training")))));
        }
        return;
      }
      if (liveId !== cur.id) {
        live?.stop();
        live = liveRun(cur.id, { chartHeight: 170 });
        liveId = cur.id;
        clear(nowSlot, card({ title: "Now training", actions: btn("Open", { size: "sm", kind: "ghost", onclick: () => ctx.go("queue") }) },
          h("div.row", { style: { marginBottom: "var(--s3)" } }, h("b", { style: { fontSize: "16px" } }, cur.name), chip("Training", "accent live", "dot"), h("div.spacer"), h("span.small.faint", cur.script)),
          live.bar, h("div", { style: { margin: "var(--s4) 0" } }, live.stats), live.chart));
      }
      live.update(cur.progress);
    });
  },
};
