import { readFileSync } from "node:fs";
import * as m from "./model.mjs";
import vm from "node:vm";

// Exports are called blindly while searching; one of them loops forever on
// a (string, string) argument since v58, so each probe call gets 1 s.
const call = (fn, ...a) =>
  vm.runInNewContext("f(...a)", { f: fn, a }, { timeout: 1000 });

// The bundle is minified, so the export NAMES change on every redeploy
// (2026-08-30: schema `a`, factory `n`; 2026-09-01: schema `s`, factory `i`).
// Find them the way refresh_model.py does -- by running them -- instead of
// hard-coding letters that go stale.
function findFactory() {
  for (const k of Object.keys(m)) {
    try {
      const o = call(m[k], "probe-id", "Probe");
      if (o && Array.isArray(o.documents) && typeof o.schemaVersion === "number")
        return k;
    } catch { /* not it */ }
  }
  return null;
}

function findSchema(probe) {
  for (const k of Object.keys(m)) {
    const v = m[k];
    if (v && typeof v.safeParse === "function" && v.safeParse(probe).success)
      return k;
  }
  return null;
}

// refresh_model.py already found and verified the factory and schema and
// recorded them in model-adapter.mjs.  Use those (one call each, no blind
// probing: the probe loop costs ~2 s per figure, 1 s of it the v58 export
// that never returns) and fall back to the search only when the adapter is
// missing or no longer agrees with the bundle.
async function fromAdapter() {
  try {
    const a = await import("./model-adapter.mjs");
    const k = name => Object.keys(m).find(key => m[key] === a[name]);
    const p = a.createProject("probe-id", "Probe");
    if (p && Array.isArray(p.documents) && a.projectSchema?.safeParse(p).success)
      return [k("createProject"), k("projectSchema"), p];
  } catch { /* no adapter */ }
  return null;
}
let found = await fromAdapter();
if (!found) {
  const fk = findFactory();
  if (!fk) { console.log("sanity FAILED: no project factory in model.mjs"); process.exit(2); }
  const p = m[fk]("probe-id", "Probe");
  const sk = findSchema(p);
  if (!sk) { console.log("sanity FAILED: no schema accepts the factory output"); process.exit(2); }
  found = [fk, sk, p];
}
const [fk, sk, probe] = found;
const schema = m[sk];
console.log("sanity: factory %s validates against schema %s  (v%d)", fk, sk, probe.schemaVersion);

const projPath = process.argv[2];
const proj = JSON.parse(readFileSync(projPath, "utf8"));
try {
  const parsed = schema.parse(proj);
  console.log("PROJECT VALID against the app's own schema (v" + parsed.schemaVersion + ")");
  const d = parsed.documents[0];
  console.log("  instances=%d nets=%d routes=%d junctions=%d annotations=%d drafting=%d",
    d.instances.length, d.nets.length, d.routes.length, d.junctions.length,
    d.annotations.length, d.drafting.objects.length);
} catch (e) {
  console.log("PROJECT REJECTED:");
  const issues = e.issues ?? e.errors ?? [];
  for (const i of issues.slice(0, 40)) {
    console.log("  -", (i.path ?? []).join("."), "|", i.code, "|", i.message);
  }
  if (!issues.length) console.log(e);
  process.exit(1);
}
