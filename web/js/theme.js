// Theme engine: a glass colour family (default, cool, warm, lilac) in light or dark. The colours live in tokens.css.

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
