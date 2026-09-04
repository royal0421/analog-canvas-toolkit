# -*- coding: utf-8 -*-
"""Lane 2 part 3: run every netlist-clean deck through the placer and score it
against the drawing the hand-written generator produced.

    python netlist_bench.py            # fast: audits + geometry score
    python netlist_bench.py --full     # also schema + label check + PNG
    python netlist_bench.py <stem>     # one figure, verbose

Score
-----
place   fraction of devices whose position matches the reference after the
        two drawings are aligned on their own bounding boxes and scaled to
        the same grid pitch (a rank match, so a uniformly wider drawing is
        not punished twice)
mirror  fraction of transistors whose mirror matches
shape   aspect ratio of the auto drawing over the reference
"""
import io
import json
import os
import sys
import glob
import contextlib

import netlist_io as N
import autoplace as A

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir, "out")
AUTO = os.path.join(HERE, "auto")


def wire_len(doc, placed=None):
    """Total Manhattan length of every route leg.

    This is the number that says "does it look hand-drawn": a placer that
    wanders costs wire, a tidy one does not.  Compared against the figure the
    human drew, it is the only quality metric here that is not a matter of
    taste.
    """
    pos = {}
    for i in doc["instances"]:
        pl = i["placement"]
        pos[i["id"]] = (pl["position"]["x"], pl["position"]["y"],
                        pl.get("mirror", "none"), pl.get("rotation", 0),
                        i["symbolId"], i.get("symbolVariantId"))
    jn = {j["id"]: (j["position"]["x"], j["position"]["y"])
          for j in doc["junctions"]}
    import icproj

    def xy(ep):
        if ep["kind"] == "junction":
            return jn[ep["junctionId"]]
        x, y, mir, rot, sid, _v = pos[ep["instanceId"]]
        for pin in icproj.sym(sid)["pins"]:
            if pin["name"] == ep["pinName"]:
                dx, dy = icproj.xf(pin["at"]["x"], pin["at"]["y"], mir, rot)
                return (x + round(dx), y + round(dy))
        return (x, y)

    total = 0
    for r in doc["routes"]:
        cur = xy(r["start"])
        for lg in r["legs"]:
            to = lg["to"]
            nxt = ((to["position"]["x"], to["position"]["y"])
                   if to["kind"] == "bend" else xy(to["endpoint"]))
            total += abs(nxt[0] - cur[0]) + abs(nxt[1] - cur[1])
            cur = nxt
    return total


PIN_PAIRS = (("1", "2"), ("A", "K"), ("+", "-"), ("P1", "P2"))


