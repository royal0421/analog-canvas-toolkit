# -*- coding: utf-8 -*-
"""Circle every corner in red, hand-drawn above / autoplace below.

    python ring_corners.py <stem> [<stem> ...]

`<stem>` is the figure's file stem, e.g. `Razavi_Fig_14_36b_biquad`; the
hand-drawn answer is `<root>/<stem>.icproj.json` and the netlist lane's
version is `auto/<stem>.icproj.json`.  Both are re-rendered here, so the
comparison never depends on a stale preview or on the two lanes' different
preview naming.

CORNER (user, 2026-09-03, after circling them by hand):
    any point where a horizontal path and a vertical path meet.
    One per point -- an L, a T and a crossing all score one.
    A path is a route segment OR a pin's escape direction: a wire dropping
    onto an op-amp's IN-, onto a port, or onto a ground stub turns 90
    degrees there exactly as it does on a resistor's pin.
"""
import io
import os
import pathlib
import re
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw

import icproj
import render_project as RP

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir, "out")
OUT = os.path.join(HERE, "auto")


def pin_dirs(f):
    """{(x, y): {"H"/"V"}} for every visible pin of every instance."""
    out = {}
    for iid in f.placed:
        sid = f.placed[iid][0]
        for pdef in icproj.sym(sid)["pins"]:
            nm = pdef["name"]
            if f._is_hidden_terminal(iid, nm):
                continue
            try:
                d, xy = f.pin_dir(iid, nm), f.pin(iid, nm)
            except (KeyError, TypeError):
                continue
            if not d:
                continue
            out.setdefault(xy, set()).add("H" if d[0] else "V")
    return out


def supply_points(f):
    """Points that belong to the supply.

    A part hanging off V_DD meets the rail at a right angle by construction
    -- that is how the textbook draws a rail, not a detour, so it does not
    count (user, 2026-09-03: "連到VDD的不算轉折").
    """
    out = set()
    supnets = {r.get("netId") for r in f.routes
               if r.get("presentation") == "power-rail"}
    for iid in f.placed:
        if f.placed[iid][0] == "vdd-port":
            for pdef in icproj.sym("vdd-port")["pins"]:
                try:
                    out.add(f.pin(iid, pdef["name"]))
                except KeyError:
                    pass
    for r in f.routes:
        if r.get("presentation") == "power-rail" or r.get("netId") in supnets:
            for _rid, x0, y0, x1, y1 in f._route_segments(r):
                out.add((x0, y0))
                out.add((x1, y1))
    return out


GATE_PIN = {"nmos": "G", "pmos": "G", "npn": "B", "pnp": "B"}


def gate_nets(f):
    """Nets that drive a gate (or a base).

    Crossing such a net ANYWHERE is crossing a gate lead: the bus exists to
    drive that gate, so a wire laid across it leaves the reader unable to
    tell whether it connects.  Looking only at the short segment that
    touches the pin missed the usual case -- the crossing happens out on the
    bus, which is a different route (user, 2026-09-03: 9.26(c)'s base bus is
    crossed by two collector risers).
    """
    gp = {"nmos": "G", "pmos": "G", "npn": "B", "pnp": "B"}
    netof = {}
    for n in f.nets:
        for t in n["terminals"]:
            netof[(t["instanceId"], t["pinName"])] = n["id"]
    out = set()
    for iid in f.placed:
        sid = f.placed[iid][0]
        if sid in gp and (iid, gp[sid]) in netof:
            out.add(netof[(iid, gp[sid])])
    return out


def _cross_points(f, want_gate):
    """Interior crossings of two nets of different electrical identity.

    `want_gate` picks which half to return: the ones that cross a gate net
    (scored 2.5 corners each) or the rest (plain crossings).
    """
    rnet = {r["id"]: r.get("netId") for r in f.routes}
    gnets = gate_nets(f)
    segs = [(rnet.get(rid), x0, y0, x1, y1)
            for rid, x0, y0, x1, y1 in f.segments()
            if not (x0 == x1 and y0 == y1)]
    out = []
    for i, (n1, ax0, ay0, ax1, ay1) in enumerate(segs):
        h1 = ay0 == ay1
        for n2, bx0, by0, bx1, by1 in segs[i + 1:]:
            h2 = by0 == by1
            if h1 == h2 or (n1 is not None and n1 == n2):
                continue
            if h1:
                hx0, hx1, hy = min(ax0, ax1), max(ax0, ax1), ay0
                vx, vy0, vy1 = bx0, min(by0, by1), max(by0, by1)
            else:
                hx0, hx1, hy = min(bx0, bx1), max(bx0, bx1), by0
                vx, vy0, vy1 = ax0, min(ay0, ay1), max(ay0, ay1)
            if not (hx0 < vx < hx1 and vy0 < hy < vy1):
                continue
            hits_gate = (n1 in gnets) or (n2 in gnets)
            if hits_gate == want_gate:
                out.append((vx, hy))
    return sorted(set(out))


