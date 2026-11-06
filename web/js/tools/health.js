// Dataset health check: caption/image problems + bucket & step estimate.
import { api } from "../api.js";
import { h, btn, card, chip, stat, toastError, clear } from "../dom.js";
import { icon } from "../icons.js";
import { datasetEditor } from "../components.js";
import { thumbUrl } from "../media.js";

const ISSUES = {
  unreadable: ["Unreadable images", "These files couldn't be opened. sd-scripts will crash on them, so remove or re-save them."],
  shared_caption: ["Two images share one caption", "Files like a.png and a.jpg both read a.txt. Rename one so each image gets its own caption."],
  missing_caption: ["Missing captions", "No caption file was found, so these images train with an empty caption."],
  empty_caption: ["Empty captions", "The caption file exists but has nothing in it."],
  no_trigger: ["Trigger word missing", "These captions don't contain your trigger word."],
  too_small: ["Small images", "Smaller than the minimum side length, so they get upscaled and may look soft."],
  extreme_aspect: ["Very wide or tall", "Extreme aspect ratios land in edge buckets and can train poorly."],
  orphan_caption: ["Captions without images", "Leftover caption files. They're ignored, but worth tidying."],
};
const SEV_ICON = { error: "circleX", warn: "alert", info: "info" };

export function health(ctx, params, root) {
    root.append(ctx.header({ title: "Dataset health check", subtitle: "Catch caption and image problems before a long run does.", icon: "image" }));

    const draft = ctx.draft || {};
    const ds = draft.dataset || { subsets: [{ image_dir: "", num_repeats: 1 }], resolution: [1024, 1024], batch_size: 2, enable_bucket: true, min_bucket_reso: 512, max_bucket_reso: 2048, bucket_reso_steps: 64, caption_extension: ".txt" };
    ds.subsets ||= [{ image_dir: "", num_repeats: 1 }];
    const opts = {
      trigger: draft.lora_info?.trigger || draft.trigger || (draft.dataset?.subsets?.[0]?.class_tokens) || "",
      epochs: draft.args?.max_train_epochs || 10,
      grad: draft.args?.gradient_accumulation_steps || 1,
      min_side: Math.round(Math.min(...(ds.resolution || [1024, 1024])) / 2),
    };
    const sync = () => { if (ctx.draft) { ctx.draft.dataset = ds; ctx.draft.trigger = opts.trigger; ctx.saveDraft(ctx.draft); } };

    const results = h("div.stack");
    const inp = (k, ph, type = "text") => h("input.input" + (type === "number" ? ".nums" : ""), { value: opts[k], placeholder: ph, type,
      onchange: (e) => { opts[k] = type === "number" ? Number(e.target.value) : e.target.value.trim(); sync(); } });

    const runBtn = btn("Run health check", { icon: "circleCheck", kind: "primary", onclick: run });
    root.append(h("div.stack",
      card({ title: "What to check", actions: ctx.draft ? chip("Shared with the Train page", "accent", "wand") : null },
        datasetEditor(ds, sync, { compact: true }),
        h("div.grid.c4", { style: { marginTop: "16px" } },
          h("div.field", h("label", "Trigger word"), inp("trigger", "e.g. mychar")),
          h("div.field", h("label", "Smallest OK side (px)"), inp("min_side", "512", "number")),
          h("div.field", h("label", "Epochs"), inp("epochs", "10", "number")),
          h("div.field", h("label", "Gradient accumulation"), inp("grad", "1", "number"))),
        h("div.row", { style: { marginTop: "16px" } }, h("div.spacer"), runBtn)),
      results));

    async function run() {
      if (!ds.subsets.some((x) => (x.image_dir || "").trim())) {
        clear(results, h("div.notice.warn", icon("folder"), "Add an image folder first."));
        return;
      }
      runBtn.disabled = true;
      clear(results, h("div.loading", h("span.spin"), "Looking through your images…"));
      try {
        const r = await api.health_check({ ...ds, trigger: opts.trigger, epochs: opts.epochs, grad_accum: opts.grad, min_side: opts.min_side });
        show(r);
      } catch (e) { toastError(e); clear(results); }
      runBtn.disabled = false;
    }

    function show(r) {
      const missing = r.folders.filter((f) => !f.exists);
      const issues = r.issues.filter((i) => i.count).sort((a, b) => ["error", "warn", "info"].indexOf(a.severity) - ["error", "warn", "info"].indexOf(b.severity));
      const tiles = h("div.grid.c4",
        stat("Images", r.total_images), stat("Unique tags", r.unique_tags),
        stat("Steps / epoch", r.steps.steps_per_epoch), stat("Total steps", r.steps.total_steps, `· ${r.steps.epochs} ep`));

      const issueCards = issues.map((i) => {
        const [title, desc] = ISSUES[i.id] || [i.id, ""];
        const bodyEl = h("div.body.hidden");
        let loaded = false;
        const toggle = () => {
          bodyEl.classList.toggle("hidden");
          if (loaded) return;
          loaded = true;
          const grid = h("div.thumbs");
          bodyEl.append(grid);
          for (const it of i.items.slice(0, 60)) {
            const t = h("div.thumb", { title: it.path }, h("div.cap", it.note ? `${it.name} · ${it.note}` : it.name));
            grid.append(t);
            if (/\.(png|jpe?g|webp|bmp)$/i.test(it.name)) {
              t.prepend(h("img", { src: thumbUrl(it.path, 200), loading: "lazy" }));
            } else t.prepend(h("div", { style: { display: "grid", placeItems: "center", height: "100%", color: "var(--text-3)" } }, icon("file")));
          }
          if (i.count > 60) bodyEl.append(h("p.tiny.faint", `…and ${i.count - 60} more`));
        };
        return h("div.issue",
          h("div.issue-head", { onclick: toggle },
            h("div.sev." + i.severity, icon(SEV_ICON[i.severity])),
            h("div.main-col", { style: { flex: 1 } }, h("b", title), h("div.small.muted", desc)),
            chip(String(i.count), i.severity === "error" ? "bad" : i.severity === "warn" ? "warn" : "info"),
            icon("down")),
          bodyEl);
      });

      const maxB = Math.max(1, ...r.buckets.map((b) => b.count));
      clear(results,
        missing.length ? h("div.notice.bad", icon("alert"), `Folder not found: ${missing.map((m) => m.image_dir || "(empty)").join(", ")}`) : null,
        tiles,
        card({ title: "Issues", actions: issues.length ? null : chip("All clear", "good", "circleCheck") },
          issues.length ? h("div.stack.sm", issueCards)
            : h("div.notice.good", icon("circleCheck"), "No problems found. Every image has a readable caption.")),
        h("div.grid.c2",
          card({ title: "Buckets" }, r.buckets.length ? h("div.bars", r.buckets.slice(0, 14).map((b) =>
            h("div.bar-row", h("span.mono.small", `${b.w}×${b.h}`), h("div.b", h("i", { style: { width: `${(b.count / maxB) * 100}%` } })), h("span.nums.small", String(b.count)))))
            : h("p.muted.small", "No images.")),
          card({ title: "Most common tags" }, h("div.row", { style: { gap: "6px" } },
            r.top_tags.map(([t, n]) => h("span.tag", t, h("b", String(n))))))),
        card({ title: "Folders" }, h("div.list", r.folders.map((f) => h("div.list-row",
          h("div.ic", icon("folder")),
          h("div.main-col", h("div.title.mono", { style: { fontSize: "13px" } }, f.image_dir || "(empty)"),
            h("div.meta", f.exists ? `${f.images} images · ${f.captions} captions · ${f.repeats} repeats → ${f.batches} batches/epoch` : "Not found")))))));
    }
}
