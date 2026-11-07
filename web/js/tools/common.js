// Shared bits for the dataset tools.
import { api } from "../api.js";
import { h, btn, store, toastError, clear } from "../dom.js";
import { icon } from "../icons.js";
import { pathInput } from "../components.js";

export function getFolder(ctx) {
  return store.get("dsFolder") || ctx.draft?.dataset?.subsets?.find((s) => s.image_dir)?.image_dir || "";
}
export const setFolder = (f) => store.set("dsFolder", f);

/** Folder picker row: path box + Load + quick chips for the Train page's dataset folders. */
export function folderBar(ctx, value, onLoad, { button = "Load", icon: ic = "folder" } = {}) {
  let cur = value;
  // A notice when this folder is used by the running training (or a queued one).
  const busy = h("div");
  const checkBusy = async (f) => {
    clear(busy);
    if (!f) return;
    try {
      const u = await api.ds_in_use(f);
      if (u.running) clear(busy, h("div.notice.warn", icon("alert"),
        `The training that's running (${u.running}) uses this folder. Moving, renaming, cropping or resizing its images is paused until it finishes. Caption edits are fine; they apply to the next training.`));
      else if (u.queued.length) clear(busy, h("div.notice", icon("info"),
        `A queued training (${u.queued.join(", ")}) uses this folder; it will train on the folder as it is when it starts.`));
    } catch { /* no notice */ }
  };
  const go = () => { if (!cur) return; setFolder(cur); onLoad(cur); checkBusy(cur); };
  checkBusy(cur);
  const input = pathInput(cur, (v) => { cur = v; }, { folder: true, placeholder: "C:/datasets/my_character" });
  input.querySelector("input").addEventListener("keydown", (e) => { if (e.key === "Enter") { cur = e.target.value.trim(); go(); } });
  const trainFolders = (ctx.draft?.dataset?.subsets || []).map((s) => s.image_dir).filter(Boolean).filter((f) => f !== cur);
  return h("div.stack.sm",
    h("div.row.nowrap", h("div", { style: { flex: 1 } }, input), btn(button, { icon: ic, kind: "primary", onclick: () => { cur = input.querySelector("input").value.trim(); go(); } })),
    trainFolders.length ? h("div.row", h("span.tiny.faint", "From Train:"), trainFolders.map((f) =>
      h("button.chip.accent", { style: { border: 0, cursor: "pointer" }, onclick: () => { cur = f; input.querySelector("input").value = f; go(); } }, f.split(/[\\/]/).pop()))) : null,
    busy);
}

/** Progress block for a worker/background task. Returns {el, set(snapshot)}. */
export function taskProgress() {
  const bar = h("div.progress", h("i"));
  const msg = h("div.small.muted");
  const el = h("div.stack.sm.hidden", bar, msg);
  return {
    el,
    set(t) {
      el.classList.remove("hidden");
      const p = t?.progress;
      const pct = p?.total ? (p.n / p.total) * 100 : 0;
      bar.firstChild.style.width = `${t?.status === "done" ? 100 : pct}%`;
      bar.classList.toggle("idle", t?.status !== "running");
      msg.textContent = t?.status === "failed" ? (t.lines.at(-1) || "Failed")
        : p?.msg || (t?.status === "done" ? "Done" : p?.total ? `${p.n} of ${p.total}` : "Starting…");
    },
    hide() { el.classList.add("hidden"); },
  };
}

/** Poll a task until it finishes. onTick(snapshot) each time. */
export function watchTask(id, onTick) {
  return new Promise((resolve) => {
    let lines = [];
    const tick = async () => {
      try {
        const t = await api.task(id, lines.length);
        if (!t) return resolve(null);
        lines = lines.concat(t.lines);
        t.lines = lines;
        onTick?.(t);
        if (t.status === "running") setTimeout(tick, 500); else resolve(t);
      } catch (e) { toastError(e); resolve(null); }
    };
    tick();
  });
}

/** Shown when a worker reports a missing package in the sd-scripts venv. */
export function missingNotice(pkg, onInstalled) {
  const allowed = ["timm", "transformers", "huggingface-hub", "numpy", "pillow"];
  const note = h("div.notice.warn", icon("alert"), h("div", { style: { flex: 1 } },
    h("b", `Your sd-scripts venv is missing “${pkg}”.`),
    h("div.small", allowed.includes(pkg) ? "LoRA Studio can install it there for you (it doesn't affect training)." : "That's a core package, so this may be the wrong venv. Check the sd-scripts page."),
    allowed.includes(pkg) ? h("div", { style: { marginTop: "8px" } }, btn(`Install ${pkg}`, { icon: "download", size: "sm", onclick: async (e) => {
      e.currentTarget.disabled = true;
      e.currentTarget.textContent = "Installing…";
      const t = await watchTask(await api.install_package(pkg));
      if (t?.status === "done") { note.remove(); onInstalled?.(); } else note.querySelector(".small").textContent = (t?.lines || []).slice(-3).join(" ");
    } })) : null));
  return note;
}
