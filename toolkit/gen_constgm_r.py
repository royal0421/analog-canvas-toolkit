# -*- coding: utf-8 -*-
"""Constant-g_m WITH resistance (Lab2 slides p.6): PMOS mirror P1/P2 over the
NMOS pair N1/N2, N2 diode-connected, R_1 degenerating N1's source."""
import os
from icproj import Schematic

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic("project-constgm-r", "Constant-gm bias with a resistor",
              "ConstGmR",
              out_proj=os.path.join(OUT, "Constant-gm_bias_with-resistor.icproj.json"),
              out_svg=os.path.join(HERE, "preview_constgm_r.svg"))

for iid, kind, cx, cy, mir in (("P1", "pmos", 150, 140, "x"),
                               ("P2", "pmos", 250, 140, "none"),
                               ("N1", "nmos", 150, 220, "x"),
                               ("N2", "nmos", 250, 220, "none")):
    f.mos(iid, kind, cx, cy, mir, iid[0] + "_" + iid[1:])
f.passive("R1", "resistor", 140, 280, "R_1")
f.gnd("GND", 200, 330)

RAIL = [120, 140, 260, 280]
J = [("jvdd-%d" % i, "net-power-vdd", x, 100) for i, x in enumerate(RAIL)]
J[0] = ("jvdd-start", "net-power-vdd", RAIL[0], 100)
J[-1] = ("jvdd-end", "net-power-vdd", RAIL[-1], 100)
for jid, net, x, y in J + [("JG", "net-b", 190, 140),
                           ("JA", "net-b", 140, 180),
                           ("JC", "net-c", 260, 190),
                           ("JGN", "net-c", 210, 220)]:
    f.junction(jid, net, x, y)

f.net("net-power-vdd", [("P1", "S"), ("P2", "S"), ("P1", "B"), ("P2", "B")])
f.net("net-b", [("P1", "D"), ("P1", "G"), ("P2", "G"), ("N1", "D")])
f.net("net-c", [("P2", "D"), ("N2", "D"), ("N2", "G"), ("N1", "G")])
f.net("net-r", [("N1", "S"), ("R1", "1")])
f.net("net-gnd-1", [("R1", "2"), ("N2", "S"), ("GND", "0"),
                    ("N1", "B"), ("N2", "B")])

T, Jn = f.term, f.jn
f.rail("net-power-vdd", 100, RAIL)
f.route("r-v1", "net-power-vdd", Jn(f._jat(140, 100)), [("to", T("P1", "S"))])
f.route("r-v2", "net-power-vdd", Jn(f._jat(260, 100)), [("to", T("P2", "S"))])
f.route("r-b1", "net-b", T("P1", "D"), [("to", Jn("JA"))])
f.route("r-b2", "net-b", Jn("JA"), [("to", T("N1", "D"))])
f.route("r-b3", "net-b", Jn("JA"), [("bend", 190, 180), ("to", Jn("JG"))])
f.route("r-b4", "net-b", Jn("JG"), [("to", T("P1", "G"))])
f.route("r-b5", "net-b", Jn("JG"), [("to", T("P2", "G"))])
f.route("r-c1", "net-c", T("P2", "D"), [("to", Jn("JC"))])
f.route("r-c2", "net-c", Jn("JC"), [("to", T("N2", "D"))])
f.route("r-c3", "net-c", Jn("JC"), [("bend", 210, 190), ("to", Jn("JGN"))])
f.route("r-c4", "net-c", Jn("JGN"), [("to", T("N1", "G"))])
f.route("r-c5", "net-c", Jn("JGN"), [("to", T("N2", "G"))])
f.route("r-r", "net-r", T("N1", "S"), [("to", T("R1", "1"))])
f.route("r-g1", "net-gnd-1", T("R1", "2"), [("bend", 140, 320),
                                            ("to", T("GND", "0"))])
f.route("r-g2", "net-gnd-1", T("N2", "S"), [("bend", 260, 320),
                                            ("to", T("GND", "0"))])

f.power_label("label-vdd", "net-power-vdd", "jvdd-end", 12, 6, "V_DD")
f.inst_label("R1", 13, 5, "start")

f.build(long_haul={"r-vdd-rail-1", "r-b3", "r-c1", "r-c3", "r-g1", "r-g2"},
        rail_ends={"jvdd-start", "jvdd-end"}, viewbox=(95, 85, 250, 275))
