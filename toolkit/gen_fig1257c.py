# -*- coding: utf-8 -*-
"""Razavi Fig. 12.57(c): differential pair M3/M4 with a PMOS current-mirror
load M5/M6, plus the M1 test set-up that measures the resistance seen at V_X.

Topology from `python scan_figure.py <screenshot>` (SOP §3C):
  * load pair prints mirror x / none -- gates face inward, tied together, and
    M6 is diode-connected (the riser left of its gate reaches its own drain);
  * the input pair prints none / x -- gates face outward;
  * node X (M5.D = M3.D) runs right and up into M1's gate, crossing the
    M6/M4 drain column with no dot -- a crossing, exactly as the book draws it;
  * M4's gate is terminated by R_M to ground, and V_X drives the M1 branch
    through a second R_M, with i_X flowing up into the drain node.
"""
import os
from icproj import Schematic, name, dy_below, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-razavi-fig-12-57c",
    "Razavi Fig. 12.57(c) — differential pair with PMOS mirror load and V_X test",
    "Fig_12_57c",
    out_proj=os.path.join(OUT, "Razavi_Fig_12_57c_diffpair-mirror-load-Rx-test.icproj.json"),
    out_svg=os.path.join(HERE, "preview_fig1257c.svg"))

# ---------------------------------------------------------------- placement
# Columns: 180 V_in | 240 M5/M3 (node X) | 300 gate tie | 340 M6/M4 (node E)
#          400 R_M | 430 X riser | 500 R_M | 520 M1/V_X | 560 r_O1 | 590 gnd
# Rows (SOP §3A stack, compressed to the book's 60-unit PMOS->NMOS drain span):
#          100 rail | 120 S | 140 PMOS centres | 160 D | 180 node E / gate tie
#          200 node X | 220 NMOS D | 240 NMOS centres | 260 S + tail bus
#          300 I_SS | 340 ground
f.mos("M5", "pmos", 250, 140, "x", "M_5")       # load pair, gates inward
f.mos("M6", "pmos", 330, 140, "none", "M_6")
f.mos("M3", "nmos", 230, 240, "none", "M_3")    # input pair, gates outward
f.mos("M4", "nmos", 350, 240, "x", "M_4")
f.mos("M1", "pmos", 510, 140, "none", "M_1")
f.isrc("ISS", 290, 300, "I_SS")
f.passive("RM1", "resistor", 400, 260, "R_M")
f.passive("RM2", "resistor", 500, 320, "R_M")
f.passive("RO1", "resistor", 560, 180, "r_O1", rotation=90)
f.place("VX", "voltage-source", 520, 240, extra={
    "schematicReference": "VX", "schematicName": name("V_X"),
    "netlist": {"binding": {"kind": "primitive",
                            "deviceClass": "voltage-source"},
                "parameters": {}, "reference": "VX"}})
f.gnd("GND1", 290, 340)                          # tail source
f.gnd("GND2", 400, 290)                          # left R_M  (pin on pin)
f.gnd("GND3", 500, 350)                          # right R_M (pin on pin)
f.place("GNDR", "ground", 590, 180, rotation=270,  # r_O1, laid on its side
        extra={"schematicReference": "GNDR"})
f.port("VIN", 180, 240)

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("jvdd-start", "net-power-vdd", 220, 100),
        ("JV5", "net-power-vdd", 240, 100),
        ("JV6", "net-power-vdd", 340, 100),
        ("JV1", "net-power-vdd", 520, 100),
        ("jvdd-end", "net-power-vdd", 540, 100),
        ("JE", "net-e", 340, 180),      # M6 drain = its own gate = M4 drain
        ("JG", "net-e", 300, 140),      # the shared gate line
        ("JX", "net-x", 240, 200),      # node X
        ("JT", "net-tail", 290, 260),   # tail node
        ("JD", "net-out1", 520, 180)):  # M1 drain = r_O1 = V_X
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
f.net("net-power-vdd", [("M5", "S"), ("M6", "S"), ("M1", "S"),
                        ("M5", "B"), ("M6", "B"), ("M1", "B")])
f.net("net-x", [("M5", "D"), ("M3", "D"), ("M1", "G")])
f.net("net-e", [("M6", "D"), ("M6", "G"), ("M5", "G"), ("M4", "D")])
f.net("net-tail", [("M3", "S"), ("M4", "S"), ("ISS", "+")])
f.net("net-in", [("VIN", "P"), ("M3", "G")])
f.net("net-g4", [("M4", "G"), ("RM1", "1")])
f.net("net-gnd-1", [("GND1", "0"), ("ISS", "-"), ("M3", "B"), ("M4", "B")])
f.net("net-gnd-2", [("RM1", "2"), ("GND2", "0")])
f.net("net-out1", [("M1", "D"), ("RO1", "2"), ("VX", "+")])
f.net("net-gnd-3", [("RO1", "1"), ("GNDR", "0")])
f.net("net-vs", [("VX", "-"), ("RM2", "1")])
f.net("net-gnd-4", [("RM2", "2"), ("GND3", "0")])

