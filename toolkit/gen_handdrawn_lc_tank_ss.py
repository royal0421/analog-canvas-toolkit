# -*- coding: utf-8 -*-
"""Small-signal model: R_P || L_P || C_1 tank at node V_1, driven by I_in, with
g_m1 V_1 feeding the C_2 output node.  From a hand drawing (lane 3b).

Read off the page with 4x crops (SOP 3I-b -- the scanner is useless on ink):
  * R_P and L_P each run horizontally from their OWN ground to the tank node;
  * the bottom rail is CONTINUOUS -- C_1's bottom, I_in's top, V_1's minus
    probe, C_2's top and V_out are all the same node;
  * I_in's arrow points UP (rotation 180) and g_m1 V_1's points DOWN, and the
    latter hangs from a ground above it.

Drawn as the page has it; nothing "fixed" (user's standing rule for lane 3b).
Column pitch 70-80 throughout, which is the density he corrected me to.
"""
import os
from icproj import Schematic, name, plain, dy_above

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-handdrawn-lc-tank-ss",
    "LC tank small-signal model with g_m1 V_1 output stage",
    "TankSS",
    out_proj=os.path.join(OUT, "Handdrawn_LC-tank_small-signal.icproj.json"),
    out_svg=os.path.join(HERE, "preview_tankss.svg"))

# ---------------------------------------------------------------- placement
#   cols 80 the two left grounds | 140 R_P / L_P | 200 tank node and C_1
#        270 the V_1 probe, its legend and I_in | 320 C_2 | 370 g_m1 V_1
#        420 V_out          (pitch 60/60/70/50/50/50)
#   I_in and C_2 sit 20 under the rail -- the grid minimum -- so the band
#   below the rail is no deeper than the one above it (user, 2026-08-30)
#   rows 150 R_P | 180/190/250 grounds | 210 tank node and L_P
#        240 g_m source | 260 C_1 | 300 the bottom rail | 360 I_in and C_2
#        390 grounds
# The +/- of V_1 belong AT THE PORT column (270), not out past it and not
# tucked in the middle of the span (user corrected both, 2026-08-30):
# the probe is above them and the return rail is below them.
f.passive("RP", "resistor", 140, 150, "R_P", rotation=90)
f.place("LP", "inductor", 140, 210, rotation=90, extra={
    "schematicReference": "LP", "schematicName": name("L_P"),
    "netlist": {"binding": {"kind": "primitive", "deviceClass": "inductor"},
                "parameters": {}, "reference": "LP"}})
f.passive("C1", "capacitor", 200, 260, "C_1")
f.passive("C2", "capacitor", 320, 340, "C_2")
# rotation 180 turns the arrow UP: I_in pushes into the rail from ground
f.isrc("IIN", 270, 340, "I_in", rotation=180)
f.isrc("IGM", 370, 240, "I_gm")
# an open pin circle, not a filled dot (user, 2026-08-30); mirrored so the
# circle sits at the far end of the stub
f.port("PV1", 270, 210, mirror="x")
f.port("VOUT", 420, 300, mirror="x")
f.gnd("GR", 80, 180)
f.gnd("GL", 80, 250)
f.gnd("GI", 270, 370)
f.gnd("GC2", 320, 370)
# rotation 180 flips a ground on its back: pin underneath, body above
f.place("GS", "ground", 370, 190, rotation=180,
        extra={"schematicReference": "GS"})

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (("JA", "net-v1", 200, 210),
                       ("JB", "net-out", 270, 300),
                       ("JC2", "net-out", 320, 300),
                       ("JG", "net-out", 370, 300)):
    f.junction(jid, net, x, y)

# -------------------------------------------------------------------- nets
f.net("net-v1", [("RP", "1"), ("LP", "1"), ("C1", "1"), ("PV1", "P")])
f.net("net-out", [("C1", "2"), ("IIN", "-"), ("C2", "1"), ("IGM", "-"),
                  ("VOUT", "P")])
