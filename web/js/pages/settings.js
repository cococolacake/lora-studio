// Settings: appearance (theme engine), training defaults, paths, about.
import { api } from "../api.js";
import { h, btn, card, toast, toastError, promptBox, confirmBox, clear, modal } from "../dom.js";
import { icon } from "../icons.js";
import { seg, switchEl, rangeEl, pathInput } from "../components.js";
import { applyTheme } from "../theme.js";
import { updateNow } from "../selfupdate.js";
import { cssThemes } from "../csstheme.js";

const SECTIONS = [["appearance", "Appearance", "palette"], ["training", "Training", "wand"], ["paths", "Folders & backup", "folder"], ["about", "About", "info"]];

export default {
  id: "settings", label: "Settings", icon: "gear",

  mount(ctx, params, root) {
    const section = params.section || "appearance";
    ctx.side(h("h2", "Settings"), SECTIONS.map(([id, label, ic]) =>
      h("button.side-item", { class: id === section ? "active" : "", onclick: () => ctx.go("settings", { section: id }) }, icon(ic), h("span", label))));
    if (section === "swarm") return ctx.go("swarm");   // SwarmUI has its own page now
    ({ appearance, training, paths, about })[section](ctx, root);
  },
};

// ---------------------------------------------------------------------------
function appearance(ctx, root) {
  let theme = structuredClone(ctx.boot.settings.theme);
  let themes = ctx.boot.themes;
  let saveTimer = null;
  const headSlot = h("div");
  root.append(headSlot);

  const commit = (redraw = true) => {
    applyTheme(theme);
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => ctx.saveSettings({ theme }).catch(toastError), 350);
    if (redraw) draw();
  };

  const body = h("div.stack");
  root.append(body);

  // CSS themes: made once (it listens for drops on the whole page), refreshed on every redraw
  const css = cssThemes(ctx, { getCurrent: () => theme.css || "", use: (name) => { theme.css = name; commit(); } });
  const cssCard = card({ title: "CSS themes" }, css.el);

  // Glass theme previews: the family's background, a panel and its button colour.
  const FAMILY = {
    default: { light: ["#E4E5E9", "#D3D5DB", "rgba(255,255,255,.75)", "#C3C6D2", "#2B2C33", "#4C4E5A"], dark: ["#2C2D33", "#212227", "#3C3E49", "#30344A", "#F2F2F5", "#C8C9D2"] },
    cool: { light: ["#DCE3EE", "#C9D2E2", "#B3C2F3", "#B8DEEC", "#5876F5", "#68BDEE"], dark: ["#252D3F", "#1B2231", "#36498F", "#246A80", "#7D96FF", "#7ED2F6"] },
    warm: { light: ["#ECE2DA", "#DDCDC2", "#F0BCA4", "#E8BCC9", "#DB7A5D", "#E097AE"], dark: ["#302723", "#241D1A", "#7A3E32", "#6A374F", "#F0997B", "#EFA8BF"] },
    lilac: { light: ["#EFE4E2", "#E2D5DD", "#DAC8F1", "#B8A6DD", "#6E5E9E", "#A48DD6"] },
    heart: { light: ["#F6E7F0", "#EAD6E6", "#FFB3D9", "#BDF5EE", "#FF5FB0", "#FF8AC8"], dark: ["#160B22", "#1D0E2C", "#FF5FB0", "#9B6BFF", "#FF5FB0", "#FF8AC8"] },
  };
  function themePreview(t) {
    const fam = FAMILY[t.family] || FAMILY.default;
    const [b1, b2, c1, c2, a1, a2] = (t.base === "dark" && fam.dark) || fam.light;
    const panel = t.base === "dark" && fam.dark ? "rgba(255,255,255,.08)" : "rgba(255,255,255,.55)";
    return h("div.tp", { style: { background: `radial-gradient(60% 90% at 10% 0%, ${c1}, transparent), radial-gradient(60% 90% at 100% 20%, ${c2}, transparent), linear-gradient(160deg, ${b1}, ${b2})` } },
      h("div.mini", { style: { background: panel, boxShadow: "inset 0 1px 0 rgba(255,255,255,.5)", border: "1px solid rgba(255,255,255,.45)" } },
        h("i", { style: { background: `linear-gradient(165deg, ${a1}, ${a2})` } }), h("b", { style: { background: t.base === "dark" && fam.dark ? "#fff" : "#17171A" } })));
  }

  function draw() {
    clear(headSlot, ctx.header({ title: "Appearance", subtitle: "Changes apply right away.", icon: "palette",
      actions: [btn("Save as theme", { icon: "save", onclick: async () => {
        const name = await promptBox("Save theme", "Theme name", theme.name && !themes.find((t) => !t.user && t.name === theme.name) ? theme.name : "My theme");
        if (!name) return;
        theme.name = name;
        themes = await api.save_theme(theme);
        ctx.boot.themes = themes;
        commit();
        toast("Theme saved", name, "good", "palette");
      } })] }));

    const isOn = (t) => t.name === theme.name && t.family === theme.family;
    const pick = (t) => { const base = theme.base; theme = structuredClone({ ...t, user: undefined }); delete theme.user; theme.base = base; commit(); };
    const gallery = card({ title: "Themes" }, h("div.theme-cards", themes.map((t) =>
      h("button.theme-card", { class: isOn(t) ? "on" : "", onclick: () => pick(t) },
        themePreview({ ...t, base: theme.base }),
        h("div.tn", t.name, h("div.spacer"), t.user ? h("span", { title: "Delete theme", style: { color: "var(--text-3)", display: "flex" },
          onclick: async (e) => { e.stopPropagation(); themes = await api.delete_theme(t.name); ctx.boot.themes = themes; draw(); } }, icon("trash")) : null)))));

    const colours = card({ title: "Mode" }, h("div.stack",
      seg([["light", "Light", "sun"], ["dark", "Dark", "moon"]], theme.base, (v) => { theme.base = v; commit(); }),
      theme.family === "lilac" && theme.base === "dark" ? h("p.small.faint", { style: { margin: 0 } }, "Lilac is a light theme, so dark mode uses Cool Glass dark.") : null));

    const effects = card({ title: "Glass effects" }, h("div.stack",
      seg([["efficient", "Efficient"], ["full", "Full"], ["off", "Off"]], theme.glass || "efficient", (v) => { theme.glass = v; commit(); }),
      h("p.small.muted", { style: { margin: 0 } }, ({
        efficient: "See-through panels over a still background. It looks almost the same as Full and is very light on your GPU. Recommended.",
        full: "Real live blur behind every panel. It's the prettiest, and it uses the most GPU power, so it suits a strong graphics card.",
        off: "Solid panels, no see-through or blur. The colours and layout stay the same.",
      })[theme.glass || "efficient"]),
      theme.glass === "off" ? null : switchEl(theme.simpleWhileTraining !== false, (v) => { theme.simpleWhileTraining = v; commit(false); }, "Simpler look while training"),
      theme.glass === "off" ? null : h("p.small.faint", { style: { margin: 0 } }, "While a LoRA trains, panels turn solid so the training gets the whole GPU. They go back when it finishes.")));

    const text = card({ title: "Text" }, h("div.field", h("label", "Font"),
      seg([["geist", "Geist"], ["system", "System"]], theme.font === "system" ? "system" : "geist", (v) => { theme.font = v; commit(); })));

    css.refresh();
    clear(body, gallery, cssCard, colours, effects, text,
      h("div.notice", icon("info"), h("div", "Want to go further? ", h("span.mono", "web/css/custom.css"), " is yours to edit: change colours, corner roundness, anything. It's loaded last, so it wins over CSS themes too.")));
  }
  draw();
}

