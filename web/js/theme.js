// Theme engine: base + accent (CSS variables in tokens.css) + a decorative header.
// Header patterns are generated as tiny SVG tiles, so they stay crisp at any size.

export const ACCENTS = [
  ["periwinkle", "Periwinkle", "#9381FF"],
  ["lilac", "Lilac", "#C9A4FF"],
  ["rose", "Rose", "#FF94BE"],
  ["peach", "Peach", "#FFB48A"],
  ["butter", "Butter", "#F2D46B"],
  ["mint", "Mint", "#75C97F"],
  ["sage", "Sage", "#A3B59F"],
  ["sky", "Sky", "#7DB7FF"],
  ["cobalt", "Cobalt", "#2F6BFF"],
  ["mono", "Mono", "#17171A"],
];

export const PATTERNS = [
  ["checker", "Checker"], ["grid", "Grid"], ["gingham", "Gingham"], ["dots", "Polka"],
  ["stripes", "Stripes"], ["sparkles", "Sparkles"], ["hearts", "Hearts"], ["waves", "Waves"],
  ["plaid", "Plaid"], ["aurora", "Aurora"], ["solid", "Solid"],
];

const enc = (svg) => `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;
const svg = (w, hgt, body) => `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${hgt}" viewBox="0 0 ${w} ${hgt}">${body}</svg>`;
const star = (cx, cy, r, fill) => {
  const k = r * 0.22;
  return `<path fill="${fill}" d="M${cx} ${cy - r} C${cx + k} ${cy - k} ${cx + k} ${cy - k} ${cx + r} ${cy} C${cx + k} ${cy + k} ${cx + k} ${cy + k} ${cx} ${cy + r} C${cx - k} ${cy + k} ${cx - k} ${cy + k} ${cx - r} ${cy} C${cx - k} ${cy - k} ${cx - k} ${cy - k} ${cx} ${cy - r}Z"/>`;
};
const heart = (x, y, s, fill) =>
  `<path fill="${fill}" transform="translate(${x} ${y}) scale(${s / 24})" d="M12 21s-8-4.9-8-10.6A4.6 4.6 0 0 1 12 7.8a4.6 4.6 0 0 1 8 2.6C20 16.1 12 21 12 21z"/>`;

/** CSS background for a pattern. c1 = background colour, c2 = pattern colour, s = scale (px). */
export function patternCSS(name, c1, c2, s = 28, c3 = null) {
  s = Math.max(8, Math.round(s));
  switch (name) {
    case "solid":
      return { background: c1 };
    case "checker":
      return { background: `${enc(svg(s * 2, s * 2, `<rect width="${s * 2}" height="${s * 2}" fill="${c1}"/><rect width="${s}" height="${s}" fill="${c2}"/><rect x="${s}" y="${s}" width="${s}" height="${s}" fill="${c2}"/>`))}` };
    case "grid":
      return { background: `${enc(svg(s, s, `<rect width="${s}" height="${s}" fill="${c1}"/><path d="M0 0.75H${s}M0.75 0V${s}" stroke="${c2}" stroke-width="1.5"/>`))}` };
    case "gingham": {
      const b = s / 2;
      return { background: `${enc(svg(s, s, `<rect width="${s}" height="${s}" fill="${c1}"/><rect width="${b}" height="${s}" fill="${c2}" opacity=".55"/><rect width="${s}" height="${b}" fill="${c2}" opacity=".55"/>`))}` };
    }
    case "dots": {
      const r = s * 0.16;
      return { background: `${enc(svg(s, s, `<rect width="${s}" height="${s}" fill="${c1}"/><circle cx="${s / 4}" cy="${s / 4}" r="${r}" fill="${c2}"/><circle cx="${s * 0.75}" cy="${s * 0.75}" r="${r}" fill="${c2}"/>`))}` };
    }
    case "stripes":
      return { background: `repeating-linear-gradient(135deg, ${c1} 0 ${s / 2}px, ${c2} ${s / 2}px ${s}px)` };
    case "sparkles": {
      const T = s * 3;
      return { background: `${enc(svg(T, T, `<rect width="${T}" height="${T}" fill="${c1}"/>${star(T * 0.28, T * 0.3, s * 0.55, c2)}${star(T * 0.78, T * 0.72, s * 0.32, c2)}<circle cx="${T * 0.72}" cy="${T * 0.2}" r="${s * 0.07}" fill="${c2}"/><circle cx="${T * 0.2}" cy="${T * 0.82}" r="${s * 0.09}" fill="${c2}"/>`))}` };
    }
    case "hearts": {
      const T = s * 2;
      return { background: `${enc(svg(T, T, `<rect width="${T}" height="${T}" fill="${c1}"/>${heart(T * 0.08, T * 0.06, s * 0.75, c2)}${heart(T * 0.58, T * 0.56, s * 0.75, c2)}`))}` };
    }
    case "waves": {
      const w = s * 2, hh = s;
      return { background: `${enc(svg(w, hh, `<rect width="${w}" height="${hh}" fill="${c1}"/><path d="M0 ${hh / 2} Q ${w / 4} ${hh * 0.15} ${w / 2} ${hh / 2} T ${w} ${hh / 2}" fill="none" stroke="${c2}" stroke-width="${Math.max(2, s / 9)}" stroke-linecap="round"/>`))}` };
    }
    case "plaid": {
      const T = s * 2;
      return { background: `${enc(svg(T, T, `<rect width="${T}" height="${T}" fill="${c1}"/><rect x="${T * 0.1}" width="${T * 0.3}" height="${T}" fill="${c2}" opacity=".45"/><rect y="${T * 0.1}" width="${T}" height="${T * 0.3}" fill="${c2}" opacity=".45"/><path d="M${T * 0.7} 0V${T}M0 ${T * 0.7}H${T}" stroke="${c2}" stroke-width="2" opacity=".8"/>`))}` };
    }
    case "aurora": {
      const c = c3 || c2;
      return { background: `radial-gradient(60% 120% at 12% 10%, ${c2} 0%, transparent 60%), radial-gradient(50% 120% at 85% 90%, ${c} 0%, transparent 62%), radial-gradient(40% 90% at 60% 0%, ${c2} 0%, transparent 60%), ${c1}` };
    }
    default:
      return { background: c1 };
  }
}

