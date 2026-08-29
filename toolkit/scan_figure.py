# -*- coding: utf-8 -*-
"""scan_figure.py — turn a textbook screenshot into hard topology facts.

    python scan_figure.py <screenshot.png> [--ref=<px>:<units>]

Replaces the "zoom to 5-6x and look at each transistor" step in SOP §3B/§8-2.
Everything it prints is measured, not judged, so it cannot be wrong the way
eyeballing can.  What it gives you:

  scale        px per drawing unit, derived from the MOS channel bar (25 units)
  MOS table    centre, mirror, D/S column x, gate pin x  -- mirror comes from
               "is the gate bar left or right of the channel bar", which is the
               single judgement call that used to cost a re-draw
  H / V wires  every wire segment.  A GAP inside a horizontal row is proof that
               two structures are NOT connected (this is what settles
               diode-connected vs cross-coupled in one glance)
  dots         solid blobs, split into junction dots / current-source arrow
               heads / MOS source arrows by area.  A crossing with NO dot is a
               crossing, not a node.
  density      the circuit's bbox, aspect, and <component height / figure
               height> for every standard symbol size -- feed the matching row
               straight into build(density_ref=...) so the FIRST layout is
               already at the textbook's density.  With no MOS on the page
               there is no automatic scale: pass --ref=<px>:<units>, e.g.
               --ref=140:50 for an opamp triangle measured at 140 px.

Reference sizes (razavi-v1, drawing units): channel bar 25 tall x 2.9 wide,
gate bar 19.2 tall x 2.9 wide, gate bar centre -10.35, channel bar centre
-5.12, D/S column +10, gate pin -20 (all for an unmirrored device; mirror "x"
negates x).
"""
import sys, os
import numpy as np
from PIL import Image

CHANNEL_H_UNITS = 25.0
GATE_BAR_CENTRE = -10.348837      # (-11.802326 + -8.895349) / 2
CHAN_BAR_CENTRE = -5.116279       # (-6.569767 + -3.662791) / 2


def runs(vec, minlen):
    out, s = [], None
    for i, v in enumerate(vec):
        if v and s is None:
            s = i
        elif not v and s is not None:
            if i - s >= minlen:
                out.append((s, i - 1))
            s = None
    if s is not None and len(vec) - s >= minlen:
        out.append((s, len(vec) - 1))
    return out


def merge_lines(raw, tol=2):
    """raw: list of (along, a0, a1) -> merge consecutive `along` with the same
    span into one thick line record."""
    out = []
    for along, a0, a1 in raw:
        hit = None
        for rec in out:
            if (abs(rec["a0"] - a0) <= tol and abs(rec["a1"] - a1) <= tol
                    and along - rec["hi"] <= 2):
                hit = rec
                break
        if hit:
            hit["hi"] = along
            hit["a0"] = min(hit["a0"], a0)
            hit["a1"] = max(hit["a1"], a1)
        else:
            out.append({"lo": along, "hi": along, "a0": a0, "a1": a1})
    for rec in out:
        rec["mid"] = (rec["lo"] + rec["hi"]) / 2.0
        rec["thick"] = rec["hi"] - rec["lo"] + 1
    return out


