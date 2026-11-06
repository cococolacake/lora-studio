// sd-scripts: connect an existing checkout or install one; see updates, update, switch branch, roll back.
import { api } from "../api.js";
import { h, btn, card, chip, kv, toast, toastError, confirmBox, clear } from "../dom.js";
import { icon } from "../icons.js";
import { pathInput, checkEl, logView, followTask } from "../components.js";

export default {
  id: "sdscripts", label: "sd-scripts", icon: "branch",

  async mount(ctx, params, root) {
    const sd = ctx.boot.sd;
    if (!sd.configured || !sd.valid) return setup(ctx, root);

    const actLog = logView(260);
    const activity = card({ title: "Activity" }, actLog.el);
    activity.classList.add("hidden");
    let installDeps = true;
    let busy = false;

    root.append(ctx.header({ title: "sd-scripts", subtitle: sd.path, icon: "branch",
      actions: [btn("Open folder", { icon: "folder", onclick: () => api.open_folder(sd.path) })] }));
    const body = h("div.stack", h("div.loading", h("span.spin"), "Checking sd-scripts…"));
    root.append(body);

    function runTask(id, doneMsg) {
      busy = true;
      activity.classList.remove("hidden");
      actLog.clear();
      activity.scrollIntoView({ behavior: "smooth", block: "start" });
      followTask(id, actLog, async (t) => {
        busy = false;
        if (t.status === "done") toast(doneMsg, "", "good", "circleCheck");
        else toast("That didn't work", "See the activity log for details.", "bad", "alert", 9000);
        await ctx.refreshBoot();
        load(false);
      });
    }

    async function load(fetch) {
      let st;
      try { st = await api.sd_status(fetch); } catch (e) { toastError(e); return; }
      const behind = st.behind;
      const status = card({ title: "Installed" },
        kv([["Branch", h("b", st.branch || "—")], ["Commit", h("span.mono", st.commit || "—")], ["Updated", st.commit_age || "—"], ["Latest change", st.commit_subject || "—"]]),
        h("div", { style: { height: "14px" } }),
        h("div.row",
          st.venv ? chip("venv found", "good", "check") : chip("No venv", "bad", "alert"),
          st.accelerate ? chip("accelerate", "good", "check") : chip("accelerate missing", "warn", "alert"),
          st.dirty ? chip("Local edits", "warn", "rename") : null));

      const changelog = (st.changelog || []).map((c) =>
        h("div.list-row", h("div.ic.accent", icon("sparkle")),
          h("div.main-col", h("div.title", c.subject), h("div.meta", `${c.commit} · ${c.author} · ${c.age}`))));

      const updates = card({ title: "Updates", actions: btn("Check for updates", { icon: "refresh", size: "sm", kind: "ghost", onclick: async (e) => {
          e.currentTarget.disabled = true; await load(true); } }) },
        st.fetch_error ? h("div.notice.warn", icon("alert"), h("div", "Couldn't reach GitHub: ", h("span.mono", st.fetch_error))) : null,
        behind == null ? h("p.muted", "This branch doesn't track a remote branch, so updates can't be checked.")
          : behind === 0 ? h("div.row", { style: { gap: "14px" } }, h("div.sev.ok", { style: { width: "44px", height: "44px", borderRadius: "14px", display: "grid", placeItems: "center" } }, icon("circleCheck")),
              h("div", h("b", "You're up to date"), h("div.small.muted", fetch ? "Just checked GitHub." : "Press “Check for updates” to look for new commits.")))
            : h("div.stack.sm",
              h("div.row", h("b", { style: { fontSize: "16px" } }, `${behind} new commit${behind === 1 ? "" : "s"} on ${st.branch}`), h("div.spacer"),
                checkEl(installDeps, (v) => { installDeps = v; }, "Reinstall requirements"),
                btn("Update now", { icon: "download", kind: "primary", disabled: st.dirty, onclick: async () => {
                  if (busy) return;
                  try { runTask(await api.sd_update(installDeps), "sd-scripts updated"); } catch (e) { toastError(e); }
                } })),
              st.dirty ? h("div.notice.warn", icon("alert"), "You've edited files inside sd-scripts. Stash or revert them before updating so nothing gets overwritten.") : null,
              h("div.list", { style: { maxHeight: "300px", overflow: "auto" } }, changelog)));
      updates.classList.add("span2");

      const branchSel = h("select.select", h("option", { value: "" }, "Loading branches…"));
      api.sd_branches().then((bs) => {
        clear(branchSel, bs.map((b) => h("option", { value: b.name, selected: b.name === st.branch }, `${b.name}  ·  ${b.age}`)));
      }).catch(() => clear(branchSel, h("option", st.branch)));
      const branch = card({ title: "Branch" },
        h("p.small.muted", { style: { marginTop: 0 } }, "Newer model families sometimes live on a development branch before they reach main."),
        h("div.row.nowrap", branchSel, btn("Switch", { icon: "branch", onclick: async () => {
          const b = branchSel.value;
          if (!b || b === st.branch) return;
          if (!(await confirmBox(`Switch to ${b}?`, "sd-scripts will check out that branch and reinstall its requirements. You can roll back afterwards."))) return;
          try { runTask(await api.sd_switch_branch(b, installDeps), `Now on ${b}`); } catch (e) { toastError(e); }
        } })));

      const rollback = card({ title: "Roll back" },
        h("p.small.muted", { style: { marginTop: 0 } }, "Go back to the version you had before the last update or branch switch."),
        btn("Roll back", { icon: "rollback", disabled: !st.can_rollback, onclick: async () => {
          if (!(await confirmBox("Roll back sd-scripts?", "This returns to the previous commit and reinstalls its requirements."))) return;
          try { runTask(await api.sd_rollback(installDeps), "Rolled back"); } catch (e) { toastError(e); }
        } }));

      const folder = card({ title: "Folder" },
        h("p.small.muted.mono", { style: { marginTop: 0, wordBreak: "break-all" } }, st.path),
        btn("Use a different folder", { icon: "folder", onclick: async () => {
          await ctx.saveSettings({ sd_scripts_dir: "" });
          await ctx.refreshBoot();
          ctx.go("sdscripts");
        } }));

      const recent = card({ title: "Recent history" }, h("div.list",
        (st.recent || []).map((c) => h("div.list-row", h("div.ic", icon("branch")),
          h("div.main-col", h("div.title", c.subject), h("div.meta", `${c.commit} · ${c.author} · ${c.age}`))))));

      clear(body,
        h("div.grid.c3", status, updates),
        h("div.grid.c3", branch, rollback, folder),
        activity, recent);
    }
    load(false);
  },
};

