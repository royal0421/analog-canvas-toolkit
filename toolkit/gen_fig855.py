# -*- coding: utf-8 -*-
"""Razavi Fig. 8.55: summing amplifier.

V_1 through R_2 and V_2 through R_1 meet at the node that R_P pulls to ground;
that node is the op amp's virtual ground X, and R_F closes the loop to V_out.

Topology from `python scan_figure.py <screenshot>` (SOP §3C): four dots -- two
on the left column (one tee for the wire to X, one where R_1 lands), one at X,
one at V_out.  "-" is on TOP, so this is the plain `opamp`, and the "+" input
grounds through the same column that carries X's riser, exactly as printed.
"""
import os
from icproj import Schematic, name, dy_above, dy_below, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-razavi-fig-8-55",
    "Razavi Fig. 8.55 — summing amplifier",
    "Fig_8_55",
    out_proj=os.path.join(OUT, "Razavi_Fig_8_55_summing-amplifier.icproj.json"),
    out_svg=os.path.join(HERE, "preview_fig855.svg"))

# ---------------------------------------------------------------- placement
#   columns 30 ports | 80 R_1/R_2 | 130 summing node | 190 X | 250 op amp
#           300 V_out node | 320 V_out port
#   rows    120 R_F | 140 V_1 | 160 X | 170 op amp centre | 180 V_2 and IN+
#           210 R_P | 240 ground
# V_1 and V_2 sit 40 apart, not the printed 20: our labels are fixed in
# drawing units while this figure is reproduced at a larger zoom than the one
# the type was calibrated against, so at 20 the two labels nearly touch.
f.place("OA", "opamp", 250, 170, extra={
    "schematicReference": "OA", "schematicName": name("A_0")})
f.passive("R2", "resistor", 80, 140, "R_2", rotation=90)
f.passive("R1", "resistor", 80, 180, "R_1", rotation=90)
f.passive("RP", "resistor", 130, 210, "R_P")
f.passive("RF", "resistor", 250, 120, "R_F", rotation=90)
f.gnd("GND1", 130, 240)                 # pin lands on R_P's lower pin: no wire
f.gnd("GND2", 190, 200)
f.port("V1", 30, 140)
f.port("V2", 30, 180)
f.port("VOUT", 320, 170, mirror="x")

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("JA1", "net-s", 130, 160),     # summing node: tee towards X
        ("JA2", "net-s", 130, 180),     # summing node: where R_1 lands
        ("JX", "net-s", 190, 160),      # X, and the R_F riser
        ("JOUT", "net-out", 300, 170)):
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
f.net("net-1", [("V1", "P"), ("R2", "2")])
f.net("net-2", [("V2", "P"), ("R1", "2")])
f.net("net-s", [("R2", "1"), ("R1", "1"), ("RP", "1"), ("RF", "2"),
                ("OA", "IN-")])
f.net("net-out", [("OA", "OUT"), ("RF", "1"), ("VOUT", "P")])
f.net("net-gnd-1", [("RP", "2"), ("GND1", "0")])
f.net("net-gnd-2", [("OA", "IN+"), ("GND2", "0")])

# ---------------------------------------------------------------- routes
T, J = f.term, f.jn
f.route("r-1", "net-1", T("V1", "P"), [("to", T("R2", "2"))])
f.route("r-2", "net-2", T("V2", "P"), [("to", T("R1", "2"))])
f.route("r-s-r2", "net-s", T("R2", "1"), [("bend", 130, 140), ("to", J("JA1"))])
f.route("r-s-r1", "net-s", T("R1", "1"), [("to", J("JA2"))])
f.route("r-s-col", "net-s", J("JA1"), [("to", J("JA2"))])
f.route("r-s-rp", "net-s", J("JA2"), [("to", T("RP", "1"))])
f.route("r-s-x", "net-s", J("JA1"), [("to", J("JX"))])
f.route("r-s-in", "net-s", J("JX"), [("to", T("OA", "IN-"))])
f.route("r-s-rf", "net-s", J("JX"), [("bend", 190, 120), ("to", T("RF", "2"))])
f.route("r-out-rf", "net-out", T("RF", "1"), [("bend", 300, 120),
                                              ("to", J("JOUT"))])
f.route("r-out-oa", "net-out", T("OA", "OUT"), [("to", J("JOUT"))])
f.route("r-out-p", "net-out", J("JOUT"), [("to", T("VOUT", "P"))])
f.route("r-g2", "net-gnd-2", T("OA", "IN+"), [("bend", 190, 180),
                                              ("to", T("GND2", "0"))])
# R_P's lower pin sits on GND1's pin -> that connection needs no wire.

f.terminal("terminal-v1", "V_1", "net-1", "input", ["V1"])
f.terminal("terminal-v2", "V_2", "net-2", "input", ["V2"])
f.terminal("terminal-vout", "V_out", "net-out", "output", ["VOUT"])

# ---------------------------------------------------------------- annotations
R_INK, R_GAP = 5.37, 6.0
f.inst_label("R2", 0, dy_above(R_INK, R_GAP), "middle")
f.inst_label("RF", 0, dy_above(R_INK, R_GAP), "middle")
f.inst_label("R1", 0, dy_below(R_INK, R_GAP), "middle")
f.inst_label("RP", 35, 5, "end")            # right side, but pushed out
                                            # past the IN+ ground symbol
f.inst_label("OA", -10, 6, "middle")        # A_0 sits inside the triangle
f.port_label("V1", "terminal-v1", -LABEL_PORT, 5, "end")
f.port_label("V2", "terminal-v2", -LABEL_PORT, 5, "end")
f.port_label("VOUT", "terminal-vout", LABEL_PORT, 5, "start")
f.text("note-x", 180, 150, "end", "X")

f.build(long_haul={"r-s-x",            # 60: summing node across to X
                   "r-out-rf"},        # 50: the feedback bus down to V_out
        extra_evidence=[],
        density_ref=("OA", 45.8),
        viewbox=(-15, 88, 400, 168))
