# -*- coding: utf-8 -*-
"""Razavi Fig. 14.36(b): biquad built from a summing difference amplifier
(OA1) driving two inverting integrators (OA2, OA3), with global feedback
R_3 from Y and R_5 from X.

Topology from `python scan_figure.py <screenshot>` (SOP §3C).  Note the
screenshot is low resolution (656 px wide), so the GAPs in the wire runs are
mostly COMPONENT BODIES, not disconnections -- each one lines up with a
resistor zigzag or a capacitor plate pair.  What the scan settled:
  * the x=126 column splits at the opamp inputs: R_3 and R_6 land on OA1's
    IN- (upper), R_4 and R_5 on its IN+ (lower)
  * the three opamp triangles sit at y 133.5 / 146.5 / 159 px -- Razavi steps
    each stage down by one pin pitch so that every stage's OUT lines up with
    the next stage's IN-, which is why the inter-stage wires are straight
"""
import os
from icproj import Schematic, dy_above, dy_below, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-razavi-fig-14-36b",
    "Razavi Fig. 14.36(b) — biquad from a difference amp and two integrators",
    "Fig_14_36b",
    out_proj=os.path.join(OUT, "Razavi_Fig_14_36b_biquad.icproj.json"),
    out_svg=os.path.join(HERE, "preview_fig1436b.svg"))

# ---------------------------------------------------------------- placement
# DENSITY (user rule, 2026-08-29): match the textbook's component/figure
# ratio.  Measured off the page: opamp triangle 69 px in a 200 px figure =
# 34.5%, aspect 2.90.  The first attempt at this figure came out 21.6% -- far
# too loose -- so every gap here is the grid-10 floor (10 units between a
# terminal and its junction) rather than the 20-30 §3A defaults.
# Stage pitch 170 is the floor: OUT -10- J -10- R(40) -10- J -10- IN = 80.
#   rows  100 R_3 bus | 140 V_out + R_6 | 160 C_1 | 170 C_2
#         190/200/210 the three opamp centres, each stage one pin pitch lower
#         so OUT(n) lines up with IN-(n+1) | 230/240 grounds | 260 R_5 bus
f.place("OA1", "opamp", 250, 190)
f.place("OA2", "opamp", 420, 200)
f.place("OA3", "opamp", 590, 210)

f.passive("R4", "resistor", 130, 200, "R_4", rotation=90)
f.passive("R6", "resistor", 250, 140, "R_6", rotation=90)
f.passive("R1", "resistor", 330, 190, "R_1", rotation=90)
f.passive("R2", "resistor", 500, 200, "R_2", rotation=90)
f.passive("R3", "resistor", 470, 100, "R_3", rotation=90)
f.passive("R5", "resistor", 300, 260, "R_5", rotation=90)
f.passive("C1", "capacitor", 410, 160, "C_1", rotation=90)
f.passive("C2", "capacitor", 590, 170, "C_2", rotation=90)

f.gnd("GND2", 360, 230)
f.gnd("GND3", 530, 240)
f.port("VIN", 80, 200)                  # circle left of its pin
f.port("VOUT", 320, 140, mirror="x")    # circle right of its pin

# ---------------------------------------------------------------- junctions
# Every labelled node carries a junction so the editor draws a black dot
# (user rule, 2026-08-29).  JY needs three DIFFERENT directions to qualify,
# which is why R_3's riser leaves to the right at x=680 instead of stacking on
# top of C_2's drop -- two wires up the same column render as a plain corner.
for jid, net, x, y in (
        ("JA", "net-a", 190, 200),     # OA1 IN+  : R_4, R_5
        ("JB", "net-b", 190, 180),     # OA1 IN-  : R_6, R_3
        ("JB2", "net-b", 190, 140),    # R_6 tees into the R_3 riser
        ("JOUT", "net-out", 300, 190),
        ("JVO", "net-out", 300, 140),  # V_out tap / R_6 return
        ("JC", "net-c", 360, 190),     # OA2 IN-  : R_1, C_1
        ("JX", "net-x", 470, 200),     # OA2 OUT  : C_1, R_2, R_5
        ("JD", "net-d", 530, 200),     # OA3 IN-  : R_2, C_2
        ("JY", "net-y", 650, 210)):    # OA3 OUT  : C_2, R_3
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
f.net("net-in", [("VIN", "P"), ("R4", "2")])
f.net("net-a", [("R4", "1"), ("R5", "2"), ("OA1", "IN+")])
f.net("net-b", [("R6", "2"), ("R3", "2"), ("OA1", "IN-")])
f.net("net-out", [("OA1", "OUT"), ("R6", "1"), ("VOUT", "P"), ("R1", "2")])
f.net("net-c", [("R1", "1"), ("C1", "2"), ("OA2", "IN-")])
f.net("net-x", [("OA2", "OUT"), ("C1", "1"), ("R2", "2"), ("R5", "1")])
f.net("net-d", [("R2", "1"), ("C2", "2"), ("OA3", "IN-")])
f.net("net-y", [("OA3", "OUT"), ("C2", "1"), ("R3", "1")])
# One ground symbol per net: putting both on a single net leaves that net
# geometrically in two pieces and the editor flags it red (user report).
f.net("net-gnd-1", [("OA2", "IN+"), ("GND2", "0")])
f.net("net-gnd-2", [("OA3", "IN+"), ("GND3", "0")])

