// SwarmUI & ComfyUI: start/open them, use them inside LoRA Studio, see the LoRAs you've sent, set them up.
import { api } from "../api.js";
import { h, btn, card, chip, empty, fmtAgo, fmtSize, clear, store, toast, toastError, confirmBox } from "../dom.js";
import { icon } from "../icons.js";
import { seg, pathInput } from "../components.js";
import { metaModal } from "../runextras.js";

export default {
  id: "swarm", label: "SwarmUI & ComfyUI", icon: "hive",

  mount(ctx, params, root) {
    let tab = params.tab || store.get("genTab", "swarm");
    const headSlot = h("div");
    const body = h("div.stack");
    root.append(headSlot, body);

    const header = () => clear(headSlot, ctx.header({
      title: tab === "comfy" ? "ComfyUI" : "SwarmUI",
      subtitle: tab === "comfy" ? "Build workflows with your new LoRAs, right next to your training." : "Your SwarmUI install, right next to your training.",
      icon: "hive",
      actions: [seg([["swarm", "SwarmUI", "hive"], ["comfy", "ComfyUI", "layers"]], tab, (v) => { tab = v; store.set("genTab", v); draw(); })],
    }));

    function draw() {
      header();
      clear(body);
      (tab === "comfy" ? comfyTab : swarmTab)(ctx, body);
    }
    draw();
  },
};

// ---------- shared pieces ----------------------------------------------------------

function statusRow(st, { name, onStart, onOpen, onRefresh, notSet }) {
  if (!st.configured) return h("p.muted.small", { style: { margin: 0 } }, notSet);
  if (!st.valid) return h("div.notice.bad", icon("alert"), `That folder doesn't look like ${name}.`);
  return h("div.row",
    st.running ? chip(`Running${st.version ? " · " + st.version : ""}`, "good", "dot") : chip("Not running", "", "dot"),
    st.lora_dir ? h("span.small.faint.ellipsis", { style: { flex: 1 } }, "LoRAs go to ", h("span.mono", st.lora_dir)) : h("div.spacer"),
    st.running ? btn("Open in browser", { icon: "external", onclick: onOpen })
      : btn(`Start ${name}`, { icon: "play", kind: "primary", onclick: async (e) => {
        const b = e.currentTarget;
        try {
          await onStart();
          b.disabled = true;
          b.lastChild.textContent = "Starting…";
          toast(`Starting ${name}`, "It opens in a minimized window. This page updates when it's ready.", "", "play", 8000);
          for (let i = 0; i < 60; i++) {
            await new Promise((r) => setTimeout(r, 3000));
            if ((await onRefresh(true))?.running) { toast(`${name} is up`, "", "good", "circleCheck"); break; }
          }
          onRefresh();
        } catch (err) { toastError(err); }
      } }),
    btn("", { icon: "refresh", title: "Check again", onclick: () => onRefresh() }));
}

function embedCard(getStatus, label) {
  const slot = h("div");
  let shown = false;
  const draw = () => {
    const st = getStatus();
    if (!st?.running) return clear(slot, h("p.small.muted", { style: { margin: 0 } }, `Start ${label} to use it inside LoRA Studio.`));
    if (!shown) {
      return clear(slot, h("div.row",
        h("p.small.muted", { style: { margin: 0, flex: 1 } }, `Opens ${label} inside this window, so you can try your new LoRAs without switching apps.`),
        btn(`Show ${label}`, { icon: "hive", kind: "primary", onclick: () => { shown = true; draw(); } })));
    }
    const frame = h("iframe.swarm-frame", { src: st.url, title: label });
    clear(slot,
      h("div.row", { style: { marginBottom: "10px" } },
        h("span.small.faint", "If this stays blank, use “Open in browser” instead."), h("div.spacer"),
        btn("", { icon: "refresh", size: "sm", kind: "ghost", title: "Reload", onclick: () => { frame.src = st.url; } }),
        btn("Hide", { size: "sm", kind: "ghost", onclick: () => { shown = false; draw(); } })),
      frame);
  };
  return { el: card({ title: `Use ${label} here` }, slot), draw };
}

