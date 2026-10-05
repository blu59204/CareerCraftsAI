import { readFileSync, writeFileSync } from "node:fs";
import postcss from "postcss";

const src = "node_modules/@copilotkit/react-core/dist/v2/index.css";
const dst = "src/app/(app)/copilot/copilot-v2.css";

const root = postcss.parse(readFileSync(src, "utf-8"));

function hoistLayers(node) {
  for (const child of [...node.nodes ?? []]) {
    if (child.type === "atrule" && child.name === "layer") {
      // Move the layer's children up in its place, preserving order.
      const index = node.index(child);
      for (const [i, grand] of [...child.nodes ?? []].entries()) {
        node.insertAfter(node.nodes[index + i - 1] ?? child, grand);
      }
      // insertAfter placed them after child; recompute: simpler—remove and re-append at index.
      child.remove();
      // Re-run to fix any nesting order issues.
    } else {
      hoistLayers(child);
    }
  }
}

// Robust approach: recursively unwrap all @layer atrules anywhere.
function unwrap(rootNode) {
  let found = true;
  while (found) {
    found = false;
    const stack = [rootNode];
    while (stack.length) {
      const n = stack.pop();
      for (const c of [...(n.nodes ?? [])]) {
        if (c.type === "atrule" && c.name === "layer") {
          const parent = c.parent;
          const idx = parent.index(c);
          for (const g of [...(c.nodes ?? [])]) {
            parent.insertAfter(parent.nodes[idx], g);
          }
          c.remove();
          found = true;
        } else {
          stack.push(c);
        }
      }
    }
  }
}

unwrap(root);
const header = `/* Vendored from @copilotkit/react-core/dist/v2/index.css with @layer wrappers
   stripped (Tailwind's PostCSS plugin rejects foreign @layer usage).
   Regenerate: bump @copilotkit/react-core, then re-run scripts/vendor-copilot-css.mjs. */\n`;
writeFileSync(dst, header + root.toString() + "\n");
console.log("wrote", dst, root.toString().length, "chars");
