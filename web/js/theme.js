// Theme engine: a glass colour family (default, cool, warm, lilac) in light or dark. The colours live in tokens.css.
// A CSS theme (a .css file dropped into Settings > Appearance) can go on top; see csstheme.js.
import { api } from "./api.js";

let current = null;
export const getTheme = () => current;

export function applyTheme(theme) {
  current = theme;
  const root = document.documentElement;
  const base = theme.base || "light";
  let family = theme.family || "default";
  if (family === "lilac" && base === "dark") family = "cool";   // Lilac is light only
  root.dataset.base = base;
  root.dataset.style = "glass";
  root.dataset.family = family;
  root.dataset.glass = ["full", "off"].includes(theme.glass) ? theme.glass : "efficient";
  root.dataset.font = theme.font === "system" ? "system" : "geist";
  applyCss(theme.css || "");
}

// ---- CSS theme: its text goes in a <style> just before custom.css, so custom.css still wins ----
let cssName = null, cssToken = 0;
const cssCache = new Map();

/** Drop a cached CSS theme (after it was replaced or deleted) so it loads fresh next time. */
export function forgetCssTheme(name) {
  cssCache.delete(name);
  if (cssName === name) cssName = null;
}

async function applyCss(name) {
  if (name === cssName) return;
  cssName = name;
  const token = ++cssToken;
  let text = "";
  if (name) {
    if (!cssCache.has(name)) {
      try { cssCache.set(name, await api.css_theme(name)); } catch { if (token === cssToken) cssName = null; return; }
    }
    text = cssCache.get(name);
  }
  if (token !== cssToken) return;   // another theme was picked while this one loaded
  let el = document.getElementById("css-theme");
  if (!text) el?.remove();
  else {
    if (!el) {
      el = document.createElement("style");
      el.id = "css-theme";
      const custom = document.querySelector('link[href$="custom.css"]');
      if (custom) custom.before(el); else document.head.append(el);
    }
    el.textContent = text;
  }
  window.dispatchEvent(new Event("cssthemechange"));
}

/** Page headers are plain title bars now (the patterned headers were removed). */
export function paintBanner(banner) {
  banner.classList.add("none");
}

/** While a training runs, switch to the solid look (if the theme asks for it). */
export function setTrainingLook(training) {
  const root = document.documentElement;
  const on = !!training && current?.simpleWhileTraining !== false && root.dataset.glass !== "off";
  if (on) root.dataset.simple = ""; else delete root.dataset.simple;
  return on;
}
