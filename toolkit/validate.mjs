import { readFileSync } from "node:fs";
import * as m from "./model.mjs";

// The bundle is minified, so the export NAMES change on every redeploy
// (2026-08-30: schema `a`, factory `n`; 2026-09-01: schema `s`, factory `i`).
// Find them the way refresh_model.py does -- by running them -- instead of
// hard-coding letters that go stale.
function findFactory() {
  for (const k of Object.keys(m)) {
    try {
      const o = m[k]("probe-id", "Probe");
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

const fk = findFactory();
if (!fk) { console.log("sanity FAILED: no project factory in model.mjs"); process.exit(2); }
const probe = m[fk]("probe-id", "Probe");
const sk = findSchema(probe);
if (!sk) { console.log("sanity FAILED: no schema accepts the factory output"); process.exit(2); }
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