def mos_pairs(vbars):
    """Find MOS devices in a schematic that does NOT use razavi-v1's filled
    bars (SOP lane 3a: Sedra, Gray, paper figures).

    In every other common house style a MOS is drawn as two parallel vertical
    strokes of the SAME height -- the gate plate and the channel -- a few pixels
    apart, with the drain and source leads coming off the channel side.  So:
    pair up equal-span vertical runs, then decide which member is the channel by
    which one the D/S column is nearer.  The gate plate is the other one, and
    that is what fixes `mirror` -- the single reading that used to have to be
    done by eye, and the one that costs a redraw when it is wrong.

    Returns [(cx, cy, mirror, ds_col, gate_x, body_h)], sorted left to right.
    """
    cand = []
    for i, a in enumerate(vbars):
        for bb in vbars[i + 1:]:
            # Concentric and about the same height -- NOT "both ends line up".
            # House styles draw the gate plate a little shorter than the
            # channel (2026-08-29: 52 px against 59, which an end-tolerance of
            # 3 px threw away and the figure came back with no transistors).
            ha = a["a1"] - a["a0"] + 1
            hb = bb["a1"] - bb["a0"] + 1
            if abs((a["a0"] + a["a1"]) - (bb["a0"] + bb["a1"])) / 2.0 > 5:
                continue
            if not 0.72 <= float(ha) / hb <= 1.4:
                continue
            d = abs(a["mid"] - bb["mid"])
            if not (8 <= d <= 30):
                continue
            if a["thick"] < 3 or bb["thick"] < 3:
                continue
            top, bot = min(a["a0"], bb["a0"]), max(a["a1"], bb["a1"])
            body = bot - top + 1
            # A device is a tall, narrow pair; the label glyphs that also pair
            # up ("M" next to a subscript) are nearly as wide as they are tall.
            # Measured on the 19-device figure: real 67/16 = 4.2, text 34/29 =
            # 1.2.  Without this the scan reported the labels as transistors.
            if body < 2.5 * d:
                continue
            mean = (a["mid"] + bb["mid"]) / 2.0
            # the D/S column: a run that passes the body by, off to one side
            col = None
            for r in vbars:
                if r is a or r is bb:
                    continue
                gap = abs(r["mid"] - mean)
                if not (15 <= gap <= 4 * d):
                    continue
                # What separates the drain/source column from the gate riser is
                # WHERE it meets the device: D and S leave from the two ENDS of
                # the channel, while a gate riser runs past the device's middle.
                # (Neither "nearest" nor "longest" alone gets this right: the
                # nearest run to M_B is a scrap, and the longest run next to
                # M_8/M_9/M_10/M_12 is their shared gate riser.  Both mistakes
                # flip `mirror`, which costs a full redraw.)
                cy = (top + bot) / 2.0
                if r["a0"] <= cy <= r["a1"]:
                    continue
                if not (abs(r["a1"] - top) <= 15 or abs(r["a0"] - bot) <= 15):
                    continue
                if col is None or gap < abs(col["mid"] - mean):
                    col = r
            if col is None:
                continue
            chan, gate = ((a, bb) if abs(a["mid"] - col["mid"])
                          < abs(bb["mid"] - col["mid"]) else (bb, a))
            cand.append({"cx": (chan["mid"] + gate["mid"]) / 2.0,
                         "cy": (top + bot) / 2.0, "d": d, "body": body,
                         "mirror": "x" if gate["mid"] > chan["mid"] else "none",
                         "col": col["mid"], "gate": gate["mid"],
                         "strokes": (id(a), id(bb))})
    if not cand:
        return []

    # Every MOS in one figure is drawn at the same size, so the true devices
    # all share one stroke separation and one body height.  Anything off those
    # two modes is a coincidental pairing (ground-symbol edges, bubble arcs,
    # a lead that happens to span the same rows) -- without this filter the
    # 19-device figure that this was built on reported 38.
    def mode(key, q):
        vals = sorted(round(c[key] / q) * q for c in cand)
        return max(set(vals), key=vals.count)

    dm, bm = mode("d", 1), mode("body", 2)
    keep = [c for c in cand
            if abs(c["d"] - dm) <= 3 and abs(c["body"] - bm) <= 0.1 * bm]

    # A stroke belongs to exactly one device: take the best-fitting pairs first.
    keep.sort(key=lambda c: (abs(c["d"] - dm), abs(c["body"] - bm)))
    used, out = set(), []
    for c in keep:
        if used & set(c["strokes"]):
            continue
        used |= set(c["strokes"])
        out.append((c["cx"], c["cy"], c["mirror"], c["col"], c["gate"],
                    c["body"]))
    return sorted(out)


def solid_blobs(b, k=9):
    """Centres of every fully-black k x k square, clustered."""
    h = k // 2
    I = b.astype(np.int32).cumsum(0).cumsum(1)

    def area(y0, x0, y1, x1):
        a = I[y1, x1]
        if y0 > 0:
            a -= I[y0 - 1, x1]
        if x0 > 0:
            a -= I[y1, x0 - 1]
        if y0 > 0 and x0 > 0:
            a += I[y0 - 1, x0 - 1]
        return a

    H, W = b.shape
    cands = set()
    for y in range(h, H - h):
        for x in range(h, W - h):
            if area(y - h, x - h, y + h, x + h) == k * k:
                cands.add((x, y))
    used, clusters = set(), []
    for p in list(cands):
        if p in used:
            continue
        stack, comp = [p], []
        used.add(p)
        while stack:
            cx, cy = stack.pop()
            comp.append((cx, cy))
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    q = (cx + dx, cy + dy)
                    if q in cands and q not in used:
                        used.add(q)
                        stack.append(q)
        xs = [q[0] for q in comp]
        ys = [q[1] for q in comp]
        clusters.append((sum(xs) / len(xs), sum(ys) / len(ys), len(comp)))
    return sorted(clusters, key=lambda c: (round(c[1] / 10), c[0]))


# Heights of the razavi-v1 symbols, in drawing units.  The scan prints the
# ratio for every one of these so you can read off whichever component the
# figure actually contains -- no need to identify it first.
REF_HEIGHTS = [("MOS channel bar", 25), ("opamp triangle", 50),
               ("BJT", 60), ("resistor pin-to-pin", 40)]


