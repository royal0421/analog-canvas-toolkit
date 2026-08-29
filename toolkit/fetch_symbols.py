# -*- coding: utf-8 -*-
"""fetch_symbols.py — sync AI/toolkit/sym/ with the upstream symbol library.

    python fetch_symbols.py            # download anything missing
    python fetch_symbols.py --force    # re-download everything (upstream may
                                       # have changed a symbol in place)

Analog Canvas is a live project and people keep adding symbols, so treat
`sym/` as a cache, not a fixed set.  Run this whenever a figure needs a symbol
that is not already there -- it takes a few seconds, which is much cheaper
than hunting one file at a time (2026-08-29: finding `resistor` by hand cost
several minutes).

Upstream layout: assets are `<id>.symbol.json` under
packages/symbols/assets/razavi-v1/ ; we store them as `sym/<id>.json`, which
is the name `icproj.sym()` looks for.  The repo copy has been verified
byte-identical to what the deployed site ships.
"""
import io, json, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SYMDIR = os.path.join(HERE, "sym")
REPO = "cascode-ai/analog-canvas"
BRANCH = "main"
ASSET_DIR = "packages/symbols/assets/razavi-v1"
CATALOG = "packages/symbols/src/razavi-catalog.generated.ts"
RAW = "https://raw.githubusercontent.com/%s/%s/" % (REPO, BRANCH)
SUFFIX = ".symbol.json"


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "analog-canvas-toolkit"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def main(force=False):
    tree = json.loads(get("https://api.github.com/repos/%s/git/trees/%s"
                          "?recursive=1" % (REPO, BRANCH), 60))["tree"]
    remote = sorted(t["path"].split("/")[-1][:-len(SUFFIX)] for t in tree
                    if t["path"].startswith(ASSET_DIR + "/")
                    and t["path"].endswith(SUFFIX))
    if not os.path.isdir(SYMDIR):
        os.makedirs(SYMDIR)
    have = {f[:-5] for f in os.listdir(SYMDIR) if f.endswith(".json")}
    want = remote if force else [s for s in remote if s not in have]
    print("upstream %d symbols, local %d, downloading %d"
          % (len(remote), len(have), len(want)))

    def one(sid):
        try:
            raw = get(RAW + "%s/%s%s" % (ASSET_DIR, sid, SUFFIX))
            d = json.loads(raw.decode("utf-8"))
            assert d.get("id") and "pins" in d and "primitives" in d, sid
            with io.open(os.path.join(SYMDIR, sid + ".json"), "w",
                         encoding="utf-8", newline="\n") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
                f.write("\n")
            return (sid, len(d["pins"]), None)
        except Exception as e:                       # noqa: BLE001
            return (sid, 0, repr(e))

    ok, bad = [], []
    if want:
        with ThreadPoolExecutor(max_workers=12) as ex:
            for sid, npins, err in ex.map(one, want):
                (bad if err else ok).append((sid, npins, err))
    for sid, _n, err in bad:
        print("  ! FAILED %s : %s" % (sid, err))
    print("  downloaded %d, failed %d" % (len(ok), len(bad)))

    # Cross-check: every symbolId the editor's catalog references must have a
    # file, or a figure using it will die at load time.
    cat = get(RAW + CATALOG, 60).decode("utf-8")
    import re
    ids = sorted(set(re.findall(r'symbolId:\s*"([a-z0-9-]+)"', cat)))
    have = {f[:-5] for f in os.listdir(SYMDIR) if f.endswith(".json")}
    missing = [i for i in ids if i not in have]
    print("catalog references %d symbolIds; local sym/ now holds %d files"
          % (len(ids), len(have)))
    if missing:
        print("  ! catalog ids with no asset file:", ", ".join(missing))
        print("    (defined in code, not as an asset -- check "
              "packages/symbols/src/builtins.ts before using them)")
    else:
        print("  every catalog symbolId has a local file")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main(force="--force" in sys.argv))
