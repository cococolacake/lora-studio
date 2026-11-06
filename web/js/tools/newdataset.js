// New dataset: download with gallery-dl (or pick a folder you already have), then copy, filter, number and
// caption everything into a clean dataset, in one click.
import { api } from "../api.js";
import { h, btn, card, chip, modal, toast, toastError, clear, store } from "../dom.js";
import { icon } from "../icons.js";
import { seg, checkEl, pathInput } from "../components.js";
import { taskProgress, watchTask, setFolder } from "./common.js";

const SITES = [["danbooru", "Danbooru"], ["gelbooru", "Gelbooru"], ["safebooru", "Safebooru"], ["e621", "e621"], ["url", "Any link"]];

export function newDataset(ctx, params, root) {
  const o = {
    source: "download", site: "danbooru", tags: "", url: "", limit: 100, folder: "",
    dest: "", trigger: "", min_side: 512, captions: "metadata", character: true, copyright: false, artist: false,
    dupes: true, useForTrain: true,
    ...store.get("newds", {}),
  };
  const save = () => store.set("newds", { ...o, folder: "", dest: "" });
  let gdl = null;
  const srcSlot = h("div");
  const dsSlot = h("div");
  const prog = taskProgress();
  const resultSlot = h("div");
  const go = btn("Make dataset", { icon: "sparkle", kind: "primary", onclick: run });

  root.append(
    ctx.header({ title: "New dataset", subtitle: "Download with gallery-dl or start from a folder; get a clean, captioned dataset in one go.", icon: "download" }),
    h("div.stack",
      card({ title: "1 · Where the images come from" }, srcSlot),
      card({ title: "2 · The dataset" }, dsSlot),
      card(null, h("div.row", h("div.steps-flow", { style: { flex: 1 } },
        h("div.stepc", h("b", "Download"), "gallery-dl saves the posts with their tags"),
        h("div.stepc", h("b", "Filter"), "skips tiny images"),
        h("div.stepc", h("b", "Name & caption"), "DATA_1, DATA_2… with tags as captions"),
        h("div.stepc", h("b", "Check"), "finds look-alikes for you to review")), go),
      h("div", { style: { marginTop: "14px" } }, prog.el)),
      resultSlot));

  // ---- source ----
  async function drawSource() {
    if (o.source === "download" && !gdl) gdl = await api.gdl_status().catch(() => ({ installed: false }));
    const choose = seg([["download", "Download with gallery-dl", "download"], ["folder", "A folder on this PC", "folder"]], o.source, (v) => { o.source = v; save(); drawSource(); });
    if (o.source === "folder") {
      clear(srcSlot, h("div.stack", choose,
        h("div.field", h("label", "Folder to import"), pathInput(o.folder, (v) => { o.folder = v; }, { folder: true, placeholder: "C:/Users/you/gallery-dl/danbooru/some_tag" }),
          h("div.help", "Sub-folders are included. If the images came from gallery-dl with --write-metadata, their tags become captions."))));
      return;
    }
    if (!gdl.installed) {
      clear(srcSlot, h("div.stack", choose, h("div.notice", icon("info"), h("div", { style: { flex: 1 } },
        h("b", "gallery-dl isn't installed yet."), h("div.small", "It's a small download tool that works with hundreds of sites. It installs into LoRA Studio's own folder."),
        h("div", { style: { marginTop: "8px" } }, btn("Install gallery-dl", { icon: "download", size: "sm", kind: "primary", onclick: async (e) => {
          e.currentTarget.disabled = true; e.currentTarget.lastChild.textContent = "Installing…";
          const t = await watchTask(await api.gdl_install());
          if (t?.status === "done") { gdl = null; toast("gallery-dl installed", "", "good", "check"); } else toast("Install failed", t?.lines.at(-1) || "", "bad", "alert");
          drawSource();
        } }))))));
      return;
    }
    const isUrl = o.site === "url";
    clear(srcSlot, h("div.stack", h("div.row", choose, h("div.spacer"), h("span.small.faint", `gallery-dl ${gdl.version}`),
      btn("Site logins", { icon: "key", size: "sm", kind: "ghost", onclick: accounts })),
      h("div.grid.c3",
        h("div.field", h("label", "Site"), h("select.select", { onchange: (e) => { o.site = e.target.value; save(); drawSource(); } },
          SITES.map(([v, l]) => h("option", { value: v, selected: v === o.site }, l)))),
        h("div.field.span2", h("label", isUrl ? "Link" : "Tags"),
          h("input.input" + (isUrl ? ".mono" : ""), { value: isUrl ? o.url : o.tags, placeholder: isUrl ? "https://www.pixiv.net/en/users/12345" : "hatsune_miku solo rating:general",
            oninput: (e) => { if (isUrl) o.url = e.target.value; else o.tags = e.target.value; save(); } }),
          h("div.help", isUrl ? "Any page gallery-dl supports: a pixiv artist, a booru search, a single post…" : "Same syntax as the site's own search. Danbooru allows 2 tags without an account."))),
      h("div.grid.c3",
        h("div.field", h("label", "How many (at most)"), h("input.input.nums", { type: "number", min: 1, value: o.limit, onchange: (e) => { o.limit = Number(e.target.value) || null; save(); } })),
        h("div.field.span2", h("label", "Download into"), pathInput(o.folder, (v) => { o.folder = v; }, { folder: true, placeholder: "Inside LoRA Studio's downloads folder" })))));
  }

  // ---- dataset ----
  function drawDataset() {
    clear(dsSlot, h("div.stack",
      h("div.grid.c3",
        h("div.field.span2", h("label", "Save the dataset in (a new folder)"), pathInput(o.dest, (v) => { o.dest = v; }, { folder: true, placeholder: "C:/datasets/my_character" })),
        h("div.field", h("label", "Trigger word"), h("input.input", { value: o.trigger, placeholder: "optional", oninput: (e) => { o.trigger = e.target.value; save(); } }))),
      h("div.row", { style: { gap: "26px", alignItems: "flex-end" } },
        h("div.field", h("label", "Captions"), seg([["metadata", "From the site's tags"], ["none", "None (auto-tag later)"]], o.captions, (v) => { o.captions = v; save(); drawDataset(); })),
        h("div.field", h("label", "Skip images smaller than"), h("div.row.nowrap", h("input.input.nums", { style: { width: "90px" }, value: o.min_side, onchange: (e) => { o.min_side = Number(e.target.value) || 0; save(); } }), h("span.small.faint", "px")))),
      o.captions === "metadata" ? h("div.row", { style: { gap: "22px" } }, h("span.small.muted", "Include:"),
        checkEl(o.character, (v) => { o.character = v; save(); }, "Character tags"),
        checkEl(o.copyright, (v) => { o.copyright = v; save(); }, "Series tags"),
        checkEl(o.artist, (v) => { o.artist = v; save(); }, "Artist tags")) : null,
      h("div.row", { style: { gap: "22px" } }, h("span.small.muted", "Then:"),
        checkEl(o.dupes, (v) => { o.dupes = v; save(); }, "Look for duplicates"),
        checkEl(o.useForTrain, (v) => { o.useForTrain = v; save(); }, "Use it on the Train page"))));
  }

  async function run() {
    const download = o.source === "download";
    if (!o.dest) return toast("Choose where to save the dataset", "", "", "folder");
    let url = null, downloadDir = o.folder;
    try {
      if (download) {
        url = o.site === "url" ? o.url.trim() : await api.gdl_build_url(o.site, o.tags);
        if (!url) return toast("Enter tags or a link first", "", "", "info");
        downloadDir ||= await api.gdl_default_dir(o.site === "url" ? "download" : `${o.site} ${o.tags}`);
      } else if (!o.folder) return toast("Choose the folder to import", "", "", "folder");
    } catch (e) { return toastError(e); }
    go.disabled = true;
    clear(resultSlot);
    try {
      const id = await api.make_dataset({ url, download_dir: downloadDir, limit: download ? o.limit : null, source: download ? null : o.folder,
        dest: o.dest, trigger: o.trigger, min_side: o.min_side, captions: o.captions, character: o.character, copyright: o.copyright, artist: o.artist });
      const t = await watchTask(id, (s) => prog.set(s));
      if (t?.status !== "done") { clear(resultSlot, card({ title: "That didn't work" }, h("pre.code", (t?.lines || []).slice(-14).join("\n")))); go.disabled = false; return; }
      const r = t.result;
      setFolder(r.dest);
      if (o.useForTrain && ctx.draft?.dataset) {
        ctx.draft.dataset.subsets = [{ image_dir: r.dest, num_repeats: ctx.draft.dataset.subsets?.[0]?.num_repeats || 2 }];
        if (o.trigger) ctx.draft.lora_info = { ...(ctx.draft.lora_info || {}), trigger: o.trigger };
        ctx.saveDraft(ctx.draft);
      }
      toast("Dataset ready", `${r.copied} images in ${r.dest.split("/").pop()}`, "good", "sparkle", 8000);
      clear(resultSlot, card({ title: "Done" },
        h("div.grid.c4",
          h("div.stat", h("div.k", "Images"), h("div.v", String(r.copied))),
          h("div.stat", h("div.k", "With captions"), h("div.v", String(r.captioned))),
          h("div.stat", h("div.k", "Skipped (small)"), h("div.v", String(r.too_small))),
          h("div.stat", h("div.k", "Unreadable"), h("div.v", String(r.unreadable)))),
        h("div.row", { style: { marginTop: "16px" } },
          o.useForTrain && ctx.draft ? chip("Set as the Train page's dataset", "accent", "check") : null, h("div.spacer"),
          btn("Health check", { icon: "circleCheck", onclick: () => ctx.go("dataset", { tool: "health" }) }),
          btn("Open in Images & tags", { icon: "tag", kind: "primary", onclick: () => ctx.go("dataset", { tool: "viewer" }) }))));
      if (o.dupes) ctx.go("dataset", { tool: "dupes", autorun: true });
    } catch (e) { toastError(e); }
    go.disabled = false;
  }

  async function accounts() {
    let a;
    try { a = await api.gdl_accounts(); } catch (e) { return toastError(e); }
    const vals = structuredClone(a.values);
    const body = h("div.stack",
      h("p.small.muted", { style: { margin: 0 } }, "Saved on this PC only, in LoRA Studio's data folder. They're never included in backups or uploaded anywhere."),
      Object.entries(a.sites).map(([site, meta]) => h("div.issue", h("div.stack.sm",
        h("div.row", h("b", meta.label), h("div.spacer"),
          site === "pixiv" ? btn("Get token", { icon: "key", size: "sm", kind: "ghost", onclick: () => api.gdl_pixiv_token().catch(toastError) }) : null),
        h("div.grid.c2", meta.fields.map(([k, label]) => h("div.field", h("label", label),
          h("input.input.mono", { type: "password", value: vals[site][k] || "", placeholder: "not set", oninput: (e) => { vals[site][k] = e.target.value; } })))),
        h("div.help", meta.help)))),
      h("div.issue", h("div.stack.sm", h("b", "Other sites that need you to be logged in"),
        h("div.field", h("label", "Use the cookies from this browser"),
          h("select.select", { onchange: (e) => { vals.cookies_browser = e.target.value; } },
            [["", "Don't use browser cookies"], ["firefox", "Firefox"], ["chrome", "Chrome"], ["edge", "Edge"]].map(([v, l]) => h("option", { value: v, selected: v === vals.cookies_browser }, l)))),
        h("div.help", "Log into the site in that browser first. Firefox works most reliably; newer Chrome and Edge versions often block this."))));
    const ok = await modal("Site logins for gallery-dl", body, [{ label: "Cancel", kind: "ghost", value: false }, { label: "Save", kind: "primary", value: true }]);
    if (!ok) return;
    try {
      for (const site of Object.keys(a.sites)) await api.gdl_save_account(site, vals[site]);
      await api.gdl_set_cookies_browser(vals.cookies_browser || "");
      toast("Logins saved", "", "good", "key");
    } catch (e) { toastError(e); }
  }

  drawSource();
  drawDataset();
}
