# -*- coding: utf-8 -*-
"""Same numbers as netlist_bench.py, one figure per core.

Iteration tool only -- `netlist_bench.py` stays the official scorer.
Run from the toolkit directory:  python bench_par.py [stem ...]
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


def main():
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
    pool = mp.Pool(min(len(stems), max(1, mp.cpu_count() - 1)))
    rows = pool.map(one, stems)
    pool.close()
    pool.join()
    keys = ("self", "legs", "labels", "on-wire", "tees", "shorts")
    tot = dict((k, 0) for k in keys)
    clean = nerr = 0
    wrs, bds, xrs, pls = [], [], [], []
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
        pls.append(r["place"])
        print("%-46s wire %4.1fx  bends %4.2fx (%5.1f/%5.1f)  X %2d  %s"
              % (r["stem"][:46], r["wire"], r.get("bend", 0),
                 r.get("bend_got", 0), r.get("bend_ref", 0),
                 r.get("cross", -1),
                 "/".join(str(r.get(k, -1)) for k in keys)))
    n = max(1, len(wrs))
    print("\n%d figures | %d fully clean | place %.0f%% | wire %.2fx | "
          "bends %.2fx | crossings %d | %s | errors %d"
          % (len(rows), clean, 100 * sum(pls) / n, sum(wrs) / n,
             sum(bds) / n, sum(xrs),
             " ".join("%s=%d" % kv for kv in sorted(tot.items())), nerr))


if __name__ == "__main__":
    main()