// ---------------------------------------------------------------------------
function training(ctx, root) {
  const s = ctx.boot.settings;
  const saveKey = (k) => (v) => ctx.saveSettings({ [k]: v }).then(() => toast("Saved", "", "good", "check", 1500)).catch(toastError);
  root.append(ctx.header({ title: "Training", subtitle: "How LoRA Studio launches sd-scripts.", icon: "wand" }),
    h("div.stack",
      card({ title: "Launcher" }, h("div.stack",
        h("div.field", h("label", "Start training with"), seg([["accelerate", "accelerate launch"], ["python", "plain python"]], s.launcher, saveKey("launcher")),
          h("div.help", "accelerate is what sd-scripts recommends. Plain python is handy if accelerate gives you trouble on a single GPU.")),
        h("div.field", h("label", "accelerate arguments"), h("input.input.mono", { value: s.accelerate_args, onchange: (e) => saveKey("accelerate_args")(e.target.value) }),
          h("div.help", "Inserted between “accelerate launch” and the script. --num_cpu_threads_per_process 4 is a good default.")))),
      card({ title: "Output folders" },
        switchEl(s.run_folders !== false, saveKey("run_folders"), "Give each run its own folder"),
        h("p.small.muted", { style: { margin: "6px 0 0" } },
          "Each training saves into a folder named after it inside your output folder, e.g. …/model/shion_anima_v1. If that folder already has files from an earlier run, the new one becomes “shion_anima_v1 (2)”, so nothing is ever overwritten.")),
      card({ title: "Notifications" }, h("div.row",
        h("div", { style: { flex: 1 } }, switchEl(s.notify_on_finish !== false, saveKey("notify_on_finish"), "Notification when a training finishes or fails"),
          h("p.small.muted", { style: { margin: "6px 0 0" } }, ctx.boot.platform === "windows"
            ? "Shows up in the corner of your screen (sent by “Windows PowerShell”, which is how Windows lets small apps do this)."
            : "Shows up as a desktop notification (uses notify-send, which most Linux desktops have).")),
        btn("Send a test", { icon: "bell", onclick: () => api.test_notification().then(() => toast("Sent", "Check the corner of your screen.", "", "bell")).catch(toastError) }))),
      card({ title: "Installs" }, h("div.field", h("label", "PyTorch download index (for fresh installs)"),
        h("input.input.mono", { value: s.torch_index_url, onchange: (e) => saveKey("torch_index_url")(e.target.value) })))));
}

