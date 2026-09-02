# -*- coding: utf-8 -*-
"""Transformer-fed full-wave bridge rectifier into R, output node grounded.
From a hand drawing (lane 3b).

⚠️ The page draws the bridge as a 45-degree DIAMOND.  That cannot be redrawn
here: routes are orthogonal only and a symbol may only sit at 0/90/180/270, so
a diode on a diagonal has no legal form.  The diamond is therefore flattened
into the equivalent RECTANGLE -- same ring, same four diodes, same nodes:

    LEFT --D1-- (AC top) --D3-- RIGHT        (top branch)
    LEFT --D2-- (AC bot) --D4-- RIGHT        (bottom branch)
    R sits between LEFT (+) and RIGHT (-), and RIGHT is grounded.

Diode directions read off 2.2x crops, one by one: every cathode faces LEFT,
i.e. both AC nodes feed the LEFT node and the RIGHT node returns to both AC
nodes -- the standard bridge, just rotated 90 degrees from the usual drawing.

Ignored, as instructed: the orange/green current arrows, the "高" notes, the
red highlight box and its "0" (the ground symbol already says 0 V).
"""
import os
from icproj import Schematic, name, plain, dy_below

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-handdrawn-bridge-rect",
    "Transformer-fed bridge rectifier",
    "BridgeRect",
    out_proj=os.path.join(OUT, "Handdrawn_bridge-rectifier.icproj.json"),
    out_svg=os.path.join(HERE, "preview_bridge.svg"))


def diode(iid, x, y, ref):
    """rotation 180 puts the CATHODE on the left, which is how all four sit."""
    f.place(iid, "diode", x, y, rotation=180, extra={
        "schematicReference": iid, "schematicName": name(ref),
        "netlist": {"binding": {"kind": "primitive", "deviceClass": "diode"},
                    "parameters": {}, "reference": iid}})


def coil(iid, x, y, ref):
    f.place(iid, "inductor", x, y, extra={
        "schematicReference": iid, "schematicName": name(ref),
        "netlist": {"binding": {"kind": "primitive", "deviceClass": "inductor"},
                    "parameters": {}, "reference": iid}})


# ---------------------------------------------------------------- placement
#   cols 60 input terminals | 130 primary | 200 secondary | 280 LEFT rail (+)
#        340 D1/D2 | 400 the AC taps and R | 460 D3/D4 | 520 RIGHT rail (-)
#        580 ground
#   rows 60 the AC wire over the top | 100 top branch | 200 R and the rails'
#        midpoint | 300 bottom branch | 340 the AC wire under the bottom
f.port("IN1", 60, 60)
coil("L1", 130, 200, "L_1")
coil("L2", 200, 200, "L_2")
diode("D1", 340, 100, "D_1")
diode("D2", 340, 300, "D_2")
diode("D3", 460, 100, "D_3")
diode("D4", 460, 300, "D_4")
f.passive("R", "resistor", 400, 200, "R", rotation=90)
f.gnd("GND", 580, 240)

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("JIN2", "net-in2", 60, 340),    # the bare second input terminal
        ("JLT", "net-p", 280, 100),      # LEFT rail corners and its R tap
        ("JLM", "net-p", 280, 200),
        ("JLB", "net-p", 280, 300),
        ("JRT", "net-n", 520, 100),      # RIGHT rail, likewise
        ("JRM", "net-n", 520, 200),
        ("JRB", "net-n", 520, 300),
        ("JAT", "net-act", 400, 100),    # the two AC taps
        ("JAB", "net-acb", 400, 300)):
    f.junction(jid, net, x, y)

# -------------------------------------------------------------------- nets
f.net("net-in1", [("IN1", "P"), ("L1", "1")])
f.net("net-in2", [("L1", "2")])
f.net("net-act", [("L2", "1"), ("D1", "A"), ("D3", "K")])
f.net("net-acb", [("L2", "2"), ("D2", "A"), ("D4", "K")])
f.net("net-p", [("D1", "K"), ("D2", "K"), ("R", "2")])
f.net("net-n", [("D3", "A"), ("D4", "A"), ("R", "1"), ("GND", "0")])

