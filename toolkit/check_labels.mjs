// Generic label check: every label's RichText must be byte-identical to what
// the editor's own builder Ws() would produce for the same name string.
// Usage: node check_labels.mjs <project.icproj.json>
import { readFileSync } from "node:fs";
import { buildName } from "./model-adapter.mjs";

const Ws = buildName;                 // discovered "name -> RichText" builder
const proj = JSON.parse(readFileSync(process.argv[2], "utf8"));

// flatten RichText back into the "base_sub" string that produced it
function toName(rt) {
  let base = "", sub = "", inSub = false;
  const walk = (n, s) => {
    if (n.kind === "text") { if (s) sub += n.value; else base += n.value; }
    else if (n.kind === "span") {
      const s2 = s || n.style === "subscript";
      if (n.style === "subscript") inSub = true;
      for (const c of n.children) walk(c, s2);
    }
  };
  for (const r of rt.runs) walk(r, false);
  return inSub ? base + "_" + sub : base;
}

let checked = 0, bad = 0;
const report = (what, rt) => {
  const nm = toName(rt);
  const want = Ws(nm);
  const same = JSON.stringify(rt.runs) === JSON.stringify(want.runs);
  checked++;
  if (!same) {
    bad++;
    console.log("DIFFER " + what + "  (name '" + nm + "')");
    console.log("   mine:", JSON.stringify(rt.runs));
    console.log("   app :", JSON.stringify(want.runs));
  } else {
    console.log("MATCH  " + what + "  (name '" + nm + "')");
  }
};

for (const doc of proj.documents) {
  for (const i of doc.instances)
    if (i.schematicName) report("instance " + i.id, i.schematicName);
  for (const a of doc.annotations) {
    if (a.formatOverride) report("annotation " + a.id + " (formatOverride)", a.formatOverride);
    else if (a.content) report("annotation " + a.id + " (content)", a.content);
  }
  for (const o of doc.drafting.objects)
    if (o.kind === "text" && o.content) report("drafting " + o.id, o.content);
}
console.log("\n" + (bad === 0
  ? `All ${checked} labels are byte-identical to the editor's own builder.`
  : `${bad} of ${checked} labels differ.`));
if (bad) process.exit(1);
