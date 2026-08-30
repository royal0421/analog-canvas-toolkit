# -*- coding: utf-8 -*-
"""Razavi Fig. 5.170: two-stage BJT amplifier.

Stage 1 is a common-emitter Q_1 with a 2k feedback resistor from its collector
back to its base and R_E1 || C_2 degeneration; stage 2 is the emitter follower
Q_2, AC-coupled through C_3 into the 50 ohm load.

Topology from `python scan_figure.py <screenshot>` (SOP §3C).  Scale came out
at 1.517 px/unit from Q_2 (its base row is the collector node row at y=114.5
and its emitter lands on node X at y=160.5, i.e. 30 units = 45.5 px).
"""
import os
from icproj import (Schematic, name, plain, name_suffix, dy_above, dy_below,
                    LABEL_PORT)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-razavi-fig-5-170",
    "Razavi Fig. 5.170 — two-stage BJT amplifier",
    "Fig_5_170",
    out_proj=os.path.join(OUT, "Razavi_Fig_5_170_two-stage-BJT-amp.icproj.json"),
    out_svg=os.path.join(HERE, "preview_fig5170.svg"),
    supply_net="net-vcc", rail_end="jvcc-end", supply_name="VCC")

# ---------------------------------------------------------------- placement
#   rows 100 V_CC rail | 140 600R | 170 collector node and Q_2 base
#        210 input row, Q_1 centre, node X | 250 Q_1 emitter node
#        280 R_E1 / C_2 / 200R / 50R | 310 grounds
#   cols 110 V_in | 130 C_1 | 180 2k in | 230 node A | 270 2k feedback
#        330 Q_1 | 380 C_2 | 470 Q_2 and node X | 550 C_3 | 610 V_out | 650 port
# No vdd-port: with a power rail the supply is the rail itself plus a
# power label on its end cap (SOP §2/§7).  Dropping a vdd-port on top of
# the rail leaves a stray stub sticking up.
f.bjt("Q1", "npn", 330, 210, "none", "Q_1")
f.bjt("Q2", "npn", 470, 170, "none", "Q_2")
f.passive("C1", "capacitor", 130, 210, "C_1", rotation=90)
f.passive("RIN", "resistor", 180, 210, "R_in", rotation=90)
f.passive("RFB", "resistor", 270, 170, "R_fb", rotation=90)
f.passive("R600", "resistor", 330, 140, "R_C")
f.passive("RE1", "resistor", 330, 280, "R_E1")
f.passive("C2", "capacitor", 390, 280, "C_2")
f.passive("R200", "resistor", 470, 250, "R_L1")
f.passive("C3", "capacitor", 550, 210, "C_3", rotation=90)
f.passive("R50", "resistor", 580, 250, "R_L2")
for iid, x, y in (("GND1", 330, 310), ("GND2", 390, 310),
                  ("GND3", 470, 280), ("GND4", 580, 280)):
    f.gnd(iid, x, y)
f.port("VIN", 110, 210)
f.port("VOUT", 620, 210, mirror="x")

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("jvcc-start", "net-vcc", 310, 100),
        ("JV1", "net-vcc", 330, 100),
        ("JV2", "net-vcc", 470, 100),
        ("jvcc-end", "net-vcc", 490, 100),
        ("JA", "net-a", 230, 210),      # Q_1 base: input chain and feedback
        ("JC", "net-c", 330, 170),      # this is node X: Q_1 collector,
                                        # R_C, the feedback resistor and
                                        # Q_2's base all meet here
        ("JE", "net-e", 330, 250),      # Q_1 emitter: R_E1 and C_2
        ("JX", "net-x", 470, 210),      # Q_2 emitter node (unlabelled in
                                        # the figure): R_L1 and C_3
        ("JOUT", "net-out", 580, 210)):
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
f.net("net-vcc", [("R600", "1"), ("Q2", "C")])
f.net("net-in", [("VIN", "P"), ("C1", "2")])
f.net("net-c1r", [("C1", "1"), ("RIN", "2")])
f.net("net-a", [("RIN", "1"), ("RFB", "2"), ("Q1", "B")])
f.net("net-c", [("R600", "2"), ("Q1", "C"), ("RFB", "1"), ("Q2", "B")])
f.net("net-e", [("Q1", "E"), ("RE1", "1"), ("C2", "1")])
f.net("net-x", [("Q2", "E"), ("R200", "1"), ("C3", "2")])
f.net("net-out", [("C3", "1"), ("R50", "1"), ("VOUT", "P")])
f.net("net-gnd-1", [("RE1", "2"), ("GND1", "0")])
f.net("net-gnd-2", [("C2", "2"), ("GND2", "0")])
f.net("net-gnd-3", [("R200", "2"), ("GND3", "0")])
f.net("net-gnd-4", [("R50", "2"), ("GND4", "0")])

