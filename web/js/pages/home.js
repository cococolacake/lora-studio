// Home: what's training, what's next, recent results, sd-scripts status.
import { api } from "../api.js";
import { h, btn, card, chip, empty, statusChip, fmtAgo, fmtLoss, fmtDuration, clear, store } from "../dom.js";
import { icon } from "../icons.js";
import { liveRun } from "../liverun.js";
import { gpuCard } from "../gpu.js";

function greeting() {
  const hr = new Date().getHours();
  return hr < 5 ? "Up late?" : hr < 12 ? "Good morning" : hr < 18 ? "Good afternoon" : "Good evening";
}

export default {
  id: "home", label: "Home", icon: "home",

  async mount(ctx, params, root) {
    const headSlot = h("div");
    const nowSlot = h("div.span2");
    const queueSlot = h("div");
    root.append(headSlot);

    const sd = ctx.boot.sd;
    const sdCard = card({ title: "sd-scripts", actions: btn("Manage", { size: "sm", kind: "ghost", onclick: () => ctx.go("sdscripts") }) },
      sd.valid ? h("div.stack.sm",
        h("div.row", h("div.ic", { style: { width: "42px", height: "42px", borderRadius: "13px", background: "var(--accent-soft)", color: "var(--accent-text)", display: "grid", placeItems: "center" } }, icon("branch")),
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
        : h("p.muted.small", { style: { margin: 0 } }, "Finished trainings show up here with their final loss."));
    recent.classList.add("span2");

    const tools = card({ title: "Shortcuts" }, h("div.stack.sm",
      [["wand", "New training", "train", {}], ["tag", "Tag & tidy a dataset", "dataset", {}], ["palette", "Change the look", "settings", { section: "appearance" }]].map(([ic, label, page, p]) =>
        h("div.list-row.click", { onclick: () => ctx.go(page, p) }, h("div.ic.accent", icon(ic)), h("div.main-col", h("div.title", label)), icon("right")))));

    // First time? A short guide that ticks itself off, then gets out of the way.
    const steps = [
      { done: !!sd.valid, title: "Connect sd-scripts", text: "Point LoRA Studio at your kohya-ss/sd-scripts folder, or let it install a fresh copy.",
        action: btn("Set up", { size: "sm", onclick: () => ctx.go("sdscripts") }) },
      { done: !!store.get("dsFolder"), title: "Make a dataset", text: "Download images with gallery-dl or pick a folder; LoRA Studio captions, numbers and checks them.",
        action: btn("New dataset", { size: "sm", onclick: () => ctx.go("dataset", { tool: "new" }) }) },
      { done: runs.some((r) => r.status === "done"), title: "Train your first LoRA", text: "Pick a training script, check the settings, and press Train now. Samples and the loss graph show up live.",
        action: btn("Train", { size: "sm", onclick: () => ctx.go("train") }) },
    ];
    const guideSlot = h("div");
    const drawGuide = () => {
      const left = steps.filter((x) => !x.done).length;
      if (!left || store.get("guideHidden")) return clear(guideSlot);
      clear(guideSlot, card({ title: "Getting started", actions: h("div.row", { style: { gap: "10px" } },
          h("span.small.faint", `${steps.length - left} of ${steps.length} done`),
          btn("Hide", { size: "sm", kind: "ghost", onclick: () => { store.set("guideHidden", true); drawGuide(); } })) },
        h("div.guide", steps.map((x, i) => h("div.guide-step", { class: x.done ? "done" : "" },
          h("div.guide-num", x.done ? icon("check") : String(i + 1)),
          h("div.main-col", h("div.title", x.title), h("div.small.muted", x.text)),
          x.done ? chip("Done", "good", "check") : x.action)))));
    };
    drawGuide();
    root.append(guideSlot);

    root.append(h("div.grid.c3", nowSlot, h("div.stack", sdCard, gpuCard(ctx, { compact: true })), recent, h("div.stack", queueSlot, tools)));

    let live = null, liveId = null, lastKey = "";
    ctx.onLeave(() => live?.stop());

    ctx.onState((st) => {
      const key = `${st.current?.id}|${st.queue.length}|${st.running}`;
      if (key !== lastKey) {
        lastKey = key;
        const n = st.queue.length;
        clear(headSlot, ctx.header({ title: greeting(), icon: "sparkle",
          subtitle: st.current ? `Training “${st.current.name}”${n ? `, ${n} more waiting` : ""}.` : n ? `${n} run${n === 1 ? "" : "s"} waiting in the queue.` : "Nothing training right now. Ready when you are.",
          actions: [btn("New training", { icon: "wand", kind: "primary", onclick: () => ctx.go("train") })] }));
        clear(queueSlot, card({ title: "Queue", actions: btn("Open", { size: "sm", kind: "ghost", onclick: () => ctx.go("queue") }) },
          h("div.row", h("div", { style: { fontFamily: "var(--font-display)", fontSize: "34px", fontWeight: 600, lineHeight: 1 } }, String(n)),
            h("div.small.muted", n === 1 ? "run waiting" : "runs waiting", h("br"), st.running ? "Queue is on" : "Queue is paused")),
          n ? h("div.list", { style: { marginTop: "10px" } }, st.queue.slice(0, 3).map((q) => h("div.list-row", h("div.main-col", h("div.title.small", q.name), h("div.meta", q.script))))) : null));
      }
      const cur = st.current;
      if (!cur) {
        if (liveId !== null || !nowSlot.childNodes.length) {
          live?.stop(); live = null; liveId = null;
          clear(nowSlot, card({ title: "Now training" }, empty("sparkle", "Nothing is training", "Pick a script, point it at your images, and press Train now.",
            btn("Start a training", { icon: "wand", kind: "primary", onclick: () => ctx.go("train") }))));
        }
        return;
      }
      if (liveId !== cur.id) {
        live?.stop();
        live = liveRun(cur.id, { chartHeight: 170 });
        liveId = cur.id;
        clear(nowSlot, card({ title: "Now training", actions: btn("Open", { size: "sm", kind: "ghost", onclick: () => ctx.go("queue") }) },
          h("div.row", { style: { marginBottom: "12px" } }, h("b", { style: { fontSize: "16px" } }, cur.name), chip("Training", "accent live", "dot"), h("div.spacer"), h("span.small.faint", cur.script)),
          live.bar, h("div", { style: { margin: "14px 0" } }, live.stats), live.chart));
      }
      live.update(cur.progress);
    });
  },
};
