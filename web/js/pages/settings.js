// Settings: appearance (theme engine), training defaults, paths, about.
import { api } from "../api.js";
import { h, btn, card, toast, toastError, promptBox, confirmBox, clear } from "../dom.js";
import { icon } from "../icons.js";
import { seg, switchEl, rangeEl, pathInput } from "../components.js";
import { ACCENTS, PATTERNS, patternCSS, accentColors, headerCSS, applyTheme } from "../theme.js";

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

  function themePreview(t) {
    const css = headerCSS(t) || { background: "var(--surface-3)" };
    const accent = (ACCENTS.find((a) => a[0] === t.accent) || ACCENTS[0])[2];
    const dark = t.base === "dark";
    return h("div.tp", { style: css },
      h("div.mini", { style: { background: dark ? "#19191C" : "#fff" } }, h("i", { style: { background: accent } }), h("b", { style: { background: dark ? "#fff" : "#17171A" } })));
  }

  function draw() {
    clear(headSlot, ctx.header({ title: "Appearance", subtitle: "Changes apply instantly. The header above is a live preview.", icon: "palette",
      actions: [btn("Save as theme", { icon: "save", onclick: async () => {
        const name = await promptBox("Save theme", "Theme name", theme.name && !themes.find((t) => !t.user && t.name === theme.name) ? theme.name : "My theme");
        if (!name) return;
        theme.name = name;
        themes = await api.save_theme(theme);
        ctx.boot.themes = themes;
        commit();
        toast("Theme saved", name, "good", "palette");
      } })] }));

    const hd = theme.header;
    const isOn = (t) => t.name === theme.name && t.base === theme.base && t.accent === theme.accent;

    const gallery = card({ title: "Themes" }, h("div.theme-cards", themes.map((t) =>
      h("button.theme-card", { class: isOn(t) ? "on" : "", onclick: () => { theme = structuredClone({ ...t, user: undefined }); delete theme.user; commit(); } },
        themePreview(t),
        h("div.tn", t.name, h("div.spacer"), t.user ? h("span", { title: "Delete theme", style: { color: "var(--text-3)", display: "flex" },
          onclick: async (e) => { e.stopPropagation(); themes = await api.delete_theme(t.name); ctx.boot.themes = themes; draw(); } }, icon("trash")) : null)))));

    const colours = card({ title: "Colours" }, h("div.row", { style: { gap: "48px", alignItems: "flex-start", flexWrap: "nowrap" } },
      h("div.field", h("label", "Mode"), seg([["light", "Light", "sun"], ["dark", "Dark", "moon"]], theme.base, (v) => { theme.base = v; commit(); })),
      h("div.field", { style: { flex: 1 } }, h("label", "Accent"), h("div.swatches", { style: { marginTop: "4px" } }, ACCENTS.map(([id, label, hex]) =>
        h("button.swatch", { class: theme.accent === id ? "on" : "", onclick: () => { theme.accent = id; commit(); } },
          h("span.ball", { style: { background: hex } }), label))))));

    // ---- header editor ----
    const [ac1, ac2, ac3] = accentColors(theme.accent, theme.base);
    const colors = hd.useAccent ? [ac1, ac2] : (hd.colors?.length ? hd.colors : [ac1, ac2]);
    const tiles = h("div.pattern-tiles", PATTERNS.map(([id, label]) =>
      h("button.ptile", { class: hd.pattern === id && hd.type === "pattern" ? "on" : "", onclick: () => { hd.type = "pattern"; hd.pattern = id; commit(); } },
        h("div.p", { style: patternCSS(id, colors[0], colors[1], Math.max(10, (hd.scale || 28) * 0.55), ac3) }), label)));

    const colorIn = (i) => h("input.color-in", { type: "color", value: colors[i], disabled: hd.useAccent,
      oninput: (e) => { hd.colors = [...colors]; hd.colors[i] = e.target.value; colors[i] = e.target.value; commit(false); } });

    const fileIn = h("input", { type: "file", accept: "image/*", style: { display: "none" }, onchange: async (e) => {
      const f = e.target.files[0];
      if (!f) return;
      try {
        hd.image = await imageToDataUrl(f);
        hd.type = "image";
        commit();
      } catch (err) { toastError(err); }
    } });

    const headerCard = card({ title: "Header" },
      h("div.stack",
        seg([["pattern", "Pattern", "sparkle"], ["image", "Image", "image"], ["none", "None", "x"]], hd.type, (v) => { hd.type = v; commit(); }),
        hd.type === "pattern" ? [
          tiles,
          h("div.grid.c3",
            h("div.field", h("label", "Colours"), h("div.row", colorIn(0), colorIn(1), switchEl(hd.useAccent, (v) => { hd.useAccent = v; if (!v) hd.colors = [...colors]; commit(); }, "Match accent"))),
            h("div.field", h("label", "Pattern size"), rangeEl(hd.scale || 28, 10, 80, 1, (v) => { hd.scale = v; commit(false); })),
            h("div.field", h("label", "Header height"), rangeEl(hd.height || 132, 96, 260, 2, (v) => { hd.height = v; commit(false); }))),
        ] : null,
        hd.type === "image" ? [
          h("div.row", fileIn, btn(hd.image ? "Choose another image" : "Choose an image", { icon: "upload", kind: "primary", onclick: () => fileIn.click() }),
            hd.image ? btn("Remove", { icon: "trash", kind: "ghost", onclick: () => { hd.image = ""; hd.type = "pattern"; commit(); } }) : null),
          h("div.grid.c3",
            h("div.field", h("label", "Fit"), seg([["cover", "Fill"], ["tile", "Tile"], ["contain", "Fit"]], hd.imageFit || "cover", (v) => { hd.imageFit = v; commit(false); })),
            h("div.field", h("label", "Tile size"), rangeEl(hd.scale || 28, 10, 80, 1, (v) => { hd.scale = v; commit(false); })),
            h("div.field", h("label", "Header height"), rangeEl(hd.height || 132, 96, 260, 2, (v) => { hd.height = v; commit(false); }))),
          h("p.small.faint", { style: { margin: 0 } }, "Your art is stored with the theme, so saved themes keep their image. Tile mode works well for seamless patterns."),
        ] : null,
        hd.type === "none" ? h("p.small.muted", { style: { margin: 0 } }, "A clean page title with no banner.") : null));

    clear(body, gallery, colours, headerCard,
      h("div.notice", icon("info"), h("div", "Want to go further? ", h("span.mono", "web/css/custom.css"), " is yours to edit. Add new accents, change corner roundness, anything. It's loaded last, so it wins.")));
  }
  draw();
}

async function imageToDataUrl(file, maxW = 2400) {
  const url = await new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(file); });
  if (file.size < 1.5e6 || file.type === "image/gif") return url;
  const img = await new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = url; });
  const scale = Math.min(1, maxW / img.width);
  const c = document.createElement("canvas");
  c.width = Math.round(img.width * scale); c.height = Math.round(img.height * scale);
  c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
  return c.toDataURL("image/webp", 0.9);
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
  root.append(ctx.header({ title: "LoRA Studio", subtitle: `Version ${ctx.boot.version}`, icon: "sparkle" }),
    card(null, h("p", { style: { marginTop: 0 } }, "A friendly front end for kohya-ss/sd-scripts. Your sd-scripts install does the training; LoRA Studio builds the configs, queues runs, and keeps the history."),
      h("p.small.muted", { style: { marginBottom: 0 } }, ctx.boot.native ? "Running in the app window." : "Running in browser mode.")));
}