function setup(ctx, root) {
  const sd = ctx.boot.sd;
  root.append(ctx.header({ title: "Let's connect sd-scripts", subtitle: "LoRA Studio drives your own copy of kohya-ss/sd-scripts.", icon: "branch" }));

  let path = sd.path || ctx.boot.guesses[0] || "";
  const msg = h("div");
  const connect = card({ title: "I already have sd-scripts" },
    h("p.muted.small", { style: { marginTop: 0 } }, "Pick the folder that contains train_network.py. Its venv is used for training, so nothing heavy gets installed twice."),
    h("div.stack.sm",
      pathInput(path, (v) => { path = v; }, { folder: true, placeholder: "C:/Users/you/Desktop/Work/sd-scripts" }),
      ctx.boot.guesses.length ? h("div.row", h("span.small.faint", "Found:"), ctx.boot.guesses.map((g) => h("button.chip.accent", { style: { border: 0, cursor: "pointer" }, onclick: () => { path = g; root.querySelector(".input").value = g; } }, g))) : null,
      sd.configured && !sd.valid ? h("div.notice.bad", icon("alert"), `“${sd.path}” doesn't look like sd-scripts (no train_network.py).`) : null,
      msg,
      h("div", btn("Connect", { icon: "check", kind: "primary", onclick: async () => {
        try {
          const r = await api.check_sd_folder(path);
          if (!r.valid) {
            clear(msg, h("div.notice.bad", icon("alert"), r.exists ? "That folder doesn't contain sd-scripts." : "That folder doesn't exist."));
            return;
          }
          await ctx.saveSettings({ sd_scripts_dir: path });
          await ctx.refreshBoot();
          toast("Connected", r.venv ? "Found sd-scripts and its venv." : "Connected, but no venv was found inside it.", r.venv ? "good" : "", r.venv ? "circleCheck" : "alert");
          ctx.go("sdscripts");
        } catch (e) { toastError(e); }
      } }))));

  const inst = { dest: "", branch: "main", python: "", torch: ctx.boot.settings.torch_index_url };
  const log = logView(240);
  const logCard = card({ title: "Install log" }, log.el);
  logCard.classList.add("hidden");
  const install = card({ title: "Install a fresh copy" },
    h("p.muted.small", { style: { marginTop: 0 } }, "Clones sd-scripts from GitHub, creates its venv, and installs PyTorch and the requirements. It's a few GB, so expect it to take a while."),
    h("div.stack.sm",
      h("div.field", h("label", "Install into (an empty folder)"), pathInput("", (v) => { inst.dest = v; }, { folder: true, placeholder: "C:/AI/sd-scripts" })),
      h("div.grid.c2",
        h("div.field", h("label", "Branch"), h("input.input", { value: "main", onchange: (e) => { inst.branch = e.target.value.trim() || "main"; } })),
        h("div.field", h("label", "Python to use"), h("input.input.mono", { placeholder: ctx.boot.platform === "windows" ? "py -3.10" : "python3.10", onchange: (e) => { inst.python = e.target.value.trim(); } }))),
      h("div.field", h("label", "PyTorch download index"), h("input.input.mono", { value: inst.torch, onchange: (e) => { inst.torch = e.target.value.trim(); } }),
        h("div.help", "cu128 suits RTX 20/30/40/50-series cards. Use cu126 or cu124 for older drivers.")),
      h("div", btn("Install", { icon: "download", onclick: async (e) => {
        if (!inst.dest) return toast("Pick a folder first", "", "", "folder");
        e.currentTarget.disabled = true;
        logCard.classList.remove("hidden");
        try {
          const id = await api.sd_install(inst.dest, inst.branch, inst.python, inst.torch);
          followTask(id, log, async (t) => {
            if (t.status === "done") { await ctx.refreshBoot(); toast("sd-scripts installed", "", "good", "circleCheck"); ctx.go("sdscripts"); }
            else { e.target.disabled = false; toast("Install didn't finish", "Check the log below.", "bad", "alert"); }
          });
        } catch (err) { toastError(err); }
      } }))));

  root.append(h("div.stack", h("div.grid.c2", connect, install), logCard,
    h("div.notice", icon("info"), h("div", "Your settings, run history and presets live in ", h("span.mono", ctx.boot.data_dir), ", separate from sd-scripts, so updating or reinstalling sd-scripts never touches them."))));
}

