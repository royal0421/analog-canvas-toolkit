// Generic label check: every label's RichText must be byte-identical to what
// the editor's own builder Ws() would produce for the same name string.
// Usage: node check_labels.mjs <project.icproj.json>
import { readFileSync } from "node:fs";
import * as m from "./model.mjs";

// The bundle is minified: the export NAME of the builder changes on every
// redeploy, so find it by running it (2026-09-01: `f` was gone).
function findBuilder() {
  for (const k of Object.keys(m)) {
    try {
      // the builder is the one that turns "M_1" into italic-bold M plus a
      // BOLD subscript 1 -- several exports take a string and return runs
      const r = m[k]("M_1");
      const j = JSON.stringify(r);
      if (r && Array.isArray(r.runs) && r.runs.length === 2
          && r.runs[0].style === "italic" && r.runs[1].style === "subscript"
          && j.includes('"value":"M"') && j.includes('"value":"1"'))
        return m[k];
    } catch { /* not it */ }
  }
  return null;
}
const Ws = findBuilder();
if (!Ws) { console.log("no RichText builder found in model.mjs"); process.exit(2); }
const proj = JSON.parse(readFileSync(process.argv[2], "utf8"));

// The v36 builder splits a name after its FIRST character and keeps every
// other character verbatim, so the string that produced a RichText is simply
// its flattened text -- re-inserting an underscore (what v31 needed) would
// ask the builder for a name nobody wrote.
function toName(rt) {
  let out = "";
  const walk = n => {
    if (n.kind === "text") out += n.value;
    else if (n.children) for (const c of n.children) walk(c);
  };
  for (const r of rt.runs) walk(r);
  return out;
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
  for (const i of doc.instances)          // v36 dropped instance.schematicName
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