# ---------------------------------------------------------------- routes
T, J = f.term, f.jn
f.rail("net-power-vdd", 100, [220, 240, 340, 520, 540])
f.route("r-vdd-drop-5", "net-power-vdd", J("JV5"), [("to", T("M5", "S"))])
f.route("r-vdd-drop-6", "net-power-vdd", J("JV6"), [("to", T("M6", "S"))])
f.route("r-vdd-drop-1", "net-power-vdd", J("JV1"), [("to", T("M1", "S"))])

f.route("r-x-m5d", "net-x", T("M5", "D"), [("to", J("JX"))])
f.route("r-x-m3d", "net-x", J("JX"), [("to", T("M3", "D"))])
# Node X drives M1's gate: right under the load pair, up, then across.  It
# crosses the M6/M4 drain column at (340,200) with no junction -- a crossing.
f.route("r-x-gate", "net-x", J("JX"), [("bend", 430, 200), ("bend", 430, 140),
                                       ("to", T("M1", "G"))])

f.route("r-e-m6d", "net-e", T("M6", "D"), [("to", J("JE"))])
f.route("r-e-m4d", "net-e", J("JE"), [("to", T("M4", "D"))])
f.route("r-e-tie", "net-e", J("JE"), [("bend", 300, 180), ("to", J("JG"))])
f.route("r-e-g5", "net-e", J("JG"), [("to", T("M5", "G"))])
f.route("r-e-g6", "net-e", J("JG"), [("to", T("M6", "G"))])

f.route("r-t-m3s", "net-tail", T("M3", "S"), [("to", J("JT"))])
f.route("r-t-m4s", "net-tail", T("M4", "S"), [("to", J("JT"))])
f.route("r-t-iss", "net-tail", J("JT"), [("to", T("ISS", "+"))])
f.route("r-in", "net-in", T("VIN", "P"), [("to", T("M3", "G"))])
f.route("r-g4", "net-g4", T("M4", "G"), [("to", T("RM1", "1"))])
f.route("r-gnd1", "net-gnd-1", T("ISS", "-"), [("to", T("GND1", "0"))])

f.route("r-o-jd", "net-out1", T("M1", "D"), [("to", J("JD"))])
f.route("r-o-ro1", "net-out1", J("JD"), [("to", T("RO1", "2"))])
f.route("r-o-vx", "net-out1", J("JD"), [("to", T("VX", "+"))])
f.route("r-vs", "net-vs", T("VX", "-"), [("bend", 520, 280), ("bend", 500, 280),
                                         ("to", T("RM2", "1"))])
# R_M x2 and r_O1 each sit pin-on-pin with their ground symbol -- no wire.

f.terminal("terminal-vin", "V_in", "net-in", "input", ["VIN"])

# ---------------------------------------------------------------- annotations
f.inst_label("M5", -18, 5, "end")           # mirrored: ink on the left
f.inst_label("M6", 18, 5, "start")
f.inst_label("M3", 18, 5, "start")
f.inst_label("M4", -18, 5, "end")
f.inst_label("M1", 18, 5, "start")
f.inst_label("ISS", 18, 5, "start")
for iid in ("RM1", "RM2"):
    f.inst_label(iid, 13, 5, "start")       # vertical resistor: ink +/-5.37
f.inst_label("RO1", 0, dy_below(5.37, 6.0), "middle")
f.inst_label("VX", 18, 5, "start")          # circle radius 10.76
f.port_label("VIN", "terminal-vin", -LABEL_PORT, 5, "end")
f.power_label("label-vdd", "net-power-vdd", "jvdd-end", 12, 6, "V_DD")

# i_X flows UP into the drain node, so the arrow points up (SOP §6B).
f.arrow("arrow-ix", 520, 210, 520, 190)
f.text("note-ix", 508, 205, "end", "i_X", owner="VX")
f.text("note-x", 227, 205, "end", "X")      # node label, left of its dot

f.build(long_haul={
            "r-vdd-rail-1", "r-vdd-rail-2",   # the V_DD rail itself
            "r-x-gate",       # node X across to M1's gate: the book's own
                              # long connection between the two sub-circuits
            "r-t-m3s", "r-t-m4s",   # 50: the shared-source bus
        },
        rail_ends={"jvdd-start", "jvdd-end"},
        viewbox=(125, 85, 495, 295))
