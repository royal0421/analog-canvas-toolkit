# -*- coding: utf-8 -*-
"""AIC intro (115-1) midterm, flicker-noise problem, Fig. 1: folded-cascode
op amp.  Topology copied from the 113-1 final exam Fig. 1:
  NMOS input pair M1/M2 + tail M11 (V_b5); PMOS sources M7/M8 (V_b4);
  PMOS cascodes M5/M6 (V_b3); NMOS cascodes M3/M4 (V_b2); NMOS sinks M9/M10
  (V_b1).  M1 drain folds into the M7/M5 node, M2 drain crosses the left
  column and folds into the M8/M6 node.  Differential output between M5/M3
  and M6/M4.

  columns: V_in 140 | M1 D/S 200 | tail 250 | M2 D/S 300 | left stack 420 |
           bias ports 490 | right stack 560
  rows:    rail 100 | M7/M8 140 | fold L 180 / fold R 200 | M5/M6 250 |
           out 290 | M3/M4 340, M1/M2 340 | M9/M10 400 | tail bus 370 |
           V_in2 390 | M11 430
"""
import os
from icproj import Schematic

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir, "out")
OUT = os.path.join(ROOT, "AIC-intro_Midterm-2026_Fig1_folded-cascode.icproj.json")
f = Schematic(
    "project-aicintro-midterm-fc",
    "AIC intro 115-1 midterm Fig. 1 - folded-cascode op amp",
    "Midterm_Fig1",
    out_proj=OUT,
    out_svg=os.path.join(HERE, "preview_aicintro_midterm_fc.svg"))

XL, XR, XC = 420, 560, 490          # stack D/S columns and their midline

# ---------------------------------------------------------------- placement
f.mos("M7", "pmos", XL + 10, 140, "x", "M_7")
f.mos("M8", "pmos", XR - 10, 140, "none", "M_8")
f.mos("M5", "pmos", XL + 10, 250, "x", "M_5")
f.mos("M6", "pmos", XR - 10, 250, "none", "M_6")
f.mos("M3", "nmos", XL + 10, 340, "x", "M_3")
f.mos("M4", "nmos", XR - 10, 340, "none", "M_4")
f.mos("M9", "nmos", XL + 10, 400, "x", "M_9")
f.mos("M10", "nmos", XR - 10, 400, "none", "M_10")
f.mos("M1", "nmos", 190, 340, "none", "M_1")
f.mos("M2", "nmos", 310, 340, "x", "M_2")
f.mos("M11", "nmos", 240, 430, "none", "M_11")
f.gnd("GND1", XL, 430)               # pin (420,420) = M9.S : pin-on-pin
f.gnd("GND2", XR, 430)
f.gnd("GND3", 250, 460)              # pin (250,450) = M11.S
# bias ports turned 90 deg: circle on top, pin 10 below the centre
for pid, yg in (("VB4", 140), ("VB3", 250), ("VB2", 340), ("VB1", 400)):
    f.place(pid, "port", XC, yg - 20, rotation=90)
f.port("VB5", 190, 430)
f.port("VIN1", 140, 340)
f.port("VIN2", 140, 390)
f.port("VOUTL", XL + 20, 290, mirror="x")   # the two V_out circles face
f.port("VOUTR", XR - 20, 290)               # each other across the label

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("jvdd-start", "net-power-vdd", XL - 20, 100),
        ("JV7", "net-power-vdd", XL, 100),
        ("JV8", "net-power-vdd", XR, 100),
        ("jvdd-end", "net-power-vdd", XR + 20, 100),
        ("JB4", "net-b4", XC, 140),
        ("JB3", "net-b3", XC, 250),
        ("JB2", "net-b2", XC, 340),
        ("JB1", "net-b1", XC, 400),
        ("JFL", "net-fl", XL, 180),
        ("JFR", "net-fr", XR, 200),
        ("JOL", "net-ol", XL, 290),
        ("JOR", "net-or", XR, 290),
        ("JT", "net-tail", 250, 370)):
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
f.net("net-power-vdd", [("M7", "S"), ("M8", "S"), ("M7", "B"), ("M8", "B"),
                        ("M5", "B"), ("M6", "B")])
f.net("net-b4", [("M7", "G"), ("M8", "G"), ("VB4", "P")])
f.net("net-b3", [("M5", "G"), ("M6", "G"), ("VB3", "P")])
f.net("net-b2", [("M3", "G"), ("M4", "G"), ("VB2", "P")])
f.net("net-b1", [("M9", "G"), ("M10", "G"), ("VB1", "P")])
f.net("net-fl", [("M7", "D"), ("M5", "S"), ("M1", "D")])
f.net("net-fr", [("M8", "D"), ("M6", "S"), ("M2", "D")])
f.net("net-ol", [("M5", "D"), ("M3", "D"), ("VOUTL", "P")])
f.net("net-or", [("M6", "D"), ("M4", "D"), ("VOUTR", "P")])
f.net("net-xl", [("M3", "S"), ("M9", "D")])
f.net("net-xr", [("M4", "S"), ("M10", "D")])
f.net("net-tail", [("M1", "S"), ("M2", "S"), ("M11", "D")])
f.net("net-in1", [("M1", "G"), ("VIN1", "P")])
f.net("net-in2", [("M2", "G"), ("VIN2", "P")])
f.net("net-b5", [("M11", "G"), ("VB5", "P")])
f.net("net-gnd-1", [("M9", "S"), ("GND1", "0"), ("M1", "B"), ("M2", "B"),
                    ("M3", "B"), ("M4", "B"), ("M9", "B"), ("M10", "B"),
                    ("M11", "B")])
