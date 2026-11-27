// "Update now": update LoRA Studio itself from inside the app, then restart it.
import { api } from "./api.js";
import { h, modal, toast, toastError, clear, btn } from "./dom.js";
import { icon } from "./icons.js";
import { taskProgress, watchTask } from "./tools/common.js";

export async function updateNow(ctx, latest) {
  let info;
  try { info = await api.app_update_info(); } catch (e) { return toastError(e); }
  if (ctx.state?.current) {
    return toast("A training is running", "Update LoRA Studio after it has finished.", "", "info", 7000);
  }
  const how = info.method === "git"
    ? (info.local_changes
      ? h("div.notice.warn", icon("alert"), "This folder has local git changes. Use Pull origin in GitHub Desktop instead.")
      : h("p.small.muted", { style: { margin: 0 } }, "Updates with a git pull."))
    : h("p.small.muted", { style: { margin: 0 } }, `Your .venv, custom.css, settings, runs and presets are kept.`);
  const go = await modal(latest?.channel === "main" ? "Update to the latest changes" : latest ? `Update to LoRA Studio ${latest.tag}` : "Update LoRA Studio", h("div.stack.sm",
    latest?.channel === "main" ? h("p", { style: { margin: 0 } }, `The newest change on main: ${latest.name}`)
      : latest ? h("p", { style: { margin: 0 } }, `You have ${ctx.boot.version}; the newest is ${latest.tag}.`) : null,
    how,
    h("p.small.muted", { style: { margin: 0 } }, "LoRA Studio restarts afterwards.")),
    [{ label: "Cancel", kind: "ghost", value: false },
     ...(latest?.url ? [{ label: "What's new", value: "notes" }] : []),
     ...(info.method === "git" && info.local_changes ? [] : [{ label: "Update now", kind: "primary", value: true, icon: "download" }])]);
  if (go === "notes") return api.open_url(latest.url).catch(toastError);
  if (go !== true) return;

  // progress window
  const prog = taskProgress();
  const log = h("pre.code", { style: { maxHeight: "180px", overflow: "auto", margin: 0 } });
  const foot = h("div.row", { style: { justifyContent: "flex-end", gap: "var(--s3)" } });
  const body = h("div.stack.sm", prog.el, log, foot);
  const scrimClose = () => document.querySelectorAll(".scrim").forEach((s) => s.remove());
  modal("Updating LoRA Studio", body, []);
  let id;
  try { id = await api.app_self_update(latest?.tag || null); } catch (e) { scrimClose(); return toastError(e); }
  const t = await watchTask(id, (s) => { prog.set(s); log.textContent = (s.lines || []).slice(-40).join("\n"); log.scrollTop = 1e9; });
  log.textContent = (t?.lines || []).slice(-40).join("\n");
  if (t?.status !== "done") {
    clear(foot, btn("Close", { onclick: scrimClose }));
    return;
  }
  if (!t.result?.restart) {
    clear(foot, h("span.small.muted", { style: { marginRight: "auto" } }, "You already have the latest version."), btn("Close", { kind: "primary", onclick: scrimClose }));
    return;
  }
  clear(foot,
    h("span.small.muted", { style: { marginRight: "auto" } }, "Updated! Restart to use the new version."),
    btn("Later", { kind: "ghost", onclick: scrimClose }),
    btn("Restart now", { kind: "primary", icon: "refresh", onclick: async () => {
      try {
        await api.app_restart();
        clear(foot, h("span.small.muted", "Restarting…"));
        if (!ctx.boot.native) setTimeout(() => window.close(), 1500);   // browser mode: the new one opens its own tab
      } catch (e) { toastError(e); }
    } }));
}
