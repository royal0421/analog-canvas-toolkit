# -*- coding: utf-8 -*-
"""Razavi Fig. 9.83 (problem 68): common-gate stage in a cascode current
mirror.

I_REF sets M_REF; M_5 and M_2 copy that bias; M_4 / M_3 form the pmos mirror
that loads the stage; M_1 is the common-gate device with V_b on its gate,
V_in on its source and V_out on its drain.

2026-09-01: ported from its own hand-written skeleton onto the shared engine.
The coordinates are unchanged; the port fixes the drift -- the old copy still
wrote schema v31, its own `explicit-net-property` evidence, and
`sizeScale 0.65` (the label size was settled at 0.58 on 2026-08-29, so this
figure had been printing bigger text than the rest of the library).
"""
import os
from icproj import Schematic, name_suffix

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-razavi-fig-9-83",
    "Razavi Fig. 9.83 — common-gate stage",
    "Fig_9_83_CG",
    out_proj=os.path.join(OUT, "Razavi_Fig_9_83_CG.icproj.json"),
    out_svg=os.path.join(HERE, "preview_fig983.svg"))

# ---------------------------------------------------------------- placement
#   column A 170 I_REF / M_REF | B 320 M_4 over M_5 | C 450 M_3 / M_1 / M_2
#   rows 100 rail | 140 pmos | 190 output tap | 230 I_REF and M_1
#        270 input tap | 310 nmos row | 350 grounds
f.isrc("IREF", 170, 230, "I_REF")
f.mos("MREF", "nmos", 180, 310, "x", "M_REF")
f.gnd("GND1", 170, 350)
f.mos("M4", "pmos", 330, 140, "x", "M_4")
f.mos("M5", "nmos", 310, 310, "none", "M_5")
f.gnd("GND2", 320, 350)
f.mos("M3", "pmos", 440, 140, "none", "M_3")
f.mos("M1", "nmos", 460, 230, "x", "M_1")
f.mos("M2", "nmos", 440, 310, "none", "M_2")
f.gnd("GND3", 450, 350)
f.port("VOUT", 480, 190, mirror="x")
f.port("VB", 510, 230, mirror="x", filled=True)
f.port("VIN", 420, 270)

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("jvdd-start", "net-power-vdd", 150, 100),
        ("JV_A", "net-power-vdd", 170, 100),
        ("JV_B", "net-power-vdd", 320, 100),
        ("JV_C", "net-power-vdd", 450, 100),
        ("jvdd-end", "net-power-vdd", 470, 100),
        ("JREF", "net-nbias", 170, 270),
        ("JG", "net-nbias", 210, 310),
        ("JG2", "net-nbias", 270, 310),
        ("JD4", "net-pbias", 320, 180),
        ("J4G", "net-pbias", 370, 140),
        ("JOUT", "net-vout", 450, 190),
        ("JIN", "net-vin", 450, 270)):
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
f.net("net-power-vdd", [("M3", "S"), ("M4", "S"), ("IREF", "+"),
                        ("M3", "B"), ("M4", "B")])
f.net("net-nbias", [("IREF", "-"), ("MREF", "D"), ("MREF", "G"),
                    ("M5", "G"), ("M2", "G")])
f.net("net-pbias", [("M4", "D"), ("M4", "G"), ("M3", "G"), ("M5", "D")])
f.net("net-vout", [("M3", "D"), ("M1", "D"), ("VOUT", "P")])
f.net("net-vb", [("M1", "G"), ("VB", "P")])
f.net("net-vin", [("M1", "S"), ("M2", "D"), ("VIN", "P")])
f.net("net-gnd-1", [("GND1", "0"), ("MREF", "S"), ("MREF", "B"),
                    ("M5", "B"), ("M2", "B"), ("M1", "B")])
f.net("net-gnd-2", [("GND2", "0"), ("M5", "S")])
f.net("net-gnd-3", [("GND3", "0"), ("M2", "S")])

# ---------------------------------------------------------------- routes
T, J = f.term, f.jn
f.rail("net-power-vdd", 100, [150, 170, 320, 450, 470])
f.route("r-vdd-drop-iref", "net-power-vdd", J("JV_A"),
        [("to", T("IREF", "+"))])
f.route("r-vdd-drop-m4", "net-power-vdd", J("JV_B"), [("to", T("M4", "S"))])
f.route("r-vdd-drop-m3", "net-power-vdd", J("JV_C"), [("to", T("M3", "S"))])