// ---- colour maths (hex only, enough for our needs) ----
const toRgb = (hex) => {
  const v = hex.replace("#", "").trim();
  const n = parseInt(v.length === 3 ? v.split("").map((x) => x + x).join("") : v, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};
const toHex = (rgb) => "#" + rgb.map((x) => Math.round(x).toString(16).padStart(2, "0")).join("");
export const mix = (a, b, t) => { const A = toRgb(a), B = toRgb(b); return toHex(A.map((x, i) => x * t + B[i] * (1 - t))); };

export function accentHex(name) {
  const known = ACCENTS.find((a) => a[0] === name);
  if (known) return known[2];
  // a custom accent defined in custom.css
  const v = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim();
  return /^#[0-9a-f]{3,6}$/i.test(v) ? v : ACCENTS[0][2];
}

/** Pattern colours that match the current accent. */
export function accentColors(accent, base) {
  const a = accentHex(accent);
  if (base === "dark") return [mix(a, "#19191C", 0.22), mix(a, "#19191C", 0.42), mix(a, "#19191C", 0.6)];
  return [mix(a, "#FFFFFF", 0.16), mix(a, "#FFFFFF", 0.42), mix(a, "#FFFFFF", 0.7)];
}

export function headerCSS(theme) {
  const hd = theme.header || {};
  if (hd.type === "none") return null;
  if (hd.type === "image" && hd.image) {
    const fit = hd.imageFit || "cover";
    return {
      backgroundImage: `url("${hd.image}")`,
      backgroundSize: fit === "tile" ? `${hd.scale * 6}px auto` : fit,
      backgroundRepeat: fit === "tile" ? "repeat" : "no-repeat",
      backgroundPosition: "center",
    };
  }
  const [c1, c2, c3] = hd.useAccent ? accentColors(theme.accent, theme.base) : [...(hd.colors || []), null];
  return patternCSS(hd.pattern || "checker", c1 || "#eee", c2 || "#fff", hd.scale || 28, c3);
}

let current = null;
export const getTheme = () => current;

export function applyTheme(theme) {
  current = theme;
  const root = document.documentElement;
  root.dataset.base = theme.base || "light";
  root.dataset.accent = theme.accent || "periwinkle";
  root.style.setProperty("--header-h", `${theme.header?.height || 132}px`);
  document.querySelectorAll(".banner").forEach(paintBanner);
}

export function paintBanner(banner) {
  if (!current) return;
  const css = headerCSS(current);
  banner.classList.toggle("none", !css);
  const art = banner.querySelector(".art");
  if (art && css) {
    art.removeAttribute("style");
    Object.assign(art.style, css);
  }
}