def bend_count(doc):
    """How many corners the drawing makes.

    A corner is any point where a horizontal path and a vertical path meet
    -- a T-junction included (user, 2026-09-03: "T型算成一個轉角").  The
    paths are the route segments AND the bodies of two-terminal parts: a
    vertical wire ending on a lying-down resistor's left pin turns 90
    degrees there, even though the two halves are a route and a component.

    ⚠️ This used to be `len(legs)-1` per route, which is wrong twice over:
    a bus and the stub dropping off it are separate routes meeting at an L
    (each scores 0), and a component body was not a path at all.  On
    14.36(b) the old count said auto 8 / hand 11 -- "better than the human"
    -- while the real numbers are auto 29 / hand 20.
    """
    pos = {}
    for i in doc["instances"]:
        pl = i["placement"]
        pos[i["id"]] = (pl["position"]["x"], pl["position"]["y"],
                        pl.get("mirror", "none"), pl.get("rotation", 0),
                        i["symbolId"])
    variant = {i["id"]: i.get("symbolVariantId") for i in doc["instances"]}
    jn = {j["id"]: (j["position"]["x"], j["position"]["y"])
          for j in doc["junctions"]}
    import icproj

    def pin_xy(iid, name):
        if iid not in pos:
            return None
        x, y, mir, rot, sid = pos[iid]
        for pin in icproj.sym(sid)["pins"]:
            if pin["name"] == name:
                dx, dy = icproj.xf(pin["at"]["x"], pin["at"]["y"], mir, rot)
                return (x + round(dx), y + round(dy))
        return None

    def xy(ep):
        if ep["kind"] == "junction":
            return jn[ep["junctionId"]]
        return pin_xy(ep["instanceId"], ep["pinName"])

    segs, rsegs = [], []
    for r in doc["routes"]:
        cur = xy(r["start"])
        for lg in r["legs"]:
            to = lg["to"]
            nxt = ((to["position"]["x"], to["position"]["y"])
                   if to["kind"] == "bend" else xy(to["endpoint"]))
            if cur and nxt:
                segs.append((cur, nxt))
                rsegs.append((r["id"], cur, nxt))
            cur = nxt
    rnet0 = {r["id"]: r.get("netId") for r in doc["routes"]}
    inc, netat = {}, {}
    for rid, a, b in rsegs:
        if a == b:
            continue
        d = "H" if a[1] == b[1] else ("V" if a[0] == b[0] else None)
        if d is None:
            continue
        for p in (a, b):
            inc.setdefault(p, set()).add(d)
            netat.setdefault(p, set()).add(rnet0.get(rid))
    # every pin's escape direction is a path too -- a wire dropping onto an
    # op-amp's IN-, a port, or a ground stub turns 90 degrees there just as
    # it does on a resistor's pin.  Counting only two-terminal bodies was
    # unfair to the netlist lane, which has many more wires landing on
    # op-amp and port pins (user, 2026-09-03).
    for iid, (x, y, mir, rot, sid) in pos.items():
        for pdef in icproj.sym(sid)["pins"]:
            nm, dirn = pdef["name"], pdef.get("direction")
            if not dirn or (sid in ("nmos", "pmos") and nm == "B"):
                continue
            p = pin_xy(iid, nm)
            if p is None:
                continue
            vx, _vy = icproj.xf(*icproj.Schematic.DIRV[dirn],
                                mirror=mir, rotation=rot)
            inc.setdefault(p, set()).add("H" if round(vx) else "V")
    # A part hanging off V_DD meets the rail at a right angle by
    # construction -- that is how a rail is drawn, not a detour, so it does
    # not count (user, 2026-09-03: "連到VDD的不算轉折").
    skip = set()
    supnets = {r.get("netId") for r in doc["routes"]
               if r.get("presentation") == "power-rail"}
    for iid, (_x, _y, _m, _r, sid) in pos.items():
        if sid == "vdd-port":
            for pdef in icproj.sym(sid)["pins"]:
                p = pin_xy(iid, pdef["name"])
                if p:
                    skip.add(p)
    for r in doc["routes"]:
        if r.get("presentation") != "power-rail" and r.get("netId") not in supnets:
            continue
        cur = xy(r["start"])
        for lg in r["legs"]:
            to = lg["to"]
            nxt = ((to["position"]["x"], to["position"]["y"])
                   if to["kind"] == "bend" else xy(to["endpoint"]))
            if cur:
                skip.add(cur)
            if nxt:
                skip.add(nxt)
            cur = nxt
    # Crossing a gate NET is worth 2.5 (user, 2026-09-03).  Net level, not
    # pin level: the crossing usually happens out on the bus, which is a
    # different route from the stub that touches the pin -- 9.26(c)'s base
    # bus is crossed by two collector risers and a pin-level test saw
    # neither.
    gate_pin = {"nmos": "G", "pmos": "G", "npn": "B", "pnp": "B"}
    netof = {}
    for n in doc.get("nets", ()):
        for t in n["terminals"]:
            netof[(t["instanceId"], t["pinName"])] = n["id"]
    rnet = {r["id"]: r.get("netId") for r in doc["routes"]}
    gnets = set()
    for iid, (_x, _y, _m, _r, sid) in pos.items():
        if sid in gate_pin and (iid, gate_pin[sid]) in netof:
            gnets.add(netof[(iid, gate_pin[sid])])
    gx = set()
    lst = [(rnet.get(rid), a2, b2) for rid, a2, b2 in rsegs if a2 != b2]
    for i, (n1, (ax0, ay0), (ax1, ay1)) in enumerate(lst):
        h1 = ay0 == ay1
        for n2, (bx0, by0), (bx1, by1) in lst[i + 1:]:
            h2 = by0 == by1
            if h1 == h2 or (n1 is not None and n1 == n2):
                continue
            if h1:
                hx0, hx1, hy = min(ax0, ax1), max(ax0, ax1), ay0
                vx, vy0, vy1 = bx0, min(by0, by1), max(by0, by1)
            else:
                hx0, hx1, hy = min(bx0, bx1), max(bx0, bx1), by0
                vx, vy0, vy1 = ax0, min(ay0, ay1), max(ay0, ay1)
            if hx0 < vx < hx1 and vy0 < hy < vy1 and (n1 in gnets or n2 in gnets):
                gx.add((vx, hy))
    # Two DIFFERENT nets forming a cross is a CROSSING, not a corner -- it
    # has its own metric and must not be counted twice (user, 2026-09-03:
    # "交叉點就是兩條不同電性的net，構成一個十字").  Pin points carry their
    # own net, so a real junction still counts.
    for iid, (_x, _y, _m, _r, sid) in pos.items():
        for pdef in icproj.sym(sid)["pins"]:
            nm = pdef["name"]
            key = (iid, nm)
            p = pin_xy(iid, nm)
            if p is not None and key in netof:
                netat.setdefault(p, set()).add(netof[key])
    jpts = set(jn.values())
    n = 0
    # A bus running THROUGH a transistor body scores the same 2.5 -- even
    # when it is the net those gates sit on (user, 2026-09-03: "匯流排穿過
    # 電晶體本體就算 2.5").  One per transistor.
    nbody = 0
    for iid, (x, y, mir, rot, sid) in pos.items():
        if sid not in ("nmos", "pmos", "npn", "pnp"):
            continue
        bb = icproj.ink_box(sid, variant.get(iid), x, y, mir, rot)
        ix0, iy0, ix1, iy1 = bb[0] + 1, bb[1] + 1, bb[2] - 1, bb[3] - 1
        if ix0 >= ix1 or iy0 >= iy1:
            continue
        for _rid, a, b in rsegs:
            if (min(a[0], b[0]) < ix1 and max(a[0], b[0]) > ix0
                    and min(a[1], b[1]) < iy1 and max(a[1], b[1]) > iy0):
                nbody += 1
                break
    # L, T and a same-net cross all score one (user: "十字也算一個轉角就好")
    for p, ds in inc.items():
        if "H" not in ds or "V" not in ds or p in skip:
            continue
        nets = {x for x in netat.get(p, ()) if x}
        if len(nets) > 1 and p not in jpts:
            continue
        n += 1
    return n + 2.5 * (len(gx) + nbody)


