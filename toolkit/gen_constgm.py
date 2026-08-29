# -*- coding: utf-8 -*-
"""Constant-g_m bias without a resistor (SOP lane 3a: a non-Razavi source).

Every position and `mirror` came from `python scan_figure.py <shot>` (7/7 by
paired strokes); PMOS/NMOS from the bubbles; connectivity read off the figure
and checked line by line against the scan's H/V wire table.

Three branches hang off one rail and one ground bus:
  * P1 over the diode-connected N3, whose gate also drives N4;
  * P2 (diode-connected, so it sets every PMOS gate) over N1 in series with N4,
    which is the triode device standing in for the usual degeneration resistor
    -- that is the "without resistance" part;
  * P3 over the diode-connected N2, whose gate also drives N1.

The source figure prints no device names, so this one carries no instance
labels: the only text is V_DD.  Its caption ("Constant-g_m without
Resistance") is a caption, not part of the schematic, so it is not drawn.
"""
import os
from icproj import Schematic

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-constgm-resistorless",
    "Constant-gm bias without a resistor",
    "ConstGm",
    out_proj=os.path.join(OUT, "Constant-gm_bias_resistorless.icproj.json"),
    out_svg=os.path.join(HERE, "preview_constgm.svg"))

# ---------------------------------------------------------------- placement
# rows 100 V_DD rail | 140 the three PMOS | 180 P2 drain node | 200 P3 drain
#      220 N1/N2 | 240 P1 drain node | 280 N3/N4 | 320 the ground bus
# cols 140 P1/N3 | 220 P2/N1/N4 | 330 P3/N2
# Tightened 2026-08-29 on the user's call: the source figure is itself
# loosely drawn, and copying its 8.5% made this too airy.  "Compare with the
# original" (SOP 3A) is a FLOOR against drawing too loose -- not a ceiling.
for iid, kind, cx, cy, mir in (
        ("P1", "pmos", 150, 140, "x"),
        ("P2", "pmos", 230, 140, "x"),
        ("P3", "pmos", 320, 140, "none"),
        ("N1", "nmos", 230, 220, "x"),
        ("N2", "nmos", 320, 220, "none"),
        ("N3", "nmos", 150, 280, "x"),
        ("N4", "nmos", 210, 280, "none")):
    # underscore form so the stored name round-trips through the editor's
    # own builder (check_labels compares byte for byte)
    f.mos(iid, kind, cx, cy, mir, iid[0] + "_" + iid[1:])
f.gnd("GND", 220, 330)

# ---------------------------------------------------------------- junctions
RAIL = [120, 140, 220, 330, 350]
J = [("jvdd-%d" % i, "net-power-vdd", x, 100) for i, x in enumerate(RAIL)]
J[0] = ("jvdd-start", "net-power-vdd", RAIL[0], 100)
J[-1] = ("jvdd-end", "net-power-vdd", RAIL[-1], 100)
for jid, net, x, y in J + [
        ("JB", "net-b", 220, 170),    # P2 drain = its own gate = N1 drain
        ("JG1", "net-b", 270, 140),   # the shared PMOS gate line
        ("JA", "net-a", 140, 240),    # P1 drain = N3 drain = N3/N4 gates
        ("JG3", "net-a", 180, 280),   # the N3/N4 gate line
        ("JT", "net-c", 330, 190),    # P3 drain = N2 drain
        ("JG2", "net-c", 280, 220)]:  # the N1/N2 gate line
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
f.net("net-power-vdd", [("P1", "S"), ("P2", "S"), ("P3", "S"),
                        ("P1", "B"), ("P2", "B"), ("P3", "B")])
f.net("net-b", [("P2", "D"), ("P2", "G"), ("P1", "G"), ("P3", "G"),
                ("N1", "D")])
f.net("net-a", [("P1", "D"), ("N3", "D"), ("N3", "G"), ("N4", "G")])
f.net("net-c", [("P3", "D"), ("N2", "D"), ("N2", "G"), ("N1", "G")])
f.net("net-d", [("N1", "S"), ("N4", "D")])
f.net("net-gnd-1", [("N3", "S"), ("N4", "S"), ("N2", "S"), ("GND", "0"),
                    ("N1", "B"), ("N2", "B"), ("N3", "B"), ("N4", "B")])

# ---------------------------------------------------------------- routes
T, Jn = f.term, f.jn
f.rail("net-power-vdd", 100, RAIL)
for iid, x in (("P1", 140), ("P2", 220), ("P3", 330)):
    f.route("r-vdd-%s" % iid, "net-power-vdd",
            Jn(f._jat(x, 100)), [("to", T(iid, "S"))])

# P2 is diode-connected and sets all three PMOS gates
f.route("r-b-d", "net-b", T("P2", "D"), [("to", Jn("JB"))])
f.route("r-b-n1", "net-b", Jn("JB"), [("to", T("N1", "D"))])
f.route("r-b-tie", "net-b", Jn("JB"), [("bend", 270, 170), ("to", Jn("JG1"))])
f.route("r-b-g2", "net-b", Jn("JG1"), [("to", T("P2", "G"))])
f.route("r-b-g3", "net-b", Jn("JG1"), [("to", T("P3", "G"))])
f.route("r-b-g1", "net-b", T("P1", "G"), [("to", T("P2", "G"))])

# P1 over the diode-connected N3, which mirrors into N4
f.route("r-a-d", "net-a", T("P1", "D"), [("to", Jn("JA"))])
f.route("r-a-n3", "net-a", Jn("JA"), [("to", T("N3", "D"))])
f.route("r-a-tie", "net-a", Jn("JA"), [("bend", 180, 240), ("to", Jn("JG3"))])
f.route("r-a-g3", "net-a", Jn("JG3"), [("to", T("N3", "G"))])
f.route("r-a-g4", "net-a", Jn("JG3"), [("to", T("N4", "G"))])

# P3 over the diode-connected N2, which mirrors into N1
f.route("r-c-d", "net-c", T("P3", "D"), [("to", Jn("JT"))])
f.route("r-c-n2", "net-c", Jn("JT"), [("to", T("N2", "D"))])
f.route("r-c-tie", "net-c", Jn("JT"), [("bend", 280, 190), ("to", Jn("JG2"))])
f.route("r-c-g1", "net-c", Jn("JG2"), [("to", T("N1", "G"))])
f.route("r-c-g2", "net-c", Jn("JG2"), [("to", T("N2", "G"))])

# N1 sits on N4: the triode device that replaces the resistor
f.route("r-d", "net-d", T("N1", "S"), [("to", T("N4", "D"))])

# the ground bus -- three legs onto the one ground symbol
f.route("r-g-n3", "net-gnd-1", T("N3", "S"), [("bend", 140, 320),
                                              ("to", T("GND", "0"))])
f.route("r-g-n4", "net-gnd-1", T("N4", "S"), [("to", T("GND", "0"))])
f.route("r-g-n2", "net-gnd-1", T("N2", "S"), [("bend", 330, 320),
                                              ("to", T("GND", "0"))])

# ---------------------------------------------------------------- annotations
f.power_label("label-vdd", "net-power-vdd", "jvdd-end", 12, 6, "V_DD")

f.build(long_haul={"r-vdd-rail-1", "r-vdd-rail-2",
                   "r-b-g1",        # 80: the PMOS gate line across to P1
                   "r-b-tie", "r-c-tie",  # the two diode ties
                   "r-a-d",         # 80: P1's drain down to the N3 node
                   "r-g-n3", "r-g-n2"},   # the ground bus
        rail_ends={"jvdd-start", "jvdd-end"},
        viewbox=(105, 85, 315, 270))
