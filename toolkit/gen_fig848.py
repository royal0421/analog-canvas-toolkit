# -*- coding: utf-8 -*-
"""Razavi Fig. 8.48: non-inverting amplifier with a T-network feedback.

V_in drives the "+" input; the feedback tap is the R_1/R_3/R_4 tee, with R_2
from the inverting node to ground.

Topology from `python scan_figure.py <screenshot>` (SOP §3C): three dots --
V_out, node A (inverting input / R_2 / R_3) and node B (R_1 / R_3 / R_4);
"+" is on TOP, so `opamp-inputs-swapped`.
"""
import os
from icproj import Schematic, name, dy_below, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-razavi-fig-8-48",
    "Razavi Fig. 8.48 — non-inverting amplifier with T-network feedback",
    "Fig_8_48",
    out_proj=os.path.join(OUT, "Razavi_Fig_8_48_noninverting-T-feedback.icproj.json"),
    out_svg=os.path.join(HERE, "preview_fig848.svg"))

# ---------------------------------------------------------------- placement
#   columns 140 V_in | 190 node A | 250 op amp and R_3 | 310 V_out and node B
#           350 V_out port
#   rows    140 IN+ | 150 op amp centre and V_out | 160 IN- | 180 R_1
#           210 node A/B | 240 R_2 and R_4 | 270 grounds
# Each ground pin lands on its resistor's lower pin, so those need no wire.
f.place("OA", "opamp-inputs-swapped", 250, 150, extra={
    "schematicReference": "OA", "schematicName": name("A_0")})
f.place("VIN", "voltage-source", 140, 180,
        extra={"schematicReference": "VIN"})
f.passive("R1", "resistor", 310, 180, "R_1")
f.passive("R2", "resistor", 190, 240, "R_2")
f.passive("R3", "resistor", 250, 210, "R_3", rotation=90)
f.passive("R4", "resistor", 310, 240, "R_4")
f.gnd("GND1", 190, 270)
f.gnd("GND2", 310, 270)
f.gnd("GND3", 140, 210)
f.port("VOUT", 350, 150, mirror="x")

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("JOUT", "net-out", 310, 150),
        ("JA", "net-a", 190, 210),
        ("JB", "net-b", 310, 210)):
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
f.net("net-in", [("VIN", "+"), ("OA", "IN+")])
f.net("net-out", [("OA", "OUT"), ("R1", "1"), ("VOUT", "P")])
f.net("net-a", [("OA", "IN-"), ("R2", "1"), ("R3", "2")])
f.net("net-b", [("R1", "2"), ("R3", "1"), ("R4", "1")])
f.net("net-gnd-1", [("R2", "2"), ("GND1", "0")])
f.net("net-gnd-2", [("R4", "2"), ("GND2", "0")])
f.net("net-gnd-3", [("VIN", "-"), ("GND3", "0")])

# ---------------------------------------------------------------- routes
T, J = f.term, f.jn
f.route("r-in", "net-in", T("VIN", "+"), [("bend", 140, 140),
                                          ("to", T("OA", "IN+"))])
f.route("r-out-oa", "net-out", T("OA", "OUT"), [("to", J("JOUT"))])
f.route("r-out-p", "net-out", J("JOUT"), [("to", T("VOUT", "P"))])
f.route("r-out-r1", "net-out", J("JOUT"), [("to", T("R1", "1"))])
f.route("r-a-in", "net-a", T("OA", "IN-"), [("bend", 190, 160), ("to", J("JA"))])
f.route("r-a-r2", "net-a", J("JA"), [("to", T("R2", "1"))])
f.route("r-a-r3", "net-a", J("JA"), [("to", T("R3", "2"))])
f.route("r-b-r1", "net-b", T("R1", "2"), [("to", J("JB"))])
f.route("r-b-r3", "net-b", T("R3", "1"), [("to", J("JB"))])
f.route("r-b-r4", "net-b", J("JB"), [("to", T("R4", "1"))])
# R_2, R_4 and the source each sit pin-on-pin with their ground symbol.

f.terminal("terminal-vout", "V_out", "net-out", "output", ["VOUT"])

# ---------------------------------------------------------------- annotations
for iid in ("R1", "R2", "R4"):
    f.inst_label(iid, 13, 5, "start")       # vertical resistor: ink +/-5.37
f.inst_label("R3", 0, dy_below(5.37, 6.0), "middle")
f.inst_label("OA", -10, 6, "middle")        # A_0 inside the triangle
f.port_label("VOUT", "terminal-vout", LABEL_PORT, 5, "start")
f.text("note-vin", 112, 185, "end", "V_in", owner="VIN")

f.build(long_haul={"r-in",        # 80: the source runs across to the + input
                   "r-a-in"},     # 50: the inverting input down to node A
        extra_evidence=[],
        density_ref=("OA", 34.9),
        viewbox=(70, 118, 350, 175))
