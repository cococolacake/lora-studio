// Runs: every training you've done, with its loss curve, config, outputs, and resume points.
import { api } from "../api.js";
import { h, btn, card, empty, stat, statusChip, fmtAgo, fmtDuration, fmtLoss, fmtSize, toast, toastError, confirmBox, clear, STATUS } from "../dom.js";
import { icon } from "../icons.js";
import { liveRun } from "../liverun.js";
import { seg } from "../components.js";
import { samplesCard, metaModal, swarmCard, starButton } from "../runextras.js";

const FILTERS = [
  ["all", "All", "list"],
  ["running", "Training", "zap"],
  ["done", "Done", "circleCheck"],
  ["failed", "Failed", "circleX"],
  ["stopped", "Stopped", "stop"],
  ["queued", "Queued", "clock"],
];
const match = (f, r) => f === "all" || r.status === f || (f === "stopped" && ["stopped", "interrupted", "cancelled"].includes(r.status));

export default {
  id: "runs", label: "Runs", icon: "history",

  async mount(ctx, params, root) {
    let runs = [];
    let filter = params.filter || "all";
    try { runs = await api.runs(); } catch (e) { toastError(e); }

    const side = () => ctx.side(h("h2", "Runs"),
      FILTERS.map(([id, label, ic]) => h("button.side-item", { class: !params.run && filter === id ? "active" : "",
        onclick: () => { filter = id; ctx.go("runs", { filter: id }); } },
      icon(ic), h("span", label), h("span.count", String(runs.filter((r) => match(id, r)).length)))),
      h("div.sep"),
      h("div.group-label", "By model"),
      Object.entries(runs.reduce((a, r) => ((a[r.family || "Other"] = (a[r.family || "Other"] || 0) + 1), a), {})).map(([fam, n]) =>
        h("div.side-item.muted", icon("box"), h("span", fam), h("span.count", String(n)))));
    side();

    if (params.run) return detail(ctx, root, params.run);

    const list = runs.filter((r) => match(filter, r));
    root.append(ctx.header({ title: "Run history", subtitle: `${runs.length} run${runs.length === 1 ? "" : "s"} so far`, icon: "history" }));
    if (!list.length) {
      root.append(card(null, empty("history", filter === "all" ? "No runs yet" : "Nothing here", filter === "all" ? "Every training you start is saved here with its settings, loss curve and log." : "No runs match this filter.",
        btn("New training", { icon: "wand", kind: "primary", onclick: () => ctx.go("train") }))));
      return;
    }
    root.append(card(null, h("div.list", list.map((r) => {
      const tone = (STATUS[r.status] || [])[1] || "";
      return h("div.list-row.click", { onclick: () => ctx.go("runs", { run: r.id }) },
        h("div.ic" + (tone.includes("accent") ? ".accent" : ""), icon(r.family === "Anima" || r.script?.includes("network") ? "sparkle" : "box")),
        h("div.main-col", h("div.title", r.name), h("div.meta", [r.script, r.started ? fmtAgo(r.started) : fmtAgo(r.created), r.duration ? fmtDuration(r.duration) : null].filter(Boolean).join(" · "))),
        h("div", { style: { textAlign: "right", minWidth: "90px" } }, h("div.nums", { style: { fontWeight: 600 } }, fmtLoss(r.loss)), h("div.tiny.faint", "final loss")),
        h("div", { style: { width: "120px", display: "flex", justifyContent: "flex-end" } }, statusChip(r.status)),
        icon("right"));
    }))));
  },
};