# ---------------------------------------------------------------- routes
T, J = f.term, f.jn
f.rail("net-vcc", 100, [310, 330, 470, 490])
f.route("r-vcc-rc", "net-vcc", J("JV1"), [("to", T("R600", "1"))])
f.route("r-vcc-q2", "net-vcc", J("JV2"), [("to", T("Q2", "C"))])

f.route("r-in", "net-in", T("VIN", "P"), [("to", T("C1", "2"))])
f.route("r-c1r", "net-c1r", T("C1", "1"), [("to", T("RIN", "2"))])
f.route("r-a-rin", "net-a", T("RIN", "1"), [("to", J("JA"))])
f.route("r-a-b", "net-a", J("JA"), [("to", T("Q1", "B"))])
f.route("r-a-fb", "net-a", J("JA"), [("bend", 230, 170), ("to", T("RFB", "2"))])

f.route("r-c-rc", "net-c", T("R600", "2"), [("to", J("JC"))])
f.route("r-c-q1", "net-c", J("JC"), [("to", T("Q1", "C"))])
f.route("r-c-fb", "net-c", T("RFB", "1"), [("to", J("JC"))])
f.route("r-c-q2", "net-c", J("JC"), [("to", T("Q2", "B"))])

f.route("r-e-q1", "net-e", T("Q1", "E"), [("to", J("JE"))])
f.route("r-e-re", "net-e", J("JE"), [("to", T("RE1", "1"))])
f.route("r-e-c2", "net-e", J("JE"), [("bend", 390, 250), ("to", T("C2", "1"))])

f.route("r-x-q2", "net-x", T("Q2", "E"), [("to", J("JX"))])
f.route("r-x-r", "net-x", J("JX"), [("to", T("R200", "1"))])
f.route("r-x-c3", "net-x", J("JX"), [("to", T("C3", "2"))])
f.route("r-o-c3", "net-out", T("C3", "1"), [("to", J("JOUT"))])
f.route("r-o-r", "net-out", J("JOUT"), [("to", T("R50", "1"))])
f.route("r-o-p", "net-out", J("JOUT"), [("to", T("VOUT", "P"))])
# Every ground pin sits on its component's lower pin: no wires needed.

f.terminal("terminal-vin", "V_in", "net-in", "input", ["VIN"])
f.terminal("terminal-vout", "V_out", "net-out", "output", ["VOUT"])

# ---------------------------------------------------------------- annotations
R_INK, C_INK, GAP = 5.37, 8.05, 6.0
f.inst_label("Q1", 8, 5, "start")           # BJT ink sits on the centre line
f.inst_label("Q2", 8, 5, "start")
f.inst_label("RE1", 13, 5, "start")
f.inst_label("C2", 13, 5, "start")
f.port_label("VIN", "terminal-vin", -LABEL_PORT, 5, "end")
f.port_label("VOUT", "terminal-vout", LABEL_PORT, 5, "start")

# Razavi prints VALUES on the rest, so those are upright drafting text.
for tid, x, y, align, label, owner in (
        ("v-rin", 180, 210 + dy_above(R_INK, GAP, sub=False), "middle",
         plain("2 k\u03a9"), "RIN"),
        ("v-rfb", 270, 170 + dy_above(R_INK, GAP, sub=False), "middle",
         plain("2 k\u03a9"), "RFB"),
        ("v-rc", 343, 145, "start", plain("600 \u03a9"), "R600"),
        ("v-r200", 483, 255, "start", plain("200 \u03a9"), "R200"),
        ("v-r50", 593, 255, "start", plain("50 \u03a9"), "R50"),
        ("v-c1", 130, 210 + dy_below(C_INK, GAP), "middle", name("C_1"), "C1"),
        ("v-c3", 550, 210 + dy_above(C_INK, GAP), "middle", name("C_3"), "C3"),
        ("v-vcc", 495, 105, "start", name_suffix("V_CC", " = 2.5 V"), None),
        # X labels the INTERSTAGE node (net-c), so it sits beside Q_2's
        # base, not beside the emitter node it happens to be nearer.
        ("note-x", 415, 191, "end", name("X"), None)):
    f.text(tid, x, y, align, label, owner)

f.build(long_haul={"r-vdd-rail-1",   # the V_CC rail itself
                   "r-e-c2",         # 50: emitter node out to C_2
                   "r-a-b",          # 60: node A across to Q_1's base
                   "r-c-q2",         # 100: collector node to Q_2's base,
                                     # the same span the textbook draws
                   "r-x-c3"},        # 60: node X out to the coupling cap
        rail_ends={"jvcc-start", "jvcc-end"},
        density_ref=("Q1", 35.9),
        viewbox=(50, 78, 640, 258),
        # plain text on purpose (values / block titles): the
        # editor's generator italicises everything, we follow the
        # textbook page instead -- SOP 4
        expect_differ={"v-rin", "v-rfb", "v-rc", "v-r200", "v-r50", "v-vcc"})