function libraryCard(ctx, load, label) {
  const slot = h("div");
  const refresh = async () => {
    let lib;
    try { lib = await load(); } catch { lib = { groups: [] }; }
    if (!lib.groups.length) {
      clear(slot, empty("hive", "Nothing sent yet", `Choose “Copy into ${label}” on the Train page, or use the card on any run's page.`,
        btn("Run history", { icon: "history", onclick: () => ctx.go("runs") })));
      return;
    }
    clear(slot, h("div.list", lib.groups.map((g) => h("div.list-row", { style: { alignItems: "flex-start" } },
      h("div.ic.accent", icon("sparkle")),
      h("div.main-col",
        h("div.title", g.name),
        h("div.meta", `${g.files.length} file${g.files.length === 1 ? "" : "s"} · updated ${fmtAgo(g.modified)}`),
        h("div.row", { style: { marginTop: "8px", gap: "6px" } }, g.files.map((f) =>
          h("button.tag", { style: { cursor: "pointer" }, title: `${fmtSize(f.size)} · click to view or edit its info`, onclick: () => metaModal(f.path, null) },
            f.name.replace(".safetensors", ""))))),
      btn("", { icon: "folder", size: "sm", kind: "ghost", title: "Open folder", onclick: () => api.open_folder(g.folder) })))));
  };
  refresh();
  return card({ title: `Your LoRAs in ${label}`, actions: h("div.row",
    btn("", { icon: "refresh", size: "sm", kind: "ghost", title: "Refresh", onclick: refresh }),
    btn("Open folder", { icon: "folder", size: "sm", kind: "ghost", onclick: async () => { const l = await load(); if (l.folder) api.open_folder(l.folder); } })) }, slot);
}

// ---------- SwarmUI -----------------------------------------------------------------

function swarmTab(ctx, body) {
  let st = null;
  const s = ctx.boot.settings;
  const statusSlot = h("div", h("div.loading", h("span.spin"), "Checking…"));
  const leftover = h("div");
  const embed = embedCard(() => st, "SwarmUI");
  const acSlot = h("div");
  const save = async (patch) => { try { await ctx.saveSettings(patch); refresh(); } catch (e) { toastError(e); } };

  async function refresh(quiet) {
    st = await api.swarm_status().catch(() => ({ configured: false }));
    if (quiet) return st;
    clear(statusSlot, statusRow(st, { name: "SwarmUI", notSet: "Not set up yet. Choose your SwarmUI folder below.",
      onStart: () => api.swarm_launch(), onOpen: () => api.swarm_open(), onRefresh: refresh }));
    embed.draw();
    if (st.valid && (await api.swarm_old_theme().catch(() => false))) {
      clear(leftover, h("div.notice", icon("info"), h("div", { style: { flex: 1 } },
        "The LoRA Studio theme from an earlier version is still installed in SwarmUI. ",
        btn("Remove it", { size: "sm", kind: "ghost", onclick: async () => {
          if (!(await confirmBox("Remove the old theme?", "Switch SwarmUI to another theme first (User → User Settings → Theme), then restart SwarmUI after removing."))) return;
          await api.swarm_remove_old_theme(); clear(leftover); toast("Theme removed", "Restart SwarmUI to finish.", "good", "check");
        } }))));
    } else clear(leftover);
    const ac = await api.autocomplete_sources().catch(() => ({ current: "", found: [] }));
    clear(acSlot, h("div.stack.sm",
      h("p.small.muted", { style: { margin: 0 } }, "The tag editor suggests tags from a CSV list, the same files SwarmUI uses for its autocomplete."),
      ac.found.length ? h("select.select", { onchange: (e) => save({ autocomplete_csv: e.target.value }) },
        ac.found.map((f) => h("option", { value: f, selected: f === ac.current }, f.split("/").pop()))) : null,
      pathInput(ctx.boot.settings.autocomplete_csv || "", (v) => save({ autocomplete_csv: v }), { kind: "any", placeholder: ac.current || "C:/path/to/tags.csv" }),
      h("div.small.faint", ac.current ? `Using ${ac.current.split("/").pop()}` : "No list found yet. Set your SwarmUI folder, or pick a CSV.")));
    return st;
  }

  body.append(
    card({ title: "Status" }, statusSlot),
    leftover,
    embed.el,
    libraryCard(ctx, () => api.swarm_library(), "SwarmUI"),
    card({ title: "Setup" }, h("div.stack",
      h("div.field", h("label", "SwarmUI folder"), pathInput(s.swarm_dir, (v) => save({ swarm_dir: v }), { folder: true, placeholder: "C:/Users/you/Desktop/Work/SwarmUI" }),
        h("div.help", "The folder with launch-windows.bat in it.")),
      h("div.grid.c2",
        h("div.field", h("label", "Address"), h("input.input.mono", { value: s.swarm_url || "http://127.0.0.1:7801", onchange: (e) => save({ swarm_url: e.target.value.trim() }) }),
          h("div.help", "7801 is SwarmUI's default port.")),
        h("div.field", h("label", "LoRA folder (optional override)"), pathInput(s.swarm_lora_dir, (v) => save({ swarm_lora_dir: v }), { folder: true, placeholder: "Detected automatically" }),
          h("div.help", "Leave empty to use the one in SwarmUI's settings. LoRAs are copied into a “LoRA Studio” subfolder."))))),
    card({ title: "Tag autocomplete" }, acSlot));
  refresh();
}

