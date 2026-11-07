// Queue: what's training now (live loss + log) and what's next.
import { api } from "../api.js";
import { h, btn, card, chip, empty, fmtAgo, fmtDuration, toast, toastError, confirmBox, clear } from "../dom.js";
import { seg } from "../components.js";
import { icon } from "../icons.js";
import { liveRun } from "../liverun.js";
import { gpuCard } from "../gpu.js";

export default {
  id: "queue", label: "Queue", icon: "layers",

  mount(ctx, params, root) {
    const headSlot = h("div");
    const currentSlot = h("div");
    const nextSlot = h("div");
    const powerSlot = h("div");
    root.append(headSlot, h("div.stack", currentSlot, gpuCard(ctx), powerSlot, nextSlot));

    // "When the queue is done": a one-time sleep / shut down after the last training.
    let lastPower = "";
    function power(st) {
      const pw = st.power || { action: "none" };
      const key = pw.action + "|" + (pw.pending || "");
      if (key === lastPower) return;
      lastPower = key;
      const set = async (v) => {
        try {
          await api.power_set(v);
          if (v !== "none") toast(v === "sleep" ? "Sleep when done" : "Shut down when done",
            "After the last training there's a 1-minute countdown you can cancel. This is a one-time setting.", "good", "moon");
          refresh();
        } catch (e) { toastError(e); }
      };
      clear(powerSlot, card({ title: "When the queue is done" },
        h("div.row", { style: { gap: "14px", flexWrap: "wrap" } },
          seg([["none", "Do nothing", "check"], ["sleep", "Sleep", "moon"], ["shutdown", "Shut down", "power"]], pw.action, set),
          h("div.small.muted", { style: { flex: 1, minWidth: "220px" } }, pw.action === "none"
            ? "Handy for overnight batches: put the PC to sleep or shut it down after the last training."
            : `After the last training finishes there's a 1-minute countdown you can cancel, then the PC will ${pw.action === "sleep" ? "go to sleep" : "shut down"}. Pressing Stop yourself won't trigger it. Resets to “Do nothing” afterwards.`))));
    }

    let live = null, liveId = null, lastQueueKey = "", lastRunning = null;
    ctx.onLeave(() => live?.stop());

    function header(st) {
      const running = st.running;
      const n = st.queue.length;
      const total = st.queue.reduce((t, q) => t + (q.estimate || 0), 0);
      const tail = total ? ` · about ${fmtDuration(total)} queued` : "";
      const sub = st.current ? `Training “${st.current.name}”${n ? ` · ${n} waiting${tail}` : ""}`
        : running ? (n ? `${n} waiting` : "Queue is on. Anything you add starts right away.") : n ? `Paused · ${n} waiting` : "Nothing queued";
      clear(headSlot, ctx.header({ title: "Queue", subtitle: sub, icon: "layers", actions: [
        running ? btn("Pause queue", { icon: "pause", onclick: () => api.queue_set_running(false).then(refresh) })
          : btn("Start queue", { icon: "play", kind: "primary", disabled: !n && !st.current, onclick: () => api.queue_set_running(true).then(refresh) }),
      ] }));
    }

    function current(st) {
      const cur = st.current;
      if (!cur) {
        live?.stop(); live = null; liveId = null;
        clear(currentSlot, card(null, empty("sparkle", "Nothing is training", st.queue.length
          ? (st.running ? "Starting the next run…" : "Your queue is paused. Start it when you're ready.")
          : "Set up a run on the Train page and press Train now, or add a few to the queue for an overnight batch.",
        btn("New training", { icon: "wand", kind: "primary", onclick: () => ctx.go("train") }),
        btn("Run history", { icon: "history", onclick: () => ctx.go("runs") }))));
        return;
      }
      if (liveId !== cur.id) {
        live?.stop();
        live = liveRun(cur.id);
        liveId = cur.id;
        clear(currentSlot, card(null,
          h("div.row", { style: { marginBottom: "16px" } },
            h("div", h("div.row", h("h3", { style: { margin: 0, fontSize: "18px", fontFamily: "var(--font-display)" } }, cur.name), chip("Training", "accent live", "dot")),
              h("div.small.faint", { style: { marginTop: "2px" } }, `${cur.script}`)),
            h("div.spacer"),
            btn("Details", { icon: "chart", kind: "ghost", onclick: () => ctx.go("runs", { run: cur.id }) }),
            btn("Stop", { icon: "stop", kind: "danger", onclick: async () => {
              if (await confirmBox("Stop this training?", "The process is stopped right away and the queue pauses. If save_state is on, you can resume from the last saved epoch on the Runs page.", "Stop", true)) {
                api.stop_current().catch(toastError);
              }
            } })),
          live.stats, h("div", { style: { margin: "16px 0 6px" } }, live.bar),
          h("div.card-head", { style: { marginTop: "18px" } }, h("h3.card-title", "Loss")), live.chart,
          h("div.card-head", { style: { marginTop: "18px" } }, h("h3.card-title", "Log")), live.log));
      }
      live.update(cur.progress);
    }

    function upNext(st) {
      const key = JSON.stringify(st.queue.map((q) => q.id));
      if (key === lastQueueKey) return;
      lastQueueKey = key;
      clear(nextSlot, card({ title: "Up next", actions: h("span.chip", String(st.queue.length)) },
        st.queue.length ? h("div.list", st.queue.map((q, i) =>
          h("div.list-row",
            h("div.ic.accent", h("b", { style: { fontSize: "14px" } }, String(i + 1))),
            h("div.main-col", h("div.title", q.name), h("div.meta", `${q.script} · added ${fmtAgo(q.created)}`)),
            q.estimate ? h("span.chip", { title: "Estimated from your past runs" }, icon("clock"), `~${fmtDuration(q.estimate)}`) : null,
            btn("", { icon: "up", kind: "ghost", size: "sm", title: "Move up", disabled: i === 0, onclick: () => api.queue_move(q.id, -1).then(apply) }),
            btn("", { icon: "down", kind: "ghost", size: "sm", title: "Move down", disabled: i === st.queue.length - 1, onclick: () => api.queue_move(q.id, 1).then(apply) }),
            btn("", { icon: "trash", kind: "ghost", size: "sm", title: "Remove", onclick: () => api.queue_remove(q.id).then(apply) }))))
          : h("p.muted.small", { style: { margin: 0 } }, "Queued runs wait here and start one after another.")));
    }

    function apply(st) {
      ctx.state = st;
      if (lastRunning !== `${st.running}|${st.current?.id}|${st.queue.length}`) {
        lastRunning = `${st.running}|${st.current?.id}|${st.queue.length}`;
        header(st);
      }
      current(st);
      power(st);
      upNext(st);
    }
    const refresh = () => api.state().then(apply).catch(toastError);
    ctx.onState(apply);
  },
};