TRANS = ("nmos", "pmos", "npn", "pnp")


def body_passes(f):
    """A bus running THROUGH a transistor body.

    Scored like crossing a gate lead -- 2.5 corners each (user, 2026-09-03:
    "匯流排穿過電晶體本體就算 2.5").  It counts even when the bus belongs to
    the very net those gates are on: the reader still cannot see where the
    connection is.  One per transistor, however many wires cross it.
    """
    out = []
    segs = [s for s in f.segments() if not (s[1] == s[3] and s[2] == s[4])]
    for iid in sorted(f.placed):
        if f.placed[iid][0] not in TRANS:
            continue
        bb = f.ink(iid)
        ix0, iy0, ix1, iy1 = bb[0] + 1, bb[1] + 1, bb[2] - 1, bb[3] - 1
        if ix0 >= ix1 or iy0 >= iy1:
            continue
        for _rid, x0, y0, x1, y1 in segs:
            if (min(x0, x1) < ix1 and max(x0, x1) > ix0
                    and min(y0, y1) < iy1 and max(y0, y1) > iy0):
                out.append(((ix0 + ix1) // 2, (iy0 + iy1) // 2))
                break
    return out


def gate_crossings(f):
    return _cross_points(f, True) + body_passes(f)


def crossings(f):
    """Two nets of DIFFERENT electrical identity forming a cross.

    Strictly interior: the horizontal segment must pass through the inside
    of the vertical one and vice versa, so a T (one segment ending on the
    other) is not a crossing (user, 2026-09-03: "交叉點就是兩條不同電性的
    net，構成一個十字").
    """
    return _cross_points(f, False)


def corners(f):
    rnet = {r["id"]: r.get("netId") for r in f.routes}
    netat, inc = {}, {}
    for rid, x0, y0, x1, y1 in f.segments():
        if (x0, y0) == (x1, y1):
            continue
        d = "H" if y0 == y1 else "V"
        for p in ((x0, y0), (x1, y1)):
            inc.setdefault(p, set()).add(d)
            netat.setdefault(p, set()).add(rnet.get(rid))
    netof = {}
    for n in f.nets:
        for t in n["terminals"]:
            netof[(t["instanceId"], t["pinName"])] = n["id"]
    for iid in f.placed:
        sid = f.placed[iid][0]
        for pdef in icproj.sym(sid)["pins"]:
            nm = pdef["name"]
            try:
                xy = f.pin(iid, nm)
            except KeyError:
                continue
            if (iid, nm) in netof:
                netat.setdefault(xy, set()).add(netof[(iid, nm)])
    for xy, ds in pin_dirs(f).items():
        inc.setdefault(xy, set()).update(ds)
    skip = supply_points(f)
    jn = {(j["position"]["x"], j["position"]["y"]) for j in f.junctions}
    pts = []
    for p, ds in inc.items():
        if "H" not in ds or "V" not in ds or p in skip:
            continue
        # two DIFFERENT nets meeting at a point is a crossing, not a corner
        # -- crossings have their own metric and must not be counted twice
        # (user, 2026-09-03: "交叉點不能算一個轉折點")
        nets = {n for n in netat.get(p, ()) if n}
        if len(nets) > 1 and p not in jn:
            continue
        pts.append(p)
    return pts, gate_crossings(f), crossings(f)


def _chrome():
    cands = [os.environ.get("CHROME_PATH")]
    cands += [shutil.which(n) for n in ("chrome", "chrome.exe", "chromium",
                                        "google-chrome")]
    cands += [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]
    return next((c for c in cands if c and os.path.isfile(c)), None)


def render(json_path, tag):
    """Re-render both lanes here: the hand-drawn previews use short names
    (`preview_fig1436b.png`) that do not match the project stem, so reusing
    them means a lookup table that goes stale."""
    svg = os.path.join(OUT, "_ring_%s.svg" % tag)
    f = RP.load(json_path, out_svg=svg)
    f._preview(RP.viewbox(f))
    png = svg[:-4] + ".png"
    if os.path.exists(png):
        os.remove(png)
    chrome = _chrome()
    if not chrome:
        raise SystemExit("Chrome not found; set CHROME_PATH")
    w, h = f.preview_px[0] + 20, f.preview_px[1] + 20
    subprocess.run([chrome, "--headless=new", "--screenshot=" + png,
                    "--window-size=%d,%d" % (w, h),
                    "--default-background-color=FFFFFFFF",
                    pathlib.Path(svg).resolve().as_uri()],
                   capture_output=True)
    return f, svg, png


def ringed(json_path, tag):
    f, svg_path, png_path = render(json_path, tag)
    pts, gates, xings = corners(f)
    svg = io.open(svg_path, encoding="utf-8").read(1500)
    vx, vy, vw, vh = [float(v) for v in re.search(
        r'viewBox="([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)"', svg).groups()]
    sw = float(re.search('width="([0-9.]+)"', svg).group(1))
    sh = float(re.search('height="([0-9.]+)"', svg).group(1))
    im = Image.open(png_path).convert("RGB")
    # the PNG carries a border: it is wider than the SVG's own width
    ox, oy = (im.width - sw) / 2.0, (im.height - sh) / 2.0
    sx, sy = sw / vw, sh / vh
    d = ImageDraw.Draw(im)
    r = max(9, int(im.width / 150))
    for x, y in pts:
        px, py = ox + (x - vx) * sx, oy + (y - vy) * sy
        d.ellipse([px - r, py - r, px + r, py + r], outline=(230, 30, 30),
                  width=max(3, r // 3))
    for x, y in xings:             # blue: a crossing, NOT a corner
        px, py = ox + (x - vx) * sx, oy + (y - vy) * sy
        d.ellipse([px - r, py - r, px + r, py + r], outline=(20, 60, 230),
                  width=max(3, r // 3))
    for x, y in gates:             # purple: crossing a gate lead (2.5)
        px, py = ox + (x - vx) * sx, oy + (y - vy) * sy
        d.ellipse([px - r * 1.4, py - r * 1.4, px + r * 1.4, py + r * 1.4],
                  outline=(150, 30, 200), width=max(3, r // 3))
    return im, len(pts) + 2.5 * len(gates), len(xings)


def compare(stem):
    hand = os.path.join(ROOT, stem + ".icproj.json")
    auto = os.path.join(OUT, stem + ".icproj.json")
    for p in (hand, auto):
        if not os.path.exists(p):
            print("missing:", p)
            return None
    im1, n1, x1 = ringed(hand, "hand")
    im2, n2, x2 = ringed(auto, "auto")
    W, PAD = 1900, 24
    sc = []
    for im in (im1, im2):
        sc.append(im.resize((W, max(1, int(im.height * W / im.width))),
                            Image.LANCZOS))
    tot = sum(i.height for i in sc) + PAD * 3
    c = Image.new("RGB", (W + PAD * 2, tot), "white")
    y = PAD
    for i, im in enumerate(sc):
        c.paste(im, (PAD, y))
        y += im.height + PAD
        if i == 0:
            for x in range(PAD, W + PAD):
                c.putpixel((x, y - PAD // 2), (190, 190, 190))
    out = os.path.join(HERE, "corners_%s.png" % stem)
    c.save(out)
    print("%-46s corners hand %5.1f auto %5.1f (%.2fx)   crossings %d / %d"
          % (stem[:40], n1, n2, n2 / float(n1 or 1), x1, x2))
    return out


def hand_only(stem):
    """Just the hand-drawn figure, ringed -- for checking the RULE itself
    against a drawing whose corners the user already knows by eye."""
    hand = os.path.join(ROOT, stem + ".icproj.json")
    if not os.path.exists(hand):
        print("missing:", hand)
        return None
    im, n, x = ringed(hand, "hand")
    out = os.path.join(HERE, "corners_hand_%s.png" % stem)
    im.save(out)
    print("%-46s %5.1f corners, %d crossings" % (stem[:46], n, x))
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    only = "--hand" in args
    stems = [a for a in args if not a.startswith("-")]
    for s in stems or ["Razavi_Fig_14_36b_biquad"]:
        hand_only(s) if only else compare(s)
