// App shell: rail navigation, side panel, header banner, routing, background polling.
import { api } from "./api.js";
import { h, clear, toast, toastError, store, btn, modal } from "./dom.js";
import { icon, logo } from "./icons.js";
import { applyTheme, paintBanner } from "./theme.js";
import { setNative } from "./components.js";
import { setMedia } from "./media.js";

import home from "./pages/home.js";
import train from "./pages/train.js";
import queue from "./pages/queue.js";
import runs from "./pages/runs.js";
import dataset from "./pages/dataset.js";
import sdscripts from "./pages/sdscripts.js";
import swarmPage from "./pages/swarm.js";
import settingsPage from "./pages/settings.js";

const PAGES = [home, train, queue, runs, dataset, swarmPage, sdscripts];
const ALL = [...PAGES, settingsPage];

const $rail = document.getElementById("rail");
const $side = document.getElementById("side");
const $main = document.getElementById("main");

const ctx = {
  boot: null,          // settings, sd status, scripts...
  state: null,         // trainer state (polled)
  draft: store.get("draft", null),   // the Train form, shared with the Dataset page
  page: null,
  params: {},
  _stateFns: [],
  _cleanup: [],

  go(id, params = {}) {
    const page = ALL.find((p) => p.id === id) || home;
    ctx._stateFns = [];
    ctx._cleanup.forEach((f) => { try { f(); } catch { /* ignore */ } });
    ctx._cleanup = [];
    ctx.page = page;
    ctx.params = params;
    store.set("page", id);
    renderRail();
    clear($side);
    const inner = h("div.main-inner.page");
    clear($main, inner);
    $main.scrollTop = 0;
    try {
      const out = page.mount(ctx, params, inner);
      if (out instanceof Promise) out.catch(toastError);
    } catch (e) { toastError(e); console.error(e); }
  },

  /** Draw the header banner at the top of a page. */
  header({ title, subtitle = "", icon: ic = "sparkle", actions = [] }) {
    const banner = h("header.banner", h("div.art"),
      h("div.sticker", h("div.chip-icon", icon(ic)), h("div", h("h1", title), subtitle ? h("p", subtitle) : null)),
      actions.length ? h("div.banner-actions", actions) : null);
    paintBanner(banner);
    return banner;
  },

  side(...kids) { clear($side, kids); },

  onState(fn) { ctx._stateFns.push(fn); if (ctx.state) fn(ctx.state); },
  onLeave(fn) { ctx._cleanup.push(fn); },

  saveDraft(d) { ctx.draft = d; store.set("draft", d); },

  async refreshBoot() {
    ctx.boot = await api.bootstrap();
    document.documentElement.dataset.platform = ctx.boot.platform || "windows";
    setNative(ctx.boot.native);
    setMedia(ctx.boot.media);
    applyTheme(ctx.boot.settings.theme);
    return ctx.boot;
  },

  async saveSettings(patch) {
    const s = await api.save_settings(patch);
    ctx.boot.settings = s;
    if (patch.theme) applyTheme(s.theme);
    return s;
  },
};
window.ctx = ctx; // handy in the dev tools console

function renderRail() {
  const running = ctx.state?.current;
  const item = (p) => {
    const b = h("button.rail-btn", { onclick: () => ctx.go(p.id), class: ctx.page?.id === p.id ? "active" : "" },
      icon(p.icon), h("span.tip", p.label));
    if (p.id === "queue" && running) b.append(h("span.badge-dot"));
    return b;
  };
  const base = ctx.boot?.settings?.theme?.base || "light";
  clear($rail,
    h("div.logo", { title: "LoRA Studio" }, logo()),
    h("div.nav", PAGES.map(item)),
    h("div.bottom",
      ctx.update?.newer ? h("button.rail-btn.update-btn", { onclick: showUpdate },
        icon("download"), h("span.badge-dot"), h("span.tip", `Update available: ${ctx.update.latest.tag}`)) : null,
      h("button.rail-btn", {
        onclick: async () => {
          const t = { ...ctx.boot.settings.theme, base: base === "dark" ? "light" : "dark" };
          await ctx.saveSettings({ theme: t });
          renderRail();
        },
      }, icon(base === "dark" ? "sun" : "moon"), h("span.tip", base === "dark" ? "Light mode" : "Dark mode")),
      item(settingsPage)));
}

// A newer LoRA Studio on GitHub? Shown as a small download button in the rail.
async function checkUpdate() {
  try {
    ctx.update = await api.app_update();
    renderRail();
    const tag = ctx.update?.newer && ctx.update.latest.tag;
    if (tag && store.get("updateToast") !== tag) {
      store.set("updateToast", tag);
      toast("A new LoRA Studio is out", `${tag} is ready to download.`, "good", "download", 9000);
    }
  } catch { /* offline: no notice */ }
}

async function showUpdate() {
  const u = ctx.update?.latest;
  if (!u) return;
  const win = ctx.boot.platform === "windows";
  const go = await modal(`LoRA Studio ${u.tag} is available`, h("div.stack.sm",
    h("p", { style: { margin: 0 } }, `You have ${ctx.update.current}. The new version is ${u.tag}${u.prerelease ? " (pre-release)" : ""}.`),
    h("p.small.muted", { style: { margin: 0 } }, win
      ? "To update: download the zip from the release page and unzip it over your LoRA Studio folder (keep the .venv folder), or Pull in GitHub Desktop if you use it."
      : "To update: run git pull in the LoRA Studio folder (or unzip the new version over it), then ./install.sh again.")),
    [{ label: "Later", kind: "ghost", value: false }, { label: "See what's new", kind: "primary", value: true }]);
  if (go) api.open_url(u.url).catch(toastError);
}

let lastEventT = Date.now() / 1000;
async function poll() {
  try {
    const st = await api.state();
    const wasRunning = !!ctx.state?.current;
    ctx.state = st;
    if (wasRunning !== !!st.current) renderRail();
    for (const ev of st.events || []) {
      if (ev.t <= lastEventT) continue;
      lastEventT = ev.t;
      const map = {
        done: ["Training finished", "good", "circleCheck"],
        failed: ["Training failed", "bad", "circleX"],
        stopped: ["Training stopped", "", "stop"],
      };
      const [title, kind, ic] = map[ev.type] || ["Training update", "", "bell"];
      const t = toast(title, ev.name, kind, ic, 12000);
      t.querySelector(":scope > div:nth-child(2)").append(h("div", btn("View run", { size: "sm", kind: "ghost", onclick: () => { t.remove(); ctx.go("runs", { run: ev.run }); } })));
    }
    ctx._stateFns.forEach((fn) => { try { fn(st); } catch (e) { console.error(e); } });
  } catch (e) { console.warn("poll failed", e); }
  setTimeout(poll, ctx.state?.current ? 1000 : 2000);
}

async function start() {
  try {
    await ctx.refreshBoot();
  } catch (e) {
    clear($main, h("div.main-inner", h("div.card", h("h3", "Couldn't reach the backend"), h("p.muted", String(e)))));
    return;
  }
  ctx.state = await api.state().catch(() => null);
  const first = !ctx.boot.sd.configured || !ctx.boot.sd.valid ? "sdscripts" : (store.get("page") || "home");
  ctx.go(first);
  poll();
  setTimeout(checkUpdate, 4000);   // after the app has settled; quietly does nothing offline
}

start();