function paths(ctx, root) {
  const s = ctx.boot.settings;
  root.append(ctx.header({ title: "Folders & backup", icon: "folder" }),
    h("div.stack",
      card({ title: "sd-scripts" }, h("p.mono.small", { style: { marginTop: 0 } }, s.sd_scripts_dir || "Not set"), btn("Manage sd-scripts", { icon: "branch", onclick: () => ctx.go("sdscripts") })),
      card({ title: "SwarmUI & ComfyUI" }, h("p.mono.small", { style: { marginTop: 0 } }, s.swarm_dir || s.comfy_dir || "Not set"), btn("Open the SwarmUI & ComfyUI page", { icon: "hive", onclick: () => ctx.go("swarm") })),
      card({ title: "LoRA Studio data" }, h("p.mono.small", { style: { marginTop: 0 } }, ctx.boot.data_dir),
        btn("Open folder", { icon: "folder", onclick: () => api.open_folder(ctx.boot.data_dir) })),
      backupCard(ctx)));
}

function backupCard(ctx) {
  let restorePath = "";
  const last = h("div");
  return card({ title: "Backup & restore" }, h("div.stack",
    h("p.small.muted", { style: { margin: 0 } }, "Your settings, presets, themes and run history in one .zip, handy before reinstalling your system or moving to a new PC. Your datasets and trained LoRAs aren't included (they're your own files), and neither are site logins."),
    h("div.row",
      btn("Create backup", { icon: "save", kind: "primary", onclick: async () => {
        try {
          const folder = ctx.boot.native ? await api.pick_folder() : null;
          const r = await api.backup_create(folder);
          clear(last, h("div.notice.good", icon("circleCheck"), h("div", { style: { flex: 1 } }, `Saved ${r.files} files to `, h("span.mono", r.path)),
            btn("Show", { size: "sm", kind: "ghost", onclick: () => api.open_folder(r.path.split("/").slice(0, -1).join("/")) })));
        } catch (e) { toastError(e); }
      } }),
      h("span.small.faint", ctx.boot.native ? "You'll be asked where to save it." : "Saved in LoRA Studio's backups folder.")),
    last,
    h("hr.soft"),
    h("div.field", h("label", "Restore from a backup"), h("div.row.nowrap",
      h("div", { style: { flex: 1 } }, pathInput("", (v) => { restorePath = v; }, { kind: "zip", placeholder: "C:/path/to/LoRA Studio backup.zip" })),
      btn("Restore", { icon: "rollback", onclick: async () => {
        if (!restorePath) return toast("Choose a backup file first", "", "", "folder");
        if (!(await confirmBox("Restore this backup?", "Settings, presets, themes and runs from the backup are added back; anything with the same name is replaced. A safety backup of what's here now is made first."))) return;
        try {
          const r = await api.backup_restore(restorePath);
          toast("Restored", `${r.restored} files. Restarting the page…`, "good", "rollback");
          setTimeout(() => location.reload(), 1200);
        } catch (e) { toastError(e); }
      } })))));
}