// ---------- ComfyUI -----------------------------------------------------------------

function comfyTab(ctx, body) {
  let st = null;
  const s = ctx.boot.settings;
  const statusSlot = h("div", h("div.loading", h("span.spin"), "Checking…"));
  const embed = embedCard(() => st, "ComfyUI");
  const setupSlot = h("div");
  const save = async (patch) => { try { await ctx.saveSettings(patch); refresh(); drawSetup(); } catch (e) { toastError(e); } };

  async function refresh(quiet) {
    st = await api.comfy_status().catch(() => ({ configured: false }));
    if (quiet) return st;
    const viaSwarm = st.mode === "swarm";
    clear(statusSlot, statusRow(st, {
      name: viaSwarm ? "SwarmUI" : "ComfyUI",
      notSet: viaSwarm ? "Uses the ComfyUI inside SwarmUI. Set your SwarmUI folder on the SwarmUI tab first." : "Not set up yet. Choose your ComfyUI folder below.",
      onStart: () => api.comfy_launch(), onOpen: () => api.comfy_open(), onRefresh: refresh,
    }));
    embed.draw();
    return st;
  }

  function drawSetup() {
    const mode = ctx.boot.settings.comfy_mode || (ctx.boot.settings.comfy_dir ? "standalone" : "swarm");
    clear(setupSlot, h("div.stack",
      h("div.field", h("label", "Which ComfyUI?"),
        seg([["swarm", "The one inside SwarmUI"], ["standalone", "A separate ComfyUI install"]], mode, (v) => save({ comfy_mode: v }))),
      mode === "swarm"
        ? h("p.small.muted", { style: { margin: 0 } }, "SwarmUI runs ComfyUI behind the scenes. This shows that same ComfyUI, so it shares SwarmUI's models and LoRA folder, and starting SwarmUI starts it too.")
        : [
          h("div.field", h("label", "ComfyUI folder"), pathInput(s.comfy_dir, (v) => save({ comfy_dir: v }), { folder: true, placeholder: "C:/AI/ComfyUI_windows_portable" }),
            h("div.help", "The portable folder (with run_nvidia_gpu.bat) or a git install (with main.py).")),
          h("div.grid.c2",
            h("div.field", h("label", "Address"), h("input.input.mono", { value: s.comfy_url || "http://127.0.0.1:8188", onchange: (e) => save({ comfy_url: e.target.value.trim() }) }),
              h("div.help", "8188 is ComfyUI's default port.")),
            h("div.field", h("label", "LoRA folder (optional override)"), pathInput(s.comfy_lora_dir, (v) => save({ comfy_lora_dir: v }), { folder: true, placeholder: "models/loras, detected automatically" }),
              h("div.help", "LoRAs are copied into a “LoRA Studio” subfolder. ComfyUI picks them up when you refresh its LoRA list."))),
        ]));
  }

  body.append(
    card({ title: "Status" }, statusSlot),
    embed.el,
    libraryCard(ctx, () => api.comfy_library(), "ComfyUI"),
    card({ title: "Setup" }, setupSlot));
  drawSetup();
  refresh();
}