def ref_placement(stem):
    p = os.path.join(ROOT, stem + ".icproj.json")
    doc = json.load(open(p, encoding="utf-8"))["documents"][0]
    out = {}
    for i in doc["instances"]:
        if i["symbolId"] in N.MARKERS:
            continue
        pl = i["placement"]
        out[i["id"]] = (pl["position"]["x"], pl["position"]["y"],
                        pl.get("mirror", "none"))
    return out


def rank_map(pos):
    """(x, y) -> (column index, row index) so two drawings can be compared
    without punishing a different absolute pitch."""
    xs = sorted(set(v[0] for v in pos.values()))
    ys = sorted(set(v[1] for v in pos.values()))
    return {k: (xs.index(v[0]), ys.index(v[1])) for k, v in pos.items()}


def order_score(ref, got):
    """Fraction of device PAIRS whose left/right and above/below relation
    agrees.  Robust to a drawing that simply has one column more."""
    ks = sorted(set(ref) & set(got))
    if len(ks) < 2:
        return 0.0
    hit = tot = 0
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            a, b = ks[i], ks[j]
            for ax in (0, 1):
                tot += 1
                sr = (ref[a][ax] > ref[b][ax]) - (ref[a][ax] < ref[b][ax])
                sg = (got[a][ax] > got[b][ax]) - (got[a][ax] < got[b][ax])
                hit += (sr == sg)
    return hit / float(tot)