f.net("net-gnd-2", [("M10", "S"), ("GND2", "0")])
f.net("net-gnd-3", [("M11", "S"), ("GND3", "0")])

# ---------------------------------------------------------------- routes
T, J = f.term, f.jn
f.rail("net-power-vdd", 100, [XL - 20, XL, XR, XR + 20])
f.route("r-vdd-7", "net-power-vdd", J("JV7"), [("to", T("M7", "S"))])
f.route("r-vdd-8", "net-power-vdd", J("JV8"), [("to", T("M8", "S"))])

for n, jb, ml, mr, port in (("b4", "JB4", "M7", "M8", "VB4"),
                            ("b3", "JB3", "M5", "M6", "VB3"),
                            ("b2", "JB2", "M3", "M4", "VB2"),
                            ("b1", "JB1", "M9", "M10", "VB1")):
    f.route("r-%s-l" % n, "net-" + n, T(ml, "G"), [("to", J(jb))])
    f.route("r-%s-r" % n, "net-" + n, J(jb), [("to", T(mr, "G"))])
    f.route("r-%s-p" % n, "net-" + n, J(jb), [("to", T(port, "P"))])

f.route("r-fl-7", "net-fl", T("M7", "D"), [("to", J("JFL"))])
f.route("r-fl-5", "net-fl", J("JFL"), [("to", T("M5", "S"))])
f.route("r-fl-1", "net-fl", T("M1", "D"), [("bend", 200, 180), ("to", J("JFL"))])
f.route("r-fr-8", "net-fr", T("M8", "D"), [("to", J("JFR"))])
f.route("r-fr-6", "net-fr", J("JFR"), [("to", T("M6", "S"))])
# crosses the left fold column at (420,200) with no dot, as in the original
f.route("r-fr-2", "net-fr", T("M2", "D"), [("bend", 300, 200), ("to", J("JFR"))])

f.route("r-ol-5", "net-ol", T("M5", "D"), [("to", J("JOL"))])
f.route("r-ol-3", "net-ol", J("JOL"), [("to", T("M3", "D"))])
f.route("r-ol-p", "net-ol", J("JOL"), [("to", T("VOUTL", "P"))])
f.route("r-or-6", "net-or", T("M6", "D"), [("to", J("JOR"))])
f.route("r-or-4", "net-or", J("JOR"), [("to", T("M4", "D"))])
f.route("r-or-p", "net-or", J("JOR"), [("to", T("VOUTR", "P"))])
f.route("r-xl", "net-xl", T("M3", "S"), [("to", T("M9", "D"))])
f.route("r-xr", "net-xr", T("M4", "S"), [("to", T("M10", "D"))])

f.route("r-t-1", "net-tail", T("M1", "S"), [("bend", 200, 370), ("to", J("JT"))])
f.route("r-t-2", "net-tail", T("M2", "S"), [("bend", 300, 370), ("to", J("JT"))])
f.route("r-t-11", "net-tail", J("JT"), [("to", T("M11", "D"))])
f.route("r-in1", "net-in1", T("VIN1", "P"), [("to", T("M1", "G"))])
# V_in2 comes back under the pair and crosses the tail riser at (250,390)
f.route("r-in2", "net-in2", T("M2", "G"), [("bend", 350, 340), ("bend", 350, 390),
                                           ("to", T("VIN2", "P"))])
f.route("r-b5", "net-b5", T("VB5", "P"), [("to", T("M11", "G"))])

# ------------------------------------------------- cell terminals for ports
for tid, nm, net, d, pid in (
        ("t-vb4", "V_b4", "net-b4", "input", "VB4"),
        ("t-vb3", "V_b3", "net-b3", "input", "VB3"),
        ("t-vb2", "V_b2", "net-b2", "input", "VB2"),
        ("t-vb1", "V_b1", "net-b1", "input", "VB1"),
        ("t-vb5", "V_b5", "net-b5", "input", "VB5"),
        ("t-vin1", "V_in1", "net-in1", "input", "VIN1"),
        ("t-vin2", "V_in2", "net-in2", "input", "VIN2"),
        ("t-vout1", "V_out1", "net-ol", "output", "VOUTL"),
        ("t-vout2", "V_out2", "net-or", "output", "VOUTR")):
    f.terminal(tid, nm, net, d, [pid])

# ---------------------------------------------------------------- annotations
for m in ("M7", "M5", "M3", "M9", "M2"):
    f.inst_label(m, -18, 5, "end")
for m in ("M8", "M6", "M4", "M10", "M1", "M11"):
    f.inst_label(m, 18, 5, "start")
for pid, tid in (("VB4", "t-vb4"), ("VB3", "t-vb3"),
                 ("VB2", "t-vb2"), ("VB1", "t-vb1")):
    f.port_label(pid, tid, 8, -2, "start")       # right of the raised circle
f.port_label("VB5", "t-vb5", -14, 5, "end")
f.power_label("label-vdd", "net-power-vdd", "jvdd-end", 12, 6, "V_DD")
f.text("note-vout", XC, 295, "middle", "V_out")
f.text("note-vin", 133, 370, "middle", "V_in")

f.build(long_haul={
            "r-fl-1", "r-fr-2",          # the two fold wires
            "r-in2",                     # V_in2 return under the pair
            "r-t-1", "r-t-2",            # tail bus
            "r-b4-l", "r-b4-r", "r-b3-l", "r-b3-r",
            "r-b2-l", "r-b2-r", "r-b1-l", "r-b1-r",   # gate bars
            "r-fr-8", "r-fl-5", "r-vdd-rail-1",
        },
        rail_ends={"jvdd-start", "jvdd-end"},
        viewbox=(100, 80, 560, 400))
