// Train: pick any sd-scripts training script, fill a form generated from its own options, queue it.
import { api } from "../api.js";
import { h, btn, card, empty, toast, toastError, modal, promptBox, clear } from "../dom.js";
import { icon } from "../icons.js";
import { argField, datasetEditor, seg, switchEl, checkEl, pathInput } from "../components.js";

const schemaCache = {};

export default {
  id: "train", label: "Train", icon: "wand",

  async mount(ctx, params, root) {
    const scripts = ctx.boot.scripts || [];
    if (!scripts.length) {
      root.append(ctx.header({ title: "Train", icon: "wand" }),
        card(null, empty("branch", "No training scripts found", "Connect your sd-scripts folder first.", btn("Set up sd-scripts", { kind: "primary", onclick: () => ctx.go("sdscripts") }))));
      return;
    }
    let draft = ctx.draft || {};
    if (params.job) draft = { ...draft, ...params.job, mode: draft.mode || "simple" };
    if (!scripts.some((s) => s.file === draft.script)) {
      draft.script = (scripts.find((s) => s.family === "Anima" && s.kind.startsWith("LoRA")) || scripts.find((s) => s.kind.startsWith("LoRA")) || scripts[0]).file;
    }
    draft.mode ||= "simple";
    draft.args ||= null;
    draft.extra_args ||= "";

    let presets = await api.presets().catch(() => []);
    const side = () => {
      const groups = {};
      for (const s of scripts) (groups[s.family] ||= []).push(s);
      ctx.side(
        h("h2", "Train"),
        Object.entries(groups).map(([fam, list]) => [
          h("div.group-label", fam),
          list.map((s) => h("button.side-item", { class: s.file === draft.script ? "active" : "", onclick: () => pick(s.file) },
            icon(s.kind.startsWith("LoRA") ? "sparkle" : s.kind === "Full fine-tune" ? "box" : "wand"),
            h("span.grow", h("span", s.kind.startsWith("LoRA") ? "LoRA" : s.kind), h("span.sub", s.file)))),
        ]),
        h("div.sep"),
        h("div.group-label", "Presets"),
        presets.map((p) => h("button.side-item", { onclick: () => loadPreset(p.name) }, icon("save"),
          h("span.grow", h("span", p.name), h("span.sub", p.script || "")))),
        h("button.side-item.muted", { onclick: savePreset }, icon("plus"), h("span", "Save as preset")),
        h("button.side-item.muted", { onclick: importToml }, icon("download"), h("span", "Import .toml files")));
    };

    let schema = null;
    const body = h("div.stack");
    root.append(body);

    async function pick(file) {
      if (file !== draft.script) {
        draft = { ...draft, script: file, args: carryArgs(draft.args) };
      }
      await load();
    }

    function carryArgs(args) {
      if (!args) return null;
      const keep = {};
      for (const k of ["output_dir", "output_name", "learning_rate", "max_train_epochs", "save_every_n_epochs", "network_dim", "network_alpha", "seed", "save_state"]) {
        if (k in args) keep[k] = args[k];
      }
      return { __carry: keep };
    }

    async function load() {
      side();
      clear(body, h("div.loading", h("span.spin.lg"), h("div", h("b", "Reading the script's options…"), h("div.small.muted", "The first time, this imports sd-scripts in its venv and can take 10–30 seconds."))));
      try {
        schema = schemaCache[draft.script] ||= await api.schema(draft.script, false);
      } catch (e) {
        clear(body, card(null, empty("alert", "Couldn't read this script's options", e.message,
          btn("Try again", { onclick: () => { delete schemaCache[draft.script]; load(); } }))));
        return;
      }
      if (!draft.args || draft.args.__carry) {
        const carry = draft.args?.__carry || {};
        draft.args = { ...schema.defaults };
        for (const [k, v] of Object.entries(carry)) if (schema.args.some((a) => a.key === k)) draft.args[k] = v;
      }
      draft.family = schema.family;
      draft.dataset ||= structuredClone(schema.dataset_defaults);
      draft.samples = { ...schema.sample_defaults, ...(draft.samples || {}) };
      draft.lora_info ||= { title: "", author: "", trigger: draft.trigger || "", tags: "", description: "", thumbnail: "sample" };
      save();
      render();
    }

    let estTimer = null;
    const estSlot = h("div");
    const save = () => { ctx.saveDraft(draft); clearTimeout(estTimer); estTimer = setTimeout(updateEstimate, 700); };

    async function updateEstimate() {
      if (!schema || !(draft.dataset?.subsets || []).some((x) => (x.image_dir || "").trim())) {
        clear(estSlot, h("div.small.muted", "Add an image folder to see how long this will take."));
        return;
      }
      let e;
      try { e = await api.estimate({ script: draft.script, family: draft.family, args: draft.args, dataset: draft.dataset }); }
      catch { clear(estSlot, h("div.small.muted", "Couldn't read the dataset folder yet.")); return; }
      const fmt = (sec) => { const m = Math.round(sec / 60); return m < 60 ? `${Math.max(1, m)} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`; };
      clear(estSlot, h("div.est",
        h("div.ic.accent", { style: { width: "44px", height: "44px", borderRadius: "14px", display: "grid", placeItems: "center", background: "var(--accent-soft)", color: "var(--accent-text)" } }, icon("clock")),
        h("div", { style: { flex: 1 } },
          h("div.big", e.seconds ? `about ${fmt(e.seconds)}` : `${e.total_steps.toLocaleString()} steps`),
          h("div.small.muted", `${e.images} images · ${e.steps_per_epoch.toLocaleString()} steps per epoch × ${e.epochs} epochs = ${e.total_steps.toLocaleString()} steps`)),
        h("div.small.faint", { style: { textAlign: "right", maxWidth: "260px" } }, e.seconds
          ? `Based on ${e.based_on} past run${e.based_on === 1 ? "" : "s"} of ${e.basis}, adjusted for resolution and batch size.`
          : "Finish a run or two and LoRA Studio will learn how fast your GPU is.")));
    }
    const setArg = (k, v) => {
      if (v === null || v === undefined || v === "") delete draft.args[k]; else draft.args[k] = v;
      save();
      const f = body.querySelector(`.field[data-key="${k}"]`);
      const arg = schema.args.find((a) => a.key === k);
      if (f && arg) f.classList.toggle("changed", v != null && v !== "" && JSON.stringify(v) !== JSON.stringify(arg.default) && !(arg.kind === "bool" && v === false));
    };

    function job() {
      return {
        name: draft.name || draft.args.output_name || "",
        script: draft.script, family: draft.family,
        args: draft.args, dataset: draft.dataset, extra_args: draft.extra_args,
        schema_args: schema.args.map((a) => ({ key: a.key, kind: a.kind })),
        samples: draft.samples, lora_info: draft.lora_info, trigger: draft.lora_info?.trigger || "",
        send_to_swarm: draft.send_to_swarm || null,
        send_to_comfy: draft.send_to_comfy || null,
      };
    }

    function problems() {
      const out = [];
      if (!(draft.dataset.subsets || []).some((s) => (s.image_dir || "").trim())) out.push("Add at least one image folder to the dataset.");
      const has = (k) => schema.args.some((a) => a.key === k);
      if (has("pretrained_model_name_or_path") && !draft.args.pretrained_model_name_or_path) out.push("Choose the base model (Pretrained model name or path).");
      if (has("output_dir") && !draft.args.output_dir) out.push("Choose an output folder for the trained LoRA.");
      if (has("output_name") && !draft.args.output_name) out.push("Give the output a name.");
      return out;
    }

    async function submit(start) {
      const p = problems();
      if (p.length) {
        const go = await modal("A few things are missing", h("div.stack.sm", p.map((t) => h("div.notice.warn", icon("alert"), t))),
          [{ label: "Go back", kind: "ghost", value: false }, { label: "Queue anyway", value: true }]);
        if (!go) return;
      }
      try {
        await api.enqueue(job(), start);
        toast(start ? "Training started" : "Added to queue", job().name || draft.script, "good", start ? "play" : "layers");
        if (start) ctx.go("queue");
      } catch (e) { toastError(e); }
    }

    async function preview() {
      try {
        const t = await api.preview_toml(job());
        let which = "training";
        const pre = h("pre.code", t.training);
        await modal("Config preview", h("div.stack.sm",
          seg([["training", "training.toml"], ["dataset", "dataset.toml"]], which, (v) => { which = v; pre.textContent = t[v]; }), pre),
          [{ label: "Close", kind: "ghost" }]);
      } catch (e) { toastError(e); }
    }

    async function savePreset() {
      if (!schema) return;
      const name = await promptBox("Save preset", "Preset name", draft.args.output_name || "");
      if (!name) return;
      presets = await api.preset_save(name, { ...job(), mode: draft.mode, name: draft.name });
      side();
      toast("Preset saved", name, "good", "save");
    }

    async function loadPreset(name) {
      const p = await api.preset_load(name);
      if (!p) return;
      draft = { ...draft, ...p, mode: draft.mode };
      delete draft.schema_args;
      save();
      await load();
      toast("Preset loaded", name, "", "save");
    }

    async function importToml() {
      let tp = "", dp = "";
      const ok = await modal("Import .toml files", h("div.stack.sm",
        h("p.small.muted", { style: { margin: 0 } }, "Bring in a training.toml and/or dataset_config.toml, e.g. from an older setup or someone else's preset. Values for the current script are filled in."),
        h("div.field", h("label", "training.toml"), pathInput("", (v) => { tp = v; }, { kind: "toml" })),
        h("div.field", h("label", "dataset_config.toml"), pathInput("", (v) => { dp = v; }, { kind: "toml" }))),
        [{ label: "Cancel", kind: "ghost", value: false }, { label: "Import", kind: "primary", value: true }]);
      if (!ok) return;
      try {
        const r = await api.import_toml(tp, dp);
        if (r.args) {
          const keys = new Set(schema.args.map((a) => a.key));
          const renames = { anima_unsloth_offload_checkpointing: "unsloth_offload_checkpointing", anima_cache_text_encoder_outputs: "cache_text_encoder_outputs" };
          const skipped = [];
          // Sample previews are set on the Sample images card, not copied from the file:
          // the old prompts file belongs to the old setup (and would ignore the on/off switch).
          const sampleKeys = ["sample_prompts", "sample_every_n_epochs", "sample_every_n_steps", "sample_at_first"];
          const hadSamples = sampleKeys.some((k) => k in r.args);
          for (let [k, v] of Object.entries(r.args)) {
            k = renames[k] || k;
            if (sampleKeys.includes(k)) { delete draft.args[k]; continue; }
            if (keys.has(k)) draft.args[k] = v; else skipped.push(k);
          }
          if (hadSamples && draft.samples) {
            if (r.args.sample_every_n_epochs) draft.samples.every_n_epochs = r.args.sample_every_n_epochs;
            if (r.args.sample_at_first) draft.samples.at_first = true;
          }
          if (skipped.length) toast("Some options were skipped", `${draft.script} doesn't accept: ${skipped.join(", ")}`, "", "info", 10000);
          if (hadSamples) toast("Sample prompts not imported", "The file had sample settings. Type your prompts into Sample images and turn on “Make previews while training” if you want them.", "", "info", 10000);
        }
        if (r.dataset) draft.dataset = r.dataset;
        save();
        render();
        const outName = draft.args.output_name ? `Output name: ${draft.args.output_name}` : "";
        const folders = (draft.dataset?.subsets || []).map((s) => s.image_dir).filter(Boolean);
        toast("Imported", [outName, folders.length ? `Dataset: ${folders.join(", ")}` : ""].filter(Boolean).join(" · ") || "", "good", "download", 10000);
      } catch (e) { toastError(e); }
    }

    function render() {
      const info = (ctx.boot.scripts || []).find((s) => s.file === draft.script) || {};
      const kindLabel = info.kind?.startsWith("LoRA") ? "LoRA" : info.kind;
      const head = ctx.header({
        title: `${draft.family} ${kindLabel || ""}`.trim(), subtitle: draft.script, icon: "wand",
        actions: [
          btn("", { icon: "eye", title: "Preview config", onclick: preview }),
          btn("Add to queue", { icon: "layers", onclick: () => submit(false) }),
          btn("Train now", { icon: "play", kind: "primary", onclick: () => submit(true) }),
        ],
      });

      let search = "";
      let onlyChanged = false;
      const sections = h("div.stack");

      const runCard = card(null,
        h("div.row", { style: { gap: "14px" } },
          h("div.field", { style: { flex: "1", minWidth: "220px" } }, h("label", "Run name"),
            h("input.input", { value: draft.name || "", placeholder: draft.args.output_name || "My character v1", onchange: (e) => { draft.name = e.target.value; save(); } })),
          h("div.field", h("label", "View"), seg([["simple", "Simple", "sparkle"], ["advanced", "All options", "sliders"]], draft.mode, (v) => { draft.mode = v; save(); drawSections(); toggleSearch(); })),
        ));
      const searchRow = h("div.row", { style: { marginTop: "14px" } },
        h("div.search", { style: { flex: 1 } }, icon("search"), h("input.input", { placeholder: `Search ${schema.args.length} options…`, oninput: (e) => { search = e.target.value.toLowerCase(); drawSections(); } })),
        switchEl(false, (v) => { onlyChanged = v; drawSections(); }, "Only changed"));
      const toggleSearch = () => searchRow.classList.toggle("hidden", draft.mode !== "advanced");
      runCard.append(searchRow);
      toggleSearch();

      const dsCard = card({ title: "Dataset", actions: btn("Check health", { icon: "circleCheck", size: "sm", kind: "ghost", onclick: () => ctx.go("dataset", { tool: "health" }) }) },
        datasetEditor(draft.dataset, () => save()));

      const fieldFor = (a) => argField(a, draft.args[a.key], (v) => setArg(a.key, v));
      const byKey = Object.fromEntries(schema.args.map((a) => [a.key, a]));

      function samplesCard() {
        const sc = draft.samples;
        const set = (k, v) => { sc[k] = v; save(); };
        const num = (k, w = "100%") => h("input.input.nums", { value: sc[k], style: { width: w }, onchange: (e) => set(k, e.target.value === "" ? null : Number(e.target.value)) });
        const body = h("div.stack", { class: sc.enabled ? "" : "dim" },
          h("div.field", h("label", "Prompts ", h("span.key", "one image per line · # = comment")),
            h("textarea.input", { rows: 4, value: sc.prompts, oninput: (e) => set("prompts", e.target.value) })),
          h("div.grid.c2",
            h("div.field", h("label", "Quality tags"), h("input.input", { value: sc.quality, oninput: (e) => set("quality", e.target.value) })),
            h("div.field", h("label", "Negative prompt"), h("input.input", { value: sc.negative, oninput: (e) => set("negative", e.target.value) }))),
          h("div.grid.c4",
            h("div.field", h("label", "Width"), num("width")), h("div.field", h("label", "Height"), num("height")),
            h("div.field", h("label", "Steps"), num("steps")), h("div.field", h("label", "CFG"), num("cfg")),
            h("div.field", h("label", "Seed"), num("seed")),
            byKey.discrete_flow_shift ? h("div.field", h("label", "Flow shift"), num("flow_shift")) : null,
            h("div.field", h("label", "Every N epochs"), num("every_n_epochs")),
            h("div.field", h("label", "Quality tags go"), seg([["start", "First"], ["end", "Last"]], sc.quality_at, (v) => set("quality_at", v)))),
          h("div.row", { style: { gap: "22px" } },
            checkEl(sc.use_trigger, (v) => set("use_trigger", v), "Add the trigger word"),
            checkEl(sc.at_first, (v) => set("at_first", v), "Also before training starts")));
        return card({ title: "Sample images", actions: switchEl(sc.enabled, (v) => { set("enabled", v); body.classList.toggle("dim", !v); }, "Make previews while training") },
          h("p.small.muted", { style: { marginTop: 0 } }, "sd-scripts renders these during training. They show up as an epoch-by-prompt grid on the run's page."),
          body);
      }

      function finishCard() {
        const li = draft.lora_info;
        const set = (k, v) => { li[k] = v; save(); };
        const inp = (k, ph) => h("input.input", { value: li[k] || "", placeholder: ph, oninput: (e) => set(k, e.target.value) });
        const swarmOk = !!ctx.boot.settings.swarm_dir;
        const comfyOwn = ctx.boot.settings.comfy_mode === "standalone" || (!ctx.boot.settings.comfy_mode && !!ctx.boot.settings.comfy_dir);
        return card({ title: "When it's done" },
          h("div.grid.c3",
            h("div.field", h("label", "LoRA title"), inp("title", draft.args.output_name || "My character")),
            h("div.field", h("label", "Trigger word"), inp("trigger", "mychar")),
            h("div.field", h("label", "Author"), inp("author", "you"))),
          h("div.grid.c2", { style: { marginTop: "14px" } },
            h("div.field", h("label", "Description"), inp("description", "What it's for, recommended strength…")),
            h("div.field", h("label", "Tags"), inp("tags", "character, anime"))),
          h("div.row", { style: { marginTop: "16px", gap: "26px", alignItems: "flex-end" } },
            h("div.field", h("label", "Thumbnail"), seg([["sample", "Latest sample"], ["none", "None"]], li.thumbnail || "sample", (v) => set("thumbnail", v))),
            h("div.field", h("label", "Copy into SwarmUI"), seg([["", "No"], ["final", "Final LoRA"], ["all", "Every epoch"]], draft.send_to_swarm || "", (v) => { draft.send_to_swarm = v || null; save(); })),
            comfyOwn ? h("div.field", h("label", "Copy into ComfyUI"), seg([["", "No"], ["final", "Final LoRA"], ["all", "Every epoch"]], draft.send_to_comfy || "", (v) => { draft.send_to_comfy = v || null; save(); })) : null,
            swarmOk || comfyOwn ? null : h("span.small.faint", { style: { paddingBottom: "8px" } }, "Set up SwarmUI or ComfyUI on its page in the sidebar first.")),
          h("p.tiny.faint", { style: { marginBottom: 0 } }, "The title, trigger word, description and thumbnail are saved inside the .safetensors files, where SwarmUI's model browser shows them."));
      }

      function drawSections() {
        const cards = [];
        if (draft.mode === "simple") {
          for (const sec of schema.simple) {
            const fields = sec.keys.map((k) => fieldFor(byKey[k]));
            cards.push(card({ title: sec.title }, h("div.grid.c2", fields)));
          }
          cards.push(h("div.notice", icon("info"), h("div", `Showing the essentials. “All options” lists every one of the ${schema.args.length} settings ${draft.script} accepts, read directly from the script, so new options appear automatically after an sd-scripts update.`)));
        } else {
          const groups = {};
          for (const a of schema.args) {
            if (["config_file", "dataset_config", "output_config"].includes(a.key)) continue;
            if (search && !(a.key.includes(search) || (a.help || "").toLowerCase().includes(search))) continue;
            if (onlyChanged && !(a.key in draft.args)) continue;
            (groups[a.group] ||= []).push(a);
          }
          const entries = Object.entries(groups);
          if (!entries.length) cards.push(card(null, empty("search", "No matching options", "Try a different word.")));
          for (const [g, list] of entries) {
            cards.push(card({ title: g === "options" || g === "optional arguments" ? "General" : g, actions: h("span.chip", `${list.length}`) },
              h("div.grid.c2", list.map(fieldFor))));
          }
        }
        if (draft.mode === "simple" || !search) {
          if (byKey.sample_prompts) cards.push(samplesCard());
          cards.push(finishCard());
        }
        cards.push(card({ title: "Extra command-line arguments" },
          h("input.input.mono", { value: draft.extra_args, placeholder: "--timestep_sampling shift --discrete_flow_shift 0.85",
            onchange: (e) => { draft.extra_args = e.target.value; save(); } }),
          h("div.help.small.faint", { style: { marginTop: "8px" } }, "Added after the config file, so they override anything above.")));
        clear(sections, cards);
      }
      drawSections();
      const estCard = card({ title: "How long will it take?" }, estSlot);
      clear(body, head, runCard, estCard, dsCard, sections);
      updateEstimate();
      side();
    }

    await load();
  },
};