def ink_bands(b, gap=15):
    """Split the page into blocks of rows separated by >= `gap` blank rows.

    A textbook screenshot usually holds the circuit plus a caption ("Figure
    8.69") and sometimes the problem text; this separates them so the density
    numbers describe the circuit alone.
    """
    rows = b.any(axis=1)
    bands, start, blank = [], None, 0
    for y, has in enumerate(rows):
        if has:
            if start is None:
                start = y
            blank = 0
        elif start is not None:
            blank += 1
            if blank >= gap:
                bands.append((start, y - blank))
                start = None
    if start is not None:
        bands.append((start, len(rows) - 1))
    return bands


def density_report(b, scale):
    bands = ink_bands(b)
    if not bands:
        return
    # The circuit is the TALLEST block.  Ranking by ink pixels instead
    # picks the problem text, which is dense but only ~100 px tall
    # (Fig 8.69).
    best = max(bands, key=lambda t: (t[1] - t[0],
                                     int(b[t[0]:t[1] + 1].sum())))
    y0, y1 = best
    xs = np.nonzero(b[y0:y1 + 1].any(axis=0))[0]
    x0, x1 = int(xs.min()), int(xs.max())
    w, h = x1 - x0 + 1, y1 - y0 + 1
    print("\nDENSITY REFERENCE")
    if len(bands) > 1:
        print("  row blocks: %s  -> taking the tallest as the circuit"
              % ", ".join("y%d..%d" % t for t in bands))
    print("  circuit bbox  x %d..%d  y %d..%d   %d x %d px" % (x0, x1, y0, y1, w, h))
    print("  aspect (w/h)  %.2f   <- match this" % (float(w) / h))
    if not scale:
        print("  no scale: pass --ref <px>:<units> (e.g. the opamp triangle"
              " height) to get the unit figures")
        return
    print("  scale %.3f px/unit  ->  figure is %.0f x %.0f units"
          % (scale, w / scale, h / scale))
    print("  component height / figure height -- feed the right row to"
          " build(density_ref=...):")
    for tag, units in REF_HEIGHTS:
        print("      %-22s %5.1f%%" % (tag, 100.0 * units * scale / h))