f.net("net-gnd", [("RP", "2"), ("GR", "0"), ("LP", "2"), ("GL", "0"),
                  ("IIN", "+"), ("GI", "0"), ("C2", "2"), ("GC2", "0"),
                  ("IGM", "+"), ("GS", "0")])

# ------------------------------------------------------------------ routes
T, Jn = f.term, f.jn
f.route("r-rp-g", "net-gnd", T("RP", "2"),
        [("bend", 80, 150), ("to", T("GR", "0"))])
f.route("r-lp-g", "net-gnd", T("LP", "2"),
        [("bend", 80, 210), ("to", T("GL", "0"))])
f.route("r-rp-a", "net-v1", T("RP", "1"),
        [("bend", 200, 150), ("to", Jn("JA"))])
f.route("r-lp-a", "net-v1", T("LP", "1"), [("to", Jn("JA"))])
f.route("r-a-c1", "net-v1", Jn("JA"), [("to", T("C1", "1"))])
f.route("r-a-pv1", "net-v1", Jn("JA"), [("to", T("PV1", "P"))])

f.route("r-o-c1", "net-out", T("C1", "2"),
        [("bend", 200, 300), ("to", Jn("JB"))])
f.route("r-o-iin", "net-out", Jn("JB"), [("to", T("IIN", "-"))])
f.route("r-o-1", "net-out", Jn("JB"), [("to", Jn("JC2"))])
f.route("r-o-c2", "net-out", Jn("JC2"), [("to", T("C2", "1"))])
f.route("r-o-2", "net-out", Jn("JC2"), [("to", Jn("JG"))])
f.route("r-o-igm", "net-out", Jn("JG"), [("to", T("IGM", "-"))])
f.route("r-o-out", "net-out", Jn("JG"), [("to", T("VOUT", "P"))])
f.route("r-gm-g", "net-gnd", T("IGM", "+"), [("to", T("GS", "0"))])
# I_in and C_2 sit pin-on-pin on their ground symbols, so neither needs a wire

f.terminal("t-v1", "V_1", "net-v1", "output", ["PV1"])
f.terminal("t-out", "V_out", "net-out", "output", ["VOUT"])

# ------------------------------------------------------------- annotations
f.port_label("VOUT", "t-out", 14, 5, "start")
f.inst_label("RP", 0, dy_above(5.37, 6), "middle")
f.inst_label("LP", 0, dy_above(15), "middle")
f.inst_label("C1", -16, 5, "end")
f.inst_label("C2", 16, 5, "start")
f.inst_label("IIN", -18, 5, "end")
# the page writes the transconductance current as a product, not a name
f.text("v-gm", 388, 245, "start",
       {"runs": name("g_m1")["runs"] + name("V_1")["runs"]}, owner="IGM")
# V_1 sits between its two probe points, as the page draws it
f.text("n-plus", 270, 240, "middle", plain("+"), owner="PV1")
f.text("n-v1", 270, 265, "middle", name("V_1"), owner="PV1")
f.text("n-minus", 270, 288, "middle", plain("\u2212"), owner="PV1")

f.build(long_haul={"r-rp-g",       # 80: R_P back to its own ground
                   "r-rp-a",       # 70+70: R_P over and down to the tank node
                   "r-lp-g",       # 50: L_P back to its own ground
                   "r-lp-a",       # 60: L_P across to the tank node
                   "r-a-pv1",      # 60: the tank node out to the + probe
                   "r-o-c1",       # 70: C_1 down and along the bottom rail
                   "r-o-1",        # 70: the rail on to C_2
                   "r-o-2",        # 70: and on to the g_m source
                   "r-o-out"},     # 60: and out to V_out
        extra_evidence=[],
        viewbox=(40, 110, 470, 320),
        # plain on purpose: the polarity marks are symbols, not device names
        expect_differ={"n-plus", "n-minus",
                       # a product of two names, not one name
                       "v-gm"})
