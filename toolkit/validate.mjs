import { readFileSync } from "node:fs";
import * as m from "./model.mjs";

const projPath = process.argv[2];
const proj = JSON.parse(readFileSync(projPath, "utf8"));

// `a` is the exported project schema (rc); `n` is the new-project factory (sc)
// which itself calls rc.parse(...) — used here to confirm we picked the right one.
const schema = m.a;
const probe = m.n("probe-id", "Probe");
const SV = probe.schemaVersion;   // whatever the live model builds
try {
  schema.parse(probe);
  console.log("sanity: factory output validates against m.a  -> correct schema");
} catch (e) {
  console.log("sanity FAILED, m.a is not the project schema:", e.message);
  process.exit(2);
}

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