def main(path, ref=None):
    im = Image.open(path).convert("L")
    b = np.array(im) < 128
    H, W = b.shape
    print("image: %s  %dx%d" % (os.path.basename(path), W, H))

    # ---- filled bars (MOS gate bar + channel bar) --------------------------
    raw = []
    for x in range(W):
        for (y0, y1) in runs(b[:, x], 30):
            raw.append((x, y0, y1))
    vbars = merge_lines(raw)
    # A razavi-v1 channel bar is thick AND SHORT -- 25 drawing units, so never
    # more than about a sixth of the figure.  Thickness alone is not enough:
    # a figure drawn with heavy 8 px strokes has WIRES that pass `thick >= 6`,
    # and the tallest of those then sets a nonsense scale (2026-08-29: a
    # 397 px wire was read as the 25-unit channel bar, giving 15.9 px/unit and
    # one transistor at x = -43).
    bars = [r for r in vbars
            if r["thick"] >= 6 and (r["a1"] - r["a0"] + 1) <= 0.25 * H]
    # Read it as razavi-v1 first; keep the rows so we can tell whether that
    # reading actually produced anything before committing to it.
    rows, tall, scale = [], None, None
    if bars:
        tall = max(r["a1"] - r["a0"] + 1 for r in bars)
        scale = tall / CHANNEL_H_UNITS
        chans = [r for r in bars if (r["a1"] - r["a0"] + 1) > 0.88 * tall]
        gates = [r for r in bars if r not in chans]
        for c in sorted(chans, key=lambda r: r["mid"]):
            cy = (c["a0"] + c["a1"]) / 2.0
            g = min((r for r in gates
                     if abs((r["a0"] + r["a1"]) / 2.0 - cy) < 0.2 * tall
                     and abs(r["mid"] - c["mid"]) < 1.2 * scale * 10),
                    key=lambda r: abs(r["mid"] - c["mid"]), default=None)
            if g is None:
                continue
            mirror = "x" if g["mid"] > c["mid"] else "none"
            sgn = -1.0 if mirror == "x" else 1.0
            cx = c["mid"] - sgn * CHAN_BAR_CENTRE * scale
            rows.append((cx, cy, mirror, cx + sgn * 10 * scale,
                         cx - sgn * 20 * scale))

    if rows:
        print("scale: %.3f px/unit  (tallest bar %d px = channel bar 25 units)"
              % (scale, tall))
        print("\nMOS devices (mirror from gate-bar side):")
        print("  %-9s %-9s %-7s %-9s %-9s" %
              ("centre_x", "centre_y", "mirror", "D/S col", "gate pin"))
        for r in rows:
            print("  %-9.1f %-9.1f %-7s %-9.1f %-9.1f" % r)
    else:
        # Either no filled bars at all, or they paired into nothing -- a
        # heavy-stroke figure can produce "bars" that are really wires.  Either
        # way this is not razavi-v1: fall back to the two-parallel-strokes
        # reading, which also hands us a scale (the body IS the channel bar).
        bars, scale = [], None
        pairs = mos_pairs(vbars)
        if pairs:
            body = sorted(p[5] for p in pairs)[len(pairs) // 2]   # modal-ish
            scale = body / CHANNEL_H_UNITS
            print("no filled bars -- generic style; %d MOS found by paired "
                  "strokes" % len(pairs))
            print("scale: %.3f px/unit  (body %d px = channel bar 25 units)"
                  % (scale, body))
            print("\nMOS devices (mirror from gate-plate side; type comes from"
                  " the bubble -- read that off the image):")
            print("  %-9s %-9s %-7s %-9s %-9s" %
                  ("centre_x", "centre_y", "mirror", "D/S col", "gate pin"))
            for cx, cy, mir, col, gx, _h in pairs:
                print("  %-9.1f %-9.1f %-7s %-9.1f %-9.1f"
                      % (cx, cy, mir, col, gx))
        else:
            print("no MOS found -- is this a MOS schematic?")
    if ref:
        px, units = (float(v) for v in ref.split(":"))
        scale = px / units
        print("scale: %.3f px/unit  (--ref %g px = %g units)"
              % (scale, px, units))

    # ---- wires --------------------------------------------------------------
    for axis, label, minlen in ((0, "HORIZONTAL", 40), (1, "VERTICAL", 40)):
        raw = []
        if axis == 0:
            for y in range(H):
                for (x0, x1) in runs(b[y], minlen):
                    raw.append((y, x0, x1))
        else:
            for x in range(W):
                for (y0, y1) in runs(b[:, x], minlen):
                    raw.append((x, y0, y1))
        lines = [r for r in merge_lines(raw) if r["thick"] < 6 or axis == 0]
        # anti-aliasing can leave a thin duplicate one pixel off the real
        # wire; drop any record another record already covers.
        lines = [r for r in lines
                 if not any(o is not r and o["thick"] >= r["thick"]
                            and abs(o["mid"] - r["mid"]) < 4
                            and o["a0"] <= r["a0"] and o["a1"] >= r["a1"]
                            for o in lines)]
        print("\n%s wires (>=%d px).  Two records on the same coordinate = a "
              "GAP = not connected." % (label, minlen))
        prev = None
        for r in sorted(lines, key=lambda r: (round(r["mid"]), r["a0"])):
            tag = ""
            if (prev is not None and abs(prev["mid"] - r["mid"]) < 3
                    and r["a0"] > prev["a1"]):
                tag = "   <-- GAP %d px after the previous run" % (
                    r["a0"] - prev["a1"])
            print("  %s=%-6.1f  %s %d..%d  len=%-5d thick=%d%s"
                  % ("y" if axis == 0 else "x", r["mid"],
                     "x" if axis == 0 else "y", r["a0"], r["a1"],
                     r["a1"] - r["a0"] + 1, r["thick"], tag))
            prev = r

    # ---- solid blobs --------------------------------------------------------
    # The detector kernel has to track the figure's resolution, or a
    # low-DPI screenshot finds nothing at all (2026-08-29: Fig 14.36 at
    # 656 px wide reported zero dots with a fixed 9x9 kernel).  Wire
    # thickness is the scale that is always available, MOS or not.
    thick = sorted(r["thick"] for r in merge_lines(
        [(y, x0, x1) for y in range(H) for (x0, x1) in runs(b[y], 40)]))
    wire = thick[len(thick) // 2] if thick else 3
    k = max(5, 2 * wire + 1)
    lo, hi = 0.55 * k * k, 1.15 * k * k
    print("\nSolid blobs, %dx%d kernel (median wire %d px).  junction dot ~ "
          "%d-%d px:" % (k, k, wire, round(lo), round(hi)))
    for cx, cy, n in solid_blobs(b, k):
        kind = ("junction dot" if lo <= n <= hi else
                "arrow head / glyph" if n > hi else "small mark")
        print("  (%4.0f, %4.0f)  n=%-3d  %s" % (cx, cy, n, kind))
    density_report(b, scale)

    print("\nReminder: a wire crossing with NO dot is a crossing, not a node.")
    print("Reminder: on a figure with passives, a GAP in a wire run is usually"
          " a COMPONENT BODY sitting there, not a disconnection -- confirm"
          " against the component list before reading it as 'not connected'.")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ref = next((a.split("=", 1)[1] for a in sys.argv[1:]
                if a.startswith("--ref=")), None)
    if len(args) != 1:
        sys.exit(__doc__)
    main(args[0], ref)
