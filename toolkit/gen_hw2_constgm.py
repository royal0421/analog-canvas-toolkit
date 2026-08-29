# -*- coding: utf-8 -*-
"""HW2 constant-g_m reference (Lab2 slides p.13): M1/M2 + R_1 set the current,
M3/M4 mirror it, M5 copies it into the diode-connected M6/M7 stack that makes
V_REF.  M1 and M4 are the diode-connected devices of their mirrors."""
import os
from icproj import Schematic, dy_below, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic("project-hw2-constgm", "HW2 constant-gm reference with V_REF",
              "HW2ConstGm",
              out_proj=os.path.join(OUT, "HW2_constant-gm_VREF.icproj.json"),
              out_svg=os.path.join(HERE, "preview_hw2constgm.svg"))

for iid, kind, cx, cy, mir in (("M1", "pmos", 150, 140, "x"),
                               ("M3", "pmos", 250, 140, "none"),
                               ("M5", "pmos", 370, 140, "none"),
                               ("M2", "nmos", 150, 220, "x"),
                               ("M4", "nmos", 250, 220, "none"),
                               ("M6", "nmos", 370, 220, "none"),
                               ("M7", "nmos", 370, 290, "none")):
    f.mos(iid, kind, cx, cy, mir, "M_" + iid[1:])
f.passive("R1", "resistor", 140, 280, "R_1")
for iid, x in (("G1", 140), ("G2", 260), ("G3", 380)):
    f.gnd(iid, x, 330)
f.port("VREF", 450, 180, mirror="x")

RAIL = [120, 140, 260, 380, 400]
J = [("jvdd-%d" % i, "net-power-vdd", x, 100) for i, x in enumerate(RAIL)]
J[0] = ("jvdd-start", "net-power-vdd", RAIL[0], 100)
J[-1] = ("jvdd-end", "net-power-vdd", RAIL[-1], 100)
for jid, net, x, y in J + [("JG", "net-b", 200, 140),
                           ("JA", "net-b", 140, 180),
                           ("JB", "net-c", 260, 190),
                           ("JGN", "net-c", 210, 220),
                           ("JR", "net-ref", 380, 180),
                           ("JS", "net-67", 380, 250)]:
    f.junction(jid, net, x, y)

PB = [(m, "B") for m in ("M1", "M3", "M5")]
f.net("net-power-vdd", [("M1", "S"), ("M3", "S"), ("M5", "S")] + PB)
f.net("net-b", [("M1", "D"), ("M1", "G"), ("M3", "G"), ("M5", "G"),
                ("M2", "D")])
f.net("net-c", [("M3", "D"), ("M4", "D"), ("M4", "G"), ("M2", "G")])
f.net("net-r", [("M2", "S"), ("R1", "1")])
f.net("net-ref", [("M5", "D"), ("M6", "D"), ("M6", "G"), ("VREF", "P")])
f.net("net-67", [("M6", "S"), ("M7", "D"), ("M7", "G")])
NB = [(m, "B") for m in ("M2", "M4", "M6", "M7")]
f.net("net-gnd-1", [("R1", "2"), ("G1", "0"), ("M4", "S"), ("G2", "0"),
                    ("M7", "S"), ("G3", "0")] + NB)

T, Jn = f.term, f.jn
f.rail("net-power-vdd", 100, RAIL)
for iid, x in (("M1", 140), ("M3", 260), ("M5", 380)):
    f.route("r-v-%s" % iid, "net-power-vdd", Jn(f._jat(x, 100)),
            [("to", T(iid, "S"))])

f.route("r-b1", "net-b", T("M1", "D"), [("to", Jn("JA"))])
f.route("r-b2", "net-b", Jn("JA"), [("to", T("M2", "D"))])
f.route("r-b3", "net-b", Jn("JA"), [("bend", 200, 180), ("to", Jn("JG"))])
f.route("r-b4", "net-b", Jn("JG"), [("to", T("M1", "G"))])
f.route("r-b5", "net-b", Jn("JG"), [("to", T("M3", "G"))])
f.route("r-b6", "net-b", T("M3", "G"), [("to", T("M5", "G"))])
f.route("r-c1", "net-c", T("M3", "D"), [("to", Jn("JB"))])
f.route("r-c2", "net-c", Jn("JB"), [("to", T("M4", "D"))])
f.route("r-c3", "net-c", Jn("JB"), [("bend", 210, 190), ("to", Jn("JGN"))])
f.route("r-c4", "net-c", Jn("JGN"), [("to", T("M2", "G"))])
f.route("r-c5", "net-c", Jn("JGN"), [("to", T("M4", "G"))])
f.route("r-r", "net-r", T("M2", "S"), [("to", T("R1", "1"))])

f.route("r-ref1", "net-ref", T("M5", "D"), [("to", Jn("JR"))])
f.route("r-ref2", "net-ref", Jn("JR"), [("to", T("M6", "D"))])
f.route("r-ref3", "net-ref", Jn("JR"), [("to", T("VREF", "P"))])
f.route("r-ref4", "net-ref", Jn("JR"), [("bend", 330, 180), ("bend", 330, 220),
                                        ("to", T("M6", "G"))])
f.route("r-671", "net-67", T("M6", "S"), [("to", Jn("JS"))])
f.route("r-672", "net-67", Jn("JS"), [("to", T("M7", "D"))])
f.route("r-673", "net-67", Jn("JS"), [("bend", 330, 250), ("bend", 330, 290),
                                      ("to", T("M7", "G"))])

f.route("r-g1", "net-gnd-1", T("R1", "2"), [("to", T("G1", "0"))])
f.route("r-g2", "net-gnd-1", T("M4", "S"), [("to", T("G2", "0"))])
f.route("r-g3", "net-gnd-1", T("M7", "S"), [("to", T("G3", "0"))])

f.terminal("t-vref", "V_REF", "net-ref", "output", ["VREF"])
for iid in ("M1", "M2"):
    f.inst_label(iid, -18, 5, "end")
for iid in ("M4", "M5", "M6", "M7"):
    f.inst_label(iid, 18, 5, "start")
# M_3 sits under the gate line that runs on to M_5, so its label drops below
f.inst_label("M3", 18, dy_below(20), "start")
f.inst_label("R1", -13, 5, "end")
f.port_label("VREF", "t-vref", LABEL_PORT, 5, "start")
f.power_label("label-vdd", "net-power-vdd", "jvdd-end", 12, 6, "V_DD")

f.build(long_haul={"r-vdd-rail-1", "r-vdd-rail-2", "r-b3", "r-b6",
                   "r-c1", "r-c3", "r-ref1", "r-ref3", "r-ref4", "r-673",
                   "r-g1", "r-g2"},
        rail_ends={"jvdd-start", "jvdd-end"}, viewbox=(80, 85, 460, 270))