f.route("r-nb-1", "net-nbias", T("IREF", "-"), [("to", J("JREF"))])
f.route("r-nb-2", "net-nbias", J("JREF"), [("to", T("MREF", "D"))])
f.route("r-nb-3", "net-nbias", J("JREF"), [("bend", 210, 270),
                                           ("to", J("JG"))])
f.route("r-nb-4", "net-nbias", J("JG"), [("to", T("MREF", "G"))])
f.route("r-nb-5", "net-nbias", J("JG"), [("to", J("JG2"))])
f.route("r-nb-6", "net-nbias", J("JG2"), [("to", T("M5", "G"))])
f.route("r-nb-7", "net-nbias", J("JG2"),
        [("bend", 270, 380), ("bend", 380, 380), ("bend", 380, 310),
         ("to", T("M2", "G"))])

f.route("r-pb-1", "net-pbias", T("M4", "D"), [("to", J("JD4"))])
f.route("r-pb-2", "net-pbias", J("JD4"), [("to", T("M5", "D"))])
f.route("r-pb-3", "net-pbias", T("M4", "G"), [("to", J("J4G"))])
f.route("r-pb-4", "net-pbias", J("J4G"), [("to", T("M3", "G"))])
f.route("r-pb-5", "net-pbias", J("J4G"), [("bend", 370, 180),
                                          ("to", J("JD4"))])

f.route("r-out-1", "net-vout", T("M3", "D"), [("to", J("JOUT"))])
f.route("r-out-2", "net-vout", J("JOUT"), [("to", T("M1", "D"))])
f.route("r-out-3", "net-vout", J("JOUT"), [("to", T("VOUT", "P"))])
f.route("r-vb-1", "net-vb", T("M1", "G"), [("to", T("VB", "P"))])
f.route("r-in-1", "net-vin", T("M1", "S"), [("to", J("JIN"))])
f.route("r-in-2", "net-vin", J("JIN"), [("to", T("M2", "D"))])
f.route("r-in-3", "net-vin", J("JIN"), [("to", T("VIN", "P"))])
f.route("r-g1", "net-gnd-1", T("MREF", "S"), [("to", T("GND1", "0"))])
f.route("r-g2", "net-gnd-2", T("M5", "S"), [("to", T("GND2", "0"))])
f.route("r-g3", "net-gnd-3", T("M2", "S"), [("to", T("GND3", "0"))])

# ------------------------------------------------- cell terminals for ports
f.terminal("terminal-vout", "Vout", "net-vout", "output", ["VOUT"])
f.terminal("terminal-vin", "Vin", "net-vin", "input", ["VIN"])
f.terminal("terminal-vb", "Vb", "net-vb", "input", ["VB"])

# ---------------------------------------------------------------- annotations
f.inst_label("IREF", -18, 5, "end")
f.inst_label("MREF", -18, 5, "end")
f.inst_label("M5", 18, 5, "start")
f.inst_label("M2", 18, 5, "start")
f.inst_label("M4", -18, 5, "end")
f.inst_label("M3", 18, 5, "start")
f.inst_label("M1", -18, 5, "end")
f.port_label("VOUT", "terminal-vout", 11, 5, "start")
f.port_label("VB", "terminal-vb", 11, 5, "start")
f.port_label("VIN", "terminal-vin", -16, 5, "end")
f.power_label("label-vdd", "net-power-vdd", "jvdd-end", 12, 6,
              name_suffix("V_DD", " = 1.8 V"))

f.build(long_haul={"r-vdd-rail-0", "r-vdd-rail-1", "r-vdd-rail-2",
                   "r-vdd-rail-3",   # the V_DD rail itself
                   "r-nb-3",         # 40+40: I_REF node down to the gate bus
                   "r-nb-5",         # 60: the gate bus across to M_5
                   "r-nb-7",         # the long way round to M_2's gate
                   "r-pb-5",         # 50+40: M_4's gate across to its drain
                   "r-vdd-drop-iref",  # 110: I_REF hangs well below the rail
                   "r-pb-2",         # 110: the pmos drain node down to M_5
                   "r-pb-4"},        # 50: the pmos gate bus across to M_3
        rail_ends={"jvdd-start", "jvdd-end"},
        viewbox=(120, 75, 440, 310))