def axis_score(ref, got, ax):
    """Column (ax=0) or row (ax=1) agreement on its own -- tells you WHICH
    of the two decisions is wrong instead of one blended number."""
    common = sorted(set(ref) & set(got))
    if not common:
        return 0.0
    ra, ga = rank_map(ref), rank_map(got)
    return sum(1 for k in common if ra[k][ax] == ga[k][ax]) / float(len(common))


def score(ref, got):
    common = set(ref) & set(got)
    if not common:
        return 0.0, 0.0
    ra, ga = rank_map(ref), rank_map(got)
    hit = sum(1 for k in common if ra[k] == ga[k])
    mos = [k for k in common if ref[k][2] in ("none", "x")]
    mir = sum(1 for k in mos if ref[k][2] == got[k][2])
    return hit / float(len(common)), (mir / float(len(mos)) if mos else 1.0)


def extent(pos):
    if not pos:
        return 0, 0
    xs = [v[0] for v in pos.values()]
    ys = [v[1] for v in pos.values()]
    return max(xs) - min(xs) + 60, max(ys) - min(ys) + 60


def run_one(stem, full=False, verbose=False):
    deck = os.path.join(HERE, "decks", stem + ".cir")
    buf = io.StringIO()
    if not os.path.isdir(AUTO):
        os.makedirs(AUTO)
    if full:
        os.environ.pop("AC_FAST", None)
    else:
        os.environ["AC_FAST"] = "1"
    err = None
    try:
        if verbose:
            p = A.place_deck(deck, verbose=True)
        else:
            with contextlib.redirect_stdout(buf):
                p = A.place_deck(deck, verbose=True)
    except Exception as e:                       # noqa: BLE001
        return {"stem": stem, "error": "%s: %s" % (type(e).__name__, e),
                "log": buf.getvalue()}
    log = buf.getvalue()
    got = {}
    for i in p.f.instances:
        if i["symbolId"] in N.MARKERS:
            continue
        pl = i["placement"]
        got[i["id"]] = (pl["position"]["x"], pl["position"]["y"],
                        pl.get("mirror", "none"))
    ref = ref_placement(stem)
    pl_s, mi_s = score(ref, got)
    refdoc = json.load(open(os.path.join(ROOT, stem + ".icproj.json"),
                            encoding="utf-8"))["documents"][0]
    gotdoc = json.load(open(p.out_proj, encoding="utf-8"))["documents"][0]
    rw, gw = wire_len(refdoc), wire_len(gotdoc)
    r_wire = (gw / float(rw)) if rw else 0
    rb, gb = bend_count(refdoc), bend_count(gotdoc)
    r_bend = (gb / float(rb)) if rb else 0
    r = {"stem": stem, "log": log, "place": pl_s, "mirror": mi_s,
         "order": order_score(ref, got), "wire": r_wire, "bend": r_bend,
         "bend_ref": rb, "bend_got": gb,
         "col": axis_score(ref, got, 0), "row": axis_score(ref, got, 1),
         "wire_ref": rw, "wire_got": gw,
         "nref": len(ref), "ngot": len(got), "error": err}
    for key, tag in (("self", "self-check errors:"), ):
        for line in log.splitlines():
            if line.startswith(tag):
                r[key] = int(line.split(":")[1])
    for line in log.splitlines():
        if line.startswith("audits:"):
            body = line.split("audits:")[1].split("(")[0]
            for part in body.split("|"):
                k, v = part.split()
                r[k] = int(v)
        if "schema:" in line:
            r["schema"] = "VALID" in line
        if line.strip().startswith("labels:"):
            r["lblchk"] = "OK" in line
        if "crossings" in line:
            r["cross"] = int(line.split("crossings")[1].split()[0])
        if line.startswith("  pitch:"):
            r["pitch"] = line.split("pitch:")[1].strip()
        if line.startswith("extent"):
            r["extent"] = line.split("|")[0].strip()
    rw, rh = extent(ref)
    gw, gh = extent(got)
    r["aspect"] = (gw / float(gh)) / (rw / float(rh)) if rh and gh else 0
    r["refsize"] = "%dx%d" % (rw, rh)
    r["gotsize"] = "%dx%d" % (gw, gh)
    return r


