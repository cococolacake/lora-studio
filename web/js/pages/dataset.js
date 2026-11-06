// Dataset tools router. Each tool lives in js/tools/.
import { h } from "../dom.js";
import { icon } from "../icons.js";
import { health } from "../tools/health.js";
import { viewer } from "../tools/viewer.js";
import { dupes } from "../tools/dupes.js";
import { rename } from "../tools/rename.js";
import { resize } from "../tools/resize.js";
import { newDataset } from "../tools/newdataset.js";

const TOOLS = [
  ["new", "New dataset", "download", newDataset],
  ["viewer", "Images & tags", "tag", viewer],
  ["health", "Health check", "circleCheck", health],
  ["dupes", "Duplicates", "dup", dupes],
  ["resize", "Crop & resize", "crop", resize],
  ["rename", "Rename", "rename", rename],
];

export default {
  id: "dataset", label: "Dataset", icon: "image",

  mount(ctx, params, root) {
    const tool = TOOLS.find((t) => t[0] === params.tool) || TOOLS[1];
    ctx.side(h("h2", "Dataset"),
      TOOLS.map(([id, label, ic]) => h("button.side-item", { class: id === tool[0] ? "active" : "", onclick: () => ctx.go("dataset", { tool: id }) },
        icon(ic), h("span", label))));
    tool[3](ctx, params, root);
  },
};
