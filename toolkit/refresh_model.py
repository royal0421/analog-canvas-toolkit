# -*- coding: utf-8 -*-
"""refresh_model.py — re-pull the site's own project schema into model.mjs.

    python refresh_model.py

Analog Canvas is redeployed regularly and the schema moves with it: on
2026-08-29 the site started writing `schemaVersion: 30` while this toolkit was
still writing 29.  Run this whenever an exported project comes back with a
different schemaVersion, or whenever validate.mjs disagrees with the editor.

Picking the right chunk is done by RUNNING it, not by pattern-matching.  Three
different chunks mention `mosBulkDefaults` and `schemaVersion` -- the App
bundle, the bundled example projects, and the model -- and neither file size
nor the version number separates them.  The model is simply the chunk that
exports a function which builds a project, plus a schema that accepts it.
"""
import io, json, os, re, shutil, subprocess, sys, tempfile, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(HERE, "schema_version.py")
SITE = "https://analog-canvas.tokenzhang.com"
IMPORT_RE = re.compile(r'from\s*"\./([A-Za-z0-9_.\-]+\.js)"')
PROBE = '''import * as m from "./%s";
const f = Object.keys(m).find(k => {
  try { const o = m[k]("p", "P"); return o && Array.isArray(o.documents)
        && typeof o.schemaVersion === "number"; } catch { return false; }
});
if (!f) { console.log("{}"); process.exit(0); }
const p = m[f]("p", "P");
const s = Object.keys(m).find(k => m[k] && m[k].safeParse
                                 && m[k].safeParse(p).success);
const l = Object.keys(m).find(k => {
  try {
    if (typeof m[k] !== "function") return false;
    const a = m[k]("V_in"), b = m[k]("V_DD");
    return a && b && Array.isArray(a.runs) && Array.isArray(b.runs)
           && JSON.stringify(a).includes('"subscript"')
           && JSON.stringify(b).includes('"DD"');
  } catch { return false; }
});
console.log(JSON.stringify({ factory: f, schema: s, label: l,
                             version: p.schemaVersion }));
'''


def get(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": "ac-toolkit"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def update_schema_version(version, path=VERSION_FILE):
    """Atomically update the single schema-version source of truth."""
    with io.open(path, encoding="utf-8") as f:
        current = f.read()
    updated, count = re.subn(
        r"(?m)^SCHEMA_VERSION[ \t]*=[ \t]*\d+[ \t]*$",
        "SCHEMA_VERSION = %d" % version,
        current,
    )
    if count != 1:
        raise RuntimeError("expected one SCHEMA_VERSION assignment in %s" % path)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(updated)
    os.replace(tmp, path)
    return current != updated


def main():
    texts, seen = {}, set()
    queue = re.findall(r'assets/[A-Za-z0-9_.\-]+\.js', get(SITE + "/"))
    while queue:
        nm = queue.pop().split("/")[-1]
        if nm in seen:
            continue
        seen.add(nm)
        try:
            t = get("%s/assets/%s" % (SITE, nm))
        except Exception as e:                       # noqa: BLE001
            print("  ! %s: %s" % (nm, e))
            continue
        texts[nm] = t
        queue += IMPORT_RE.findall(t)
        queue += re.findall(r'assets/[A-Za-z0-9_.\-]+\.js', t)
    print("walked %d chunks" % len(texts))

    tmp = tempfile.mkdtemp(prefix="ac-bundle-")
    for nm, t in texts.items():
        io.open(os.path.join(tmp, nm), "w", encoding="utf-8",
                newline="\n").write(t)

    winner = None
    for nm, t in sorted(texts.items(), key=lambda kv: len(kv[1])):
        if "mosBulkDefaults" not in t:
            continue
        io.open(os.path.join(tmp, "_probe.mjs"), "w", encoding="utf-8",
                newline="\n").write(PROBE % nm)
        r = subprocess.run(["node", "_probe.mjs"], cwd=tmp,
                           capture_output=True, text=True)
        try:
            info = json.loads((r.stdout or "{}").strip() or "{}")
        except ValueError:
            info = {}
        if info.get("factory") and info.get("schema") and info.get("label"):
            winner = (nm, info)
            break
    if not winner:
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit("no chunk exports a working project factory -- bundle changed?")
    name, info = winner
    print("model chunk: %s  ->  factory %s, schema %s, schemaVersion %d"
          % (name, info["factory"], info["schema"], info["version"]))

    order, need = [], [name]
    while need:
        n = need.pop()
        if n in order:
            continue
        order.append(n)
        need += IMPORT_RE.findall(texts.get(n, ""))
    rename = {name: "model.mjs"}
    for i, n in enumerate(d for d in order if d != name):
        rename[n] = "model-dep-%d.mjs" % i
    for old in [f for f in os.listdir(HERE) if f.startswith("model-dep-")]:
        os.remove(os.path.join(HERE, old))
    for n, out in rename.items():
        body = IMPORT_RE.sub(
            lambda m: 'from "./%s"' % rename.get(m.group(1), m.group(1)),
            texts[n])
        io.open(os.path.join(HERE, out), "w", encoding="utf-8",
                newline="\n").write(body)
        print("  wrote %-18s (%d bytes)" % (out, len(body)))
    adapter = '''// Generated by refresh_model.py; do not edit.\n\
import * as model from "./model.mjs";\n\
export const projectSchema = model[%s];\n\
export const createProject = model[%s];\n\
export const buildName = model[%s];\n\
export const schemaVersion = %d;\n''' % (
        json.dumps(info["schema"]), json.dumps(info["factory"]),
        json.dumps(info["label"]), info["version"])
    io.open(os.path.join(HERE, "model-adapter.mjs"), "w", encoding="utf-8",
            newline="\n").write(adapter)
    print("  wrote %-18s (%d bytes)" % ("model-adapter.mjs", len(adapter)))
    shutil.rmtree(tmp, ignore_errors=True)
    changed = update_schema_version(info["version"])
    print("\n%s schema_version.py -> %d; re-run every generator."
          % ("updated" if changed else "confirmed", info["version"]))
    return info["version"]


if __name__ == "__main__":
    main()
