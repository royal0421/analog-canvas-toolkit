# -*- coding: utf-8 -*-
"""Sallen-Key low-pass filter -- the HAND-PLACED reference for lane 2.

This is the standard answer the netlist placer is scored against.  There is
no printed original for this circuit in the project, so the layout is the
textbook one: the signal runs left to right along one row (V_in, R_1, n1,
R_2, p, the buffer), the shunt capacitor drops from p to ground, and the two
things that reach back over the amplifier -- C_1 from n1 to the output and
the unity-gain feedback from the output to IN- -- ride two tracks above it.

Lane 2 only.  It writes into AI\\toolkit\\refs\\ and does not touch the 29
hand-drawn figures at the repository root.
"""
import os
from icproj import Schematic, dy_above, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "refs")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

f = Schematic(
    "project-sallen-key-lp-ref",
    "Sallen-Key low-pass filter (hand-placed reference)",
    "SallenKey",
    out_proj=os.path.join(OUT, "sallen-key-lp.icproj.json"),
    out_svg=os.path.join(OUT, "preview_sallen-key-lp.svg"))

# ---------------------------------------------------------------- placement
# main row y=200: everything the signal walks through, left to right.
f.port("VIN", 100, 200)                     # pin at 110, circle to its left
f.passive("R1", "resistor", 160, 200, "R_1", rotation=90)   # pins 140 / 180
f.passive("R2", "resistor", 280, 200, "R_2", rotation=90)   # pins 260 / 300
f.passive("C2", "capacitor", 340, 250, "C_2")               # pins 230 / 270
f.gnd("G1", 340, 280)                       # its pin lands on C_2's lower pin
f.place("OA", "opamp", 430, 190, extra={"schematicReference": "OA"})
f.port("VOUT", 560, 190, mirror="x")        # pin at 550, circle to its right
# the two things that reach back over the amplifier, one track each
f.passive("C1", "capacitor", 280, 130, "C_1", rotation=90)  # pins 260 / 300

f.junction("J1", "net-n1", 220, 200)        # R_1, R_2, C_1's riser
f.junction("J2", "net-p", 340, 200)         # R_2, C_2, IN+
f.junction("J3", "net-out", 510, 190)       # OUT, V_out, the track above
f.junction("J4", "net-out", 510, 150)       # C_1 and the unity-gain feedback

# ---------------------------------------------------------------- nets
f.net("net-in", [("VIN", "P"), ("R1", "2")])
f.net("net-n1", [("R1", "1"), ("R2", "2"), ("C1", "2")])
f.net("net-p", [("R2", "1"), ("C2", "1"), ("OA", "IN+")])
f.net("net-out", [("C1", "1"), ("OA", "OUT"), ("OA", "IN-"), ("VOUT", "P")])
f.net("net-0", [("C2", "2"), ("G1", "0")])

# ---------------------------------------------------------------- routes
T, J = f.term, f.jn
f.route("r-in", "net-in", T("VIN", "P"), [("to", T("R1", "2"))])

f.route("r-n1-r1", "net-n1", T("R1", "1"), [("to", J("J1"))])
f.route("r-n1-r2", "net-n1", J("J1"), [("to", T("R2", "2"))])
f.route("r-n1-c1", "net-n1", J("J1"),
        [("bend", 220, 130), ("to", T("C1", "2"))])

f.route("r-p-r2", "net-p", T("R2", "1"), [("to", J("J2"))])
f.route("r-p-c2", "net-p", J("J2"), [("to", T("C2", "1"))])
f.route("r-p-oa", "net-p", J("J2"), [("to", T("OA", "IN+"))])

f.route("r-out-oa", "net-out", T("OA", "OUT"), [("to", J("J3"))])
f.route("r-out-port", "net-out", J("J3"), [("to", T("VOUT", "P"))])
f.route("r-out-c1", "net-out", T("C1", "1"),
        [("bend", 510, 130), ("to", J("J4"))])
f.route("r-out-down", "net-out", J("J4"), [("to", J("J3"))])
f.route("r-out-fb", "net-out", J("J4"),
        [("bend", 360, 150), ("bend", 360, 180), ("to", T("OA", "IN-"))])
# C_2's lower pin and G1's pin share a coordinate -> no route needed.

f.terminal("terminal-vin", "V_in", "net-in", "input", ["VIN"])
f.terminal("terminal-vout", "V_out", "net-out", "output", ["VOUT"])

# ---------------------------------------------------------------- labels
f.inst_label("R1", 0, dy_above(5.37), "middle")
f.inst_label("R2", 0, dy_above(5.37), "middle")
f.inst_label("C1", 0, dy_above(8.05), "middle")
f.inst_label("C2", 16, 5, "start")
f.port_label("VIN", "terminal-vin", -LABEL_PORT, 5, "end")
f.port_label("VOUT", "terminal-vout", LABEL_PORT, 5, "start")
f.text("note-n1", 212, 188, "end", "n1")

# r-out-c1 and r-out-fb are the two deliberate long hauls over the amplifier.
f.build(long_haul={"r-out-c1", "r-out-fb", "r-n1-c1"}, extra_evidence=[],
        viewbox=(40, 95, 600, 230))
