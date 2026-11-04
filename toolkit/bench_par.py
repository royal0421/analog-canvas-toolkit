# -*- coding: utf-8 -*-
"""Same numbers as netlist_bench.py, one figure per core.

Iteration tool only -- `netlist_bench.py` stays the official scorer.
Run from the toolkit directory:  python bench_par.py [stem ...]

    python bench_par.py --gen     the generalisation decks instead
                                  (decks/new, decks/razavi: no hand-drawn
                                  reference, so audits / crossings / bends
                                  only -- what a change must not break)
    python bench_par.py --gen --accept
                                  store this run as gen_baseline.json

Without --accept, --gen compares against gen_baseline.json and exits 1 if
any deck got more audit errors, crossings or bends.
"""
import glob
import multiprocessing as mp
import os
import sys

sys.path.insert(0, os.getcwd())

import netlist_bench as NB   # noqa: E402
import netlist_io as N       # noqa: E402


def one(stem):
    r = NB.run_one(stem)
    r.pop("log", None)
    return r


def gen_one(path):
    """Draw one generalisation deck into a private temp dir; report the
    audit counts the way the build log prints them."""
    import contextlib
    import io
    import shutil
    import tempfile
    import time
    import autoplace as A
    import ring_corners as RC
    os.environ["AC_FAST"] = "1"
    tmp = tempfile.mkdtemp(prefix="gen-")
    stem = os.path.basename(path)[:-4]
    buf, t0 = io.StringIO(), time.time()
    try:
        with contextlib.redirect_stdout(buf):
            p = A.place_deck(path, out_proj=os.path.join(tmp, stem + ".json"),
                             out_svg=os.path.join(tmp, stem + ".svg"),
                             verbose=True)
        pts, gates, _x = RC.corners(p.f)
        log = buf.getvalue()
        errs = A._audit_count(log)
        cross = A._cross_from(log)
        return (stem, errs, cross, len(pts) + 2.5 * len(gates),
                time.time() - t0, None)
    except Exception as e:                       # noqa: BLE001
        return (stem, None, None, None, time.time() - t0,
                "%s: %s" % (type(e).__name__, e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def compare_gen(now, base):
    """(worse, better, new) between two {deck: {errors, crossings, bends}}
    tables.  A deck missing from `now` is not judged here: a deck that
    fails to draw is reported by the caller."""
    worse, better, new = [], [], []
    for stem, v in sorted(now.items()):
        b = base.get(stem)
        if b is None:
            new.append(stem)
            continue
        for k in ("errors", "crossings", "bends"):
            if v[k] > b[k]:
                worse.append("%s %s %s -> %s" % (stem, k, b[k], v[k]))
            elif v[k] < b[k]:
                better.append("%s %s %s -> %s" % (stem, k, b[k], v[k]))
    return worse, better, new


def main_gen():
    import time
    paths = sorted(glob.glob(os.path.join(NB.HERE, "decks", "new", "*.cir"))
                   + glob.glob(os.path.join(NB.HERE, "decks", "razavi",
                                            "*.cir")))
    t0 = time.time()
    pool = mp.Pool(min(len(paths), max(1, mp.cpu_count())))
    rows = pool.map(gen_one, paths, chunksize=1)
    pool.close()
    pool.join()
    clean = cross = 0
    for stem, errs, x, bends, secs, err in rows:
        if err:
            print("%-40s ERROR %s" % (stem[:40], err[:80]))
            continue
        clean += errs == 0
        cross += x
        print("%-40s audit errors %2d  crossings %2d  bends %5.1f  %4.0f s"
              % (stem[:40], errs, x, bends, secs))
    print("\n%d decks | %d clean | crossings %d | errors %d\nwall %.0f s"
          % (len(rows), clean, cross, sum(1 for r in rows if r[5]),
             time.time() - t0))
    import json
    base_path = os.path.join(NB.HERE, "gen_baseline.json")
    now = dict((r[0], {"errors": r[1], "crossings": r[2], "bends": r[3]})
               for r in rows if not r[5])
    if "--accept" in sys.argv:
        with open(base_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(now, indent=1, sort_keys=True) + "\n")
        print("baseline stored: %d decks" % len(now))
        return 0
    if not os.path.exists(base_path):
        print("no gen_baseline.json yet (run with --accept)")
        return 0
    base = json.load(open(base_path, encoding="utf-8"))
    worse, better, new = compare_gen(now, base)
    for stem in new:
        print("  + new   %s" % stem)
    for w in better:
        print("  better  " + w)
    for w in worse:
        print("  WORSE   " + w)
    failed = [r[0] for r in rows if r[5]]
    for stem in failed:
        print("  FAILED  " + stem)
    print("vs baseline: %d worse, %d better" % (len(worse), len(better)))
    return 1 if worse or failed else 0


def main():
    if "--gen" in sys.argv:
        sys.exit(main_gen())
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        stems = args
    else:
        stems = []
        for d in sorted(glob.glob(os.path.join(NB.HERE, "decks", "*.cir"))):
            stem = os.path.basename(d)[:-4]
            _c, problems = N.export_project(
                os.path.join(NB.ROOT, stem + ".icproj.json"))
            if not problems:
                stems.append(stem)
    import time
    t0 = time.time()
    # the parent only waits, so every core gets a figure; chunksize=1 hands
    # them out one at a time (the default batches them, and the last batch
    # then runs on a single core while the others idle)
    pool = mp.Pool(min(len(stems), max(1, mp.cpu_count())))
    rows = pool.map(one, stems, chunksize=1)
    pool.close()
    pool.join()
    elapsed = time.time() - t0
    keys = ("self", "legs", "labels", "on-wire", "tees", "shorts")
    tot = dict((k, 0) for k in keys)
    clean = nerr = 0
    wrs, bds, xrs, pls, xov = [], [], [], [], []
    bds_opt = []          # SOP 3J: NAND/NOR corners are not comparable
    for r in rows:
        if r.get("error"):
            nerr += 1
            print("%-46s ERROR %s" % (r["stem"][:46], r["error"][:70]))
            continue
        s = sum(r.get(k, 0) for k in keys)
        for k in keys:
            tot[k] += r.get(k, 0)
        if s == 0:
            clean += 1
        wrs.append(r["wire"])
        bds.append(r.get("bend", 0))
        if "NAND" not in r["stem"] and "NOR" not in r["stem"]:
            bds_opt.append(r.get("bend", 0))
        xrs.append(r.get("cross", 0))
        xov.append(r.get("cross_over", 0))
        pls.append(r["place"])
        print("%-46s wire %4.1fx  bends %4.2fx (%5.1f/%5.1f)  X %2d/%d  %s"
              "  place %3.0f%%"
              % (r["stem"][:46], r["wire"], r.get("bend", 0),
                 r.get("bend_got", 0), r.get("bend_ref", 0),
                 r.get("cross", -1), r.get("cross_ref", 0),
                 "/".join(str(r.get(k, -1)) for k in keys),
                 100 * r["place"]))
    n = max(1, len(wrs))
    print("\n%d figures | %d fully clean | place %.0f%% | wire %.2fx | "
          "bends %.2fx | crossings %d (over hand %d) | %s | errors %d"
          % (len(rows), clean, 100 * sum(pls) / n, sum(wrs) / n,
             sum(bds) / n, sum(xrs), sum(xov),
             " ".join("%s=%d" % kv for kv in sorted(tot.items())), nerr))
    print("wall %.0f s on %d workers" % (elapsed, pool._processes))


if __name__ == "__main__":
    main()