function about(ctx, root) {
  const s = ctx.boot.settings;
  const upd = h("div.row", { style: { gap: "10px", flexWrap: "wrap" } });
  const showUpd = (u) => {
    if (u && !u.off) ctx.update = u;
    clear(upd, !u || u.off ? null
      : u.newer ? [h("span.small", h("b", `${u.latest.tag} is available.`)), btn("Update now", { icon: "download", kind: "primary", size: "sm", onclick: () => updateNow(ctx, u.latest) })]
      : h("span.small.muted", u.latest ? `You're up to date (latest is ${u.latest.tag}).` : "Couldn't reach GitHub just now."));
  };
  if (ctx.update) showUpd(ctx.update);
  root.append(ctx.header({ title: "LoRA Studio", subtitle: `Version ${ctx.boot.version}`, icon: "sparkle" }),
    h("div.stack",
      card(null, h("p", { style: { marginTop: 0 } }, "A friendly front end for kohya-ss/sd-scripts. Your sd-scripts install does the training; LoRA Studio builds the configs, queues runs, and keeps the history."),
        h("p.small.muted", { style: { marginBottom: 0 } }, ctx.boot.native ? "Running in the app window." : "Running in browser mode.")),
      card({ title: "Updates" },
        h("div.row", { style: { gap: "12px", flexWrap: "wrap" } },
          switchEl(s.check_app_updates !== false, async (v) => { await ctx.saveSettings({ check_app_updates: v }); }, "Tell me when a new version is out"),
          btn("Check now", { icon: "refresh", onclick: async () => { clear(upd, h("span.small.muted", "Checking…")); try { showUpd(await api.app_update(true)); } catch (e) { toastError(e); } } })),
        h("div", { style: { marginTop: "8px" } }, upd)),
      card({ title: "Something not working?" },
        h("p.small.muted", { style: { marginTop: 0 } }, "Copy diagnostics puts your LoRA Studio and sd-scripts versions, system, GPU and the end of the last failed run's log on your clipboard, ready to paste into a bug report. Your name is hidden from folder paths and site logins are never included."),
        h("div.row", { style: { gap: "10px", flexWrap: "wrap" } },
          btn("Copy diagnostics", { icon: "copy", kind: "primary", onclick: () => copyDiagnostics() }),
          btn("Report a problem", { icon: "alert", onclick: () => api.open_url("https://github.com/cococolacake/lora-studio/issues/new/choose").catch(toastError) })))));
}

export async function copyDiagnostics() {
  let text;
  try { text = await api.diagnostics(); } catch (e) { return toastError(e); }
  try {
    await navigator.clipboard.writeText(text);
    toast("Diagnostics copied", "Paste them into your bug report.", "good", "copy");
  } catch {
    // Some windows don't allow clipboard access: show it so it can be copied by hand.
    const ta = h("textarea.textarea.mono", { rows: 14, readonly: true, style: { width: "100%" } });
    ta.value = text;
    await modal("Diagnostics", h("div.stack.sm", h("p.small.muted", { style: { margin: 0 } }, "Select all (Ctrl+A) and copy (Ctrl+C):"), ta), [{ label: "Done", kind: "primary" }]);
  }
}