# ------------------------------------------------------------------ routes
T, Jn = f.term, f.jn
f.route("r-in1", "net-in1", T("IN1", "P"),
        [("bend", 130, 60), ("to", T("L1", "1"))])
f.route("r-in2", "net-in2", T("L1", "2"),
        [("bend", 130, 340), ("to", Jn("JIN2"))])

f.route("r-ac-t", "net-act", T("L2", "1"),
        [("bend", 200, 60), ("bend", 400, 60), ("to", Jn("JAT"))])
f.route("r-ac-b", "net-acb", T("L2", "2"),
        [("bend", 200, 340), ("bend", 400, 340), ("to", Jn("JAB"))])
f.route("r-at-d1", "net-act", Jn("JAT"), [("to", T("D1", "A"))])
f.route("r-at-d3", "net-act", Jn("JAT"), [("to", T("D3", "K"))])
f.route("r-ab-d2", "net-acb", Jn("JAB"), [("to", T("D2", "A"))])
f.route("r-ab-d4", "net-acb", Jn("JAB"), [("to", T("D4", "K"))])

f.route("r-p-d1", "net-p", T("D1", "K"), [("to", Jn("JLT"))])
f.route("r-p-d2", "net-p", T("D2", "K"), [("to", Jn("JLB"))])
f.route("r-p-1", "net-p", Jn("JLT"), [("to", Jn("JLM"))])
f.route("r-p-2", "net-p", Jn("JLM"), [("to", Jn("JLB"))])
f.route("r-p-r", "net-p", Jn("JLM"), [("to", T("R", "2"))])

f.route("r-n-d3", "net-n", T("D3", "A"), [("to", Jn("JRT"))])
f.route("r-n-d4", "net-n", T("D4", "A"), [("to", Jn("JRB"))])
f.route("r-n-1", "net-n", Jn("JRT"), [("to", Jn("JRM"))])
f.route("r-n-2", "net-n", Jn("JRM"), [("to", Jn("JRB"))])
f.route("r-n-r", "net-n", Jn("JRM"), [("to", T("R", "1"))])
f.route("r-n-g", "net-n", Jn("JRM"),
        [("bend", 580, 200), ("to", T("GND", "0"))])

f.terminal("t-in", "V_in", "net-in1", "input", ["IN1"])

# ------------------------------------------------------------- annotations
f.port_label("IN1", "t-in", -14, 5, "end")
f.inst_label("R", 0, dy_below(5.37, 6), "middle")
# the secondary voltage, as the page marks it
f.text("n-6v", 230, 150, "start", plain("6 V"))
f.text("n-vi", 230, 185, "start", name("V_i"))
f.text("n-vip", 238, 118, "middle", plain("+"))
f.text("n-vim", 238, 292, "middle", plain("\u2212"))
# V_o across R, + on the LEFT node
f.text("n-vop", 366, 180, "middle", plain("+"), owner="R")
f.text("n-vo", 400, 180, "middle", name("V_o"), owner="R")
f.text("n-vom", 434, 180, "middle", plain("\u2212"), owner="R")

f.build(long_haul={"r-in1",        # 70+110: in at the top, down to the primary
                   "r-in2",        # 110+70: and out at the bottom
                   "r-ac-t",       # the secondary wraps over the top branch
                   "r-ac-b",       # and under the bottom one
                   "r-p-1", "r-p-2", "r-n-1", "r-n-2",   # the two DC rails
                   "r-p-r", "r-n-r",                     # rails across to R
                   "r-n-g"},       # out to the ground
        extra_evidence=[],
        rail_ends={"JIN2"},
        viewbox=(20, 30, 600, 340),
        # plain on purpose: a value and two polarity marks
        expect_differ=set())