def main(argv):
    full = "--full" in argv
    args = [a for a in argv[1:] if not a.startswith("-")]
    if args:
        r = run_one(args[0], full=full, verbose=True)
        if r.get("error"):
            print("ERROR", r["error"])
        else:
            print("place %.0f%%  order %.0f%%  mirror %.0f%%  aspect x%.2f  %s -> %s"
                  % (100 * r["place"], 100 * r["order"], 100 * r["mirror"],
                     r["aspect"],
                     r["refsize"], r["gotsize"]))
        return
    clean = []
    for d in sorted(glob.glob(os.path.join(HERE, "decks", "*.cir"))):
        stem = os.path.basename(d)[:-4]
        _c, problems = N.export_project(os.path.join(ROOT,
                                                     stem + ".icproj.json"))
        if not problems:
            clean.append(stem)
    tot = {"legs": 0, "labels": 0, "on-wire": 0, "tees": 0,
           "shorts": 0, "self": 0}
    pls, mis, ors, wrs, bad, aud_rows = [], [], [], [], [], []
    bds = []
    cls, rws, xrs = [], [], []
    print("%-42s %5s %5s %5s %5s %5s %4s %5s  %-16s %s"
          % ("figure", "col", "row", "order", "mirr", "wire", "X", "aspct",
             "audits s/l/L/w/t/S", "size"))
    for stem in clean:
        r = run_one(stem, full=full)
        if r.get("error"):
            bad.append(stem)
            print("%-46s  ERROR %s" % (stem[:46], r["error"][:60]))
            continue
        for k in tot:
            tot[k] += r.get(k, 0)
        aud_rows.append(sum(r.get(k, 0) for k in tot))
        wrs.append(r["wire"])
        bds.append(r.get("bend", 0))
        xrs.append(r.get("cross", 0))
        cls.append(r["col"]); rws.append(r["row"])
        pls.append(r["place"])
        ors.append(r["order"])
        mis.append(r["mirror"])
        if full and not r.get("schema", True):
            bad.append(stem + " (schema)")
        aud = "%d/%d/%d/%d/%d/%d" % (r.get("self", -1), r.get("legs", -1),
                                     r.get("labels", -1), r.get("on-wire", -1),
                                     r.get("tees", -1), r.get("shorts", -1))
        print("%-42s %4.0f%% %4.0f%% %4.0f%% %4.0f%% %4.1fx %4d %5.2f  %-16s %s -> %s"
              % (stem[:42], 100 * r["col"], 100 * r["row"], 100 * r["order"],
                 100 * r["mirror"], r["wire"], r.get("cross", -1),
                 r["aspect"],
                 aud + ("" if not full else
                        (" S" if r.get("schema") else " s!")), r["refsize"],
                 r["gotsize"]))
    n = max(1, len(pls))
    clean = sum(1 for v in aud_rows if v == 0)
    print("\n%d figures | %d fully clean | place %.0f%% | order %.0f%% | "
          "col %.0f%% | row %.0f%% | "
          "mirror %.0f%% | wire %.2fx | bends %.2fx | crossings %d | %s "
          "| errors %d"
          % (len(pls), clean, 100 * sum(pls) / n, 100 * sum(ors) / n,
             100 * sum(cls) / n, 100 * sum(rws) / n,
             100 * sum(mis) / n, sum(wrs) / n,
             sum(bds) / max(1, len(bds)),
             sum(xrs),
             " ".join("%s=%d" % kv for kv in sorted(tot.items())), len(bad)))


if __name__ == "__main__":
    main(sys.argv)
