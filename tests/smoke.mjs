// Browser smoke test: open every page and dataset tool, load a small dataset, and fail on any
// JavaScript error. Run by GitHub Actions; locally: start LoRA Studio with --browser, then
//   SMOKE_URL=http://127.0.0.1:8765 SMOKE_DATASET=/path/to/images node tests/smoke.mjs
import { chromium } from "playwright";

const url = process.env.SMOKE_URL || "http://127.0.0.1:8765";
const dataset = process.env.SMOKE_DATASET;
const errors = [];
let where = "start";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.on("pageerror", (e) => errors.push(`[${where}] ${e.message}`));
page.on("console", (m) => { if (m.type() === "error" && !/Failed to load resource/.test(m.text())) errors.push(`[${where}] ${m.text()}`); });

const go = async (name, js, wait = 900) => { where = name; await page.evaluate(js); await page.waitForTimeout(wait); };
await page.goto(url);
await page.waitForTimeout(1500);

for (const p of ["home", "train", "queue", "runs", "swarm", "sdscripts"]) await go(p, `ctx.go(${JSON.stringify(p)})`);
for (const s of ["appearance", "training", "paths", "about"]) await go(`settings/${s}`, `ctx.go("settings", { section: ${JSON.stringify(s)} })`);
for (const t of ["new", "viewer", "health", "dupes", "resize", "rename"]) await go(`dataset/${t}`, `ctx.go("dataset", { tool: ${JSON.stringify(t)} })`);

if (dataset) {
  where = "viewer with images";
  await page.evaluate(`ctx.go("dataset", { tool: "viewer" })`);
  await page.waitForTimeout(500);
  const input = await page.$("#main input.input.mono");
  await input.fill(dataset);
  await input.dispatchEvent("change");
  await page.click('#main button:has-text("Load")');
  await page.waitForTimeout(1500);
  const tiles = await page.$$(".vtile");
  if (!tiles.length) errors.push("[viewer with images] no images were shown");
  else { await tiles[0].click(); await page.waitForTimeout(400); }
  for (const t of ["health", "dupes", "resize", "rename"]) await go(`dataset/${t} with folder`, `ctx.go("dataset", { tool: ${JSON.stringify(t)} })`);
}

await browser.close();
if (errors.length) {
  console.error("Smoke test found problems:\n" + errors.join("\n"));
  process.exit(1);
}
console.log("Smoke test passed: every page opened without errors.");