async function detail(ctx, root, runId) {
  let r;
  try { r = await api.run_detail(runId); } catch (e) { toastError(e); return; }
  if (!r) { root.append(card(null, empty("alert", "Run not found", "It may have been deleted.", btn("Back", { onclick: () => ctx.go("runs") })))); return; }
  const s = r.summary;
  const isLive = r.status === "running";

  root.append(ctx.header({ title: r.name, subtitle: `${r.script} · ${new Date((r.started || r.created) * 1000).toLocaleString()}`, icon: "history",
    actions: [
      btn("", { icon: "left", title: "Back to runs", onclick: () => ctx.go("runs") }),
      btn("Edit & train", { icon: "wand", onclick: async () => ctx.go("train", { job: await api.run_job(runId) }) }),
      btn("Run again", { icon: "refresh", kind: "primary", onclick: async () => {
        try { await api.run_rerun(runId, false); toast("Queued again", r.name, "good", "layers"); ctx.go("queue"); } catch (e) { toastError(e); }
      } }),
    ] }));

  const live = liveRun(runId, { live: isLive, chartHeight: 260 });
  ctx.onLeave(() => live.stop());
  if (isLive) ctx.onState((st) => { if (st.current?.id === runId) live.update(st.current.progress); });
  else live.update(r.progress);

  const tiles = h("div.grid.c5",
    h("div.stat", h("div.k", "Status"), h("div.v", { style: { fontSize: "15px", paddingTop: "6px" } }, statusChip(r.status))),
    stat("Duration", fmtDuration(s.duration)),
    stat("Final loss", fmtLoss(s.loss)),
    stat("Steps", s.total ? `${s.step}` : "—", s.total ? `/ ${s.total}` : ""),
    stat("Epochs", s.epochs ? `${s.epoch}` : "—", s.epochs ? `/ ${s.epochs}` : ""));

  const outputs = card({ title: "Saved LoRAs", actions: r.config?.output_dir ? btn("Open folder", { icon: "folder", size: "sm", kind: "ghost", onclick: () => api.open_folder(r.config.output_dir) }) : null },
    r.outputs.length ? h("div.list", r.outputs.map((o) => h("div.list-row", h("div.ic.accent", icon("sparkle")),
      h("div.main-col", h("div.title.mono", { style: { fontSize: "13px" } }, o.name), h("div.meta", fmtSize(o.size))),
      starButton(r, o, () => ctx.go("runs", { run: runId })),
      btn("Info", { icon: "tag", size: "sm", kind: "ghost", title: "View & edit the metadata saved in this file", onclick: () => metaModal(o.path, r) }))))
      : h("p.muted.small", { style: { margin: 0 } }, "No .safetensors files found in the output folder yet."));

  const canResume = ["stopped", "failed", "interrupted", "done"].includes(r.status);
  const resume = card({ title: "Resume" },
    r.states.length ? h("div.list", r.states.slice(0, 6).map((st, i) => h("div.list-row", h("div.ic", icon("save")),
      h("div.main-col", h("div.title.mono", { style: { fontSize: "13px" } }, st.name), h("div.meta", fmtAgo(st.mtime))),
      btn(i === 0 ? "Resume" : "", { icon: "play", size: "sm", kind: i === 0 ? "primary" : "", disabled: !canResume, title: "Resume from this state",
        onclick: async () => {
          try { await api.run_resume(runId, st.path, true); toast("Resuming", st.name, "good", "play"); ctx.go("queue"); } catch (e) { toastError(e); }
        } }))))
      : h("div.notice", icon("info"), h("div", r.config?.save_state ? "No saved states yet. They appear after each saved epoch." : "This run didn't save training states. Turn on “Save state” on the Train page to be able to resume runs.")));

  let tab = "log";
  const code = h("div");
  const showTab = () => clear(code, tab === "log" ? live.log : h("pre.code", tab === "training" ? r.training_toml : r.dataset_toml));
  showTab();
  const files = card({ title: "Details", actions: btn("Run folder", { icon: "folder", size: "sm", kind: "ghost", onclick: () => api.open_folder(r.folder) }) },
    h("div", { style: { marginBottom: "12px" } }, seg([["log", "Log", "terminal"], ["training", "training.toml", "file"], ["dataset", "dataset.toml", "image"]], tab, (v) => { tab = v; showTab(); })),
    code,
    h("p.tiny.faint", { style: { marginBottom: 0 } }, `sd-scripts ${r.sd_branch || ""} @ ${r.sd_commit || "?"}${r.extra_args ? " · extra: " + r.extra_args : ""}${r.resume_from ? " · resumed from " + r.resume_from : ""}`));

  const danger = h("div.row", h("div.spacer"), btn("Delete run", { icon: "trash", kind: "ghost danger", size: "sm", disabled: isLive, onclick: async () => {
    if (!(await confirmBox("Delete this run?", "Its log, loss history and saved config are removed from LoRA Studio. Your trained .safetensors files are not touched.", "Delete", true))) return;
    try { await api.run_delete(runId); ctx.go("runs"); } catch (e) { toastError(e); }
  } }));

  root.append(h("div.stack", tiles,
    card({ title: "Loss" }, isLive ? h("div", { style: { marginBottom: "14px" } }, live.bar) : null, live.chart),
    r.best ? h("div.notice.good", icon("star"), h("div", { style: { flex: 1 } }, h("b", `Best epoch: ${r.best.epoch ?? "final"}`), ` saved as ${r.best.path.split("/").pop()}. Copy it to SwarmUI or ComfyUI from the card below.`)) : null,
    r.sample_grid?.cells?.length ? samplesCard(r, () => ctx.go("runs", { run: runId })) : null,
    h("div.grid.c2", outputs, resume),
    swarmCard(ctx, r),
    files, danger));
}