# ---------------------------------------------------------------- routes
T, J = f.term, f.jn
f.route("r-in", "net-in", T("VIN", "P"), [("to", T("R4", "2"))])
f.route("r-a-r4", "net-a", T("R4", "1"), [("to", J("JA"))])
f.route("r-a-oa1", "net-a", J("JA"), [("to", T("OA1", "IN+"))])
f.route("r-b-oa1", "net-b", J("JB"), [("to", T("OA1", "IN-"))])

f.route("r-out-oa1", "net-out", T("OA1", "OUT"), [("to", J("JOUT"))])
f.route("r-out-tap", "net-out", J("JOUT"), [("to", J("JVO"))])
f.route("r-out-vout", "net-out", J("JVO"), [("to", T("VOUT", "P"))])
f.route("r-out-r6", "net-out", J("JVO"), [("to", T("R6", "1"))])
f.route("r-b-r6", "net-b", T("R6", "2"), [("to", J("JB2"))])
f.route("r-b-riser", "net-b", J("JB2"), [("to", J("JB"))])

f.route("r-out-r1", "net-out", J("JOUT"), [("to", T("R1", "2"))])
f.route("r-c-r1", "net-c", T("R1", "1"), [("to", J("JC"))])
f.route("r-c-oa2", "net-c", J("JC"), [("to", T("OA2", "IN-"))])
f.route("r-c-c1", "net-c", J("JC"), [("bend", 360, 160), ("to", T("C1", "2"))])
f.route("r-x-c1", "net-x", T("C1", "1"), [("bend", 470, 160), ("to", J("JX"))])
f.route("r-x-oa2", "net-x", T("OA2", "OUT"), [("to", J("JX"))])

f.route("r-x-r2", "net-x", J("JX"), [("to", T("R2", "2"))])
f.route("r-d-r2", "net-d", T("R2", "1"), [("to", J("JD"))])
f.route("r-d-oa3", "net-d", J("JD"), [("to", T("OA3", "IN-"))])
f.route("r-d-c2", "net-d", J("JD"), [("bend", 530, 170), ("to", T("C2", "2"))])
f.route("r-y-c2", "net-y", T("C2", "1"), [("bend", 650, 170), ("to", J("JY"))])
f.route("r-y-oa3", "net-y", T("OA3", "OUT"), [("to", J("JY"))])

# global feedback: R_3 from Y over the top, R_5 from X under the bottom
f.route("r-y-r3", "net-y", J("JY"), [("bend", 690, 210), ("bend", 690, 100),
                                     ("to", T("R3", "1"))])
f.route("r-b-r3", "net-b", T("R3", "2"), [("bend", 190, 100), ("to", J("JB2"))])
f.route("r-x-r5", "net-x", J("JX"), [("bend", 470, 260), ("to", T("R5", "1"))])
f.route("r-a-r5", "net-a", T("R5", "2"), [("bend", 190, 260), ("to", J("JA"))])

# A route must leave a pin along its own escape direction; IN+ is
# "west", so it goes left first and only then down (this is exactly
# what the editor was painting red).
f.route("r-g2", "net-gnd-1", T("OA2", "IN+"),
        [("bend", 360, 210), ("to", T("GND2", "0"))])
f.route("r-g3", "net-gnd-2", T("OA3", "IN+"),
        [("bend", 530, 220), ("to", T("GND3", "0"))])

# ------------------------------------------------- cell terminals for ports
f.terminal("terminal-vin", "V_in", "net-in", "input", ["VIN"])
f.terminal("terminal-vout", "V_out", "net-out", "output", ["VOUT"])

# ---------------------------------------------------------------- annotations
# Resistor labels sit 6 units clear of the zigzag, not the 1.5 used for a
# capacitor (user: "R 都離電阻再遠一點"):
#   above  dy = -(5.37 + 6 + 5.5) = -17
#   below  dy = +(5.37 + 6 + 13.8) = +25
R_INK, C_INK, R_GAP = 5.37, 8.05, 6.0     # resistor / capacitor half-height
for iid in ("R4", "R6"):
    f.inst_label(iid, 0, dy_above(R_INK, R_GAP), "middle")
f.inst_label("R5", 0, dy_above(R_INK, R_GAP), "middle")
for iid in ("C1", "C2"):
    f.inst_label(iid, 0, dy_above(C_INK), "middle")
for iid in ("R1", "R2", "R3"):
    f.inst_label(iid, 0, dy_below(R_INK, R_GAP), "middle")
f.port_label("VIN", "terminal-vin", -LABEL_PORT, 5, "end")
f.port_label("VOUT", "terminal-vout", LABEL_PORT, 5, "start")

f.text("note-x", 480, 186, "start", "X")
f.text("note-y", 660, 196, "start", "Y")

f.build(long_haul={
            "r-out-tap",                        # 50: the V_out tap column
            "r-y-r3", "r-b-r3", "r-x-r5", "r-a-r5",   # global feedback buses
        },
        extra_evidence=[],          # no supply rail in this figure
        density_ref=("OA1", 34.5),  # measured off the textbook page
        viewbox=(30, 85, 690, 200))
