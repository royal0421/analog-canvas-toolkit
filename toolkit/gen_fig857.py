# -*- coding: utf-8 -*-
"""Razavi Fig. 8.57: op amp with a diode in the feedback path.

V_in drives the non-inverting input; the output Y feeds back to node X through
D_1, and R_1 pulls X to ground.  X is also the output terminal V_out.

Topology from `python scan_figure.py <screenshot>` (SOP §3C): one junction dot
only, at X/V_out, where four wires meet; Y is a plain corner (two wires), so it
gets no dot -- same as the printed figure.
"""
import os
from icproj import Schematic, dy_below, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-razavi-fig-8-57",
    "Razavi Fig. 8.57 — op amp with a diode in the feedback path",
    "Fig_8_57",
    out_proj=os.path.join(OUT, "Razavi_Fig_8_57_diode-feedback-opamp.icproj.json"),
    out_svg=os.path.join(HERE, "preview_fig857.svg"))

# ---------------------------------------------------------------- placement
# "+" on top -> opamp-inputs-swapped.  The diode ships horizontal (A at -20,
# K at +20), so no rotation.  GND1's pin lands exactly on R_1's lower pin, so
# that connection needs no wire at all.
f.place("OA", "opamp-inputs-swapped", 300, 150,
        extra={"schematicReference": "OA"})
f.place("D1", "diode", 310, 200, extra={
    "schematicReference": "D1", "schematicName": __import__("icproj").name("D_1"),
    "netlist": {"binding": {"kind": "primitive", "deviceClass": "diode"},
                "parameters": {}, "reference": "D1"}})
f.passive("R1", "resistor", 250, 230, "R_1")
f.gnd("GND1", 250, 260)
f.port("VIN", 230, 140)                 # circle left of its pin
f.port("VOUT", 220, 200)

f.junction("JX", "net-x", 250, 200)     # X = V_out: IN-, D_1, R_1, the port

# ---------------------------------------------------------------- nets
f.net("net-in", [("VIN", "P"), ("OA", "IN+")])
f.net("net-y", [("OA", "OUT"), ("D1", "K")])
f.net("net-x", [("OA", "IN-"), ("D1", "A"), ("VOUT", "P"), ("R1", "1")])
f.net("net-gnd-1", [("R1", "2"), ("GND1", "0")])

# ---------------------------------------------------------------- routes
T, J = f.term, f.jn
f.route("r-in", "net-in", T("VIN", "P"), [("to", T("OA", "IN+"))])
f.route("r-y", "net-y", T("OA", "OUT"), [("bend", 350, 150), ("bend", 350, 200),
                                         ("to", T("D1", "K"))])
f.route("r-x-in", "net-x", T("OA", "IN-"), [("to", J("JX"))])
f.route("r-x-d", "net-x", J("JX"), [("to", T("D1", "A"))])
f.route("r-x-vout", "net-x", J("JX"), [("to", T("VOUT", "P"))])
f.route("r-x-r1", "net-x", J("JX"), [("to", T("R1", "1"))])
# R_1's lower pin and GND1's pin share a coordinate -> no route needed.

f.terminal("terminal-vin", "V_in", "net-in", "input", ["VIN"])
f.terminal("terminal-vout", "V_out", "net-x", "output", ["VOUT"])

# ---------------------------------------------------------------- annotations
f.inst_label("R1", 13, 5, "start")            # resistor ink is +/-5.37 wide
f.inst_label("D1", 0, dy_below(7.33, 5.5), "middle")
f.port_label("VIN", "terminal-vin", -LABEL_PORT, 5, "end")
f.port_label("VOUT", "terminal-vout", -LABEL_PORT, 5, "end")
f.text("note-x", 240, 170, "end", "X")
f.text("note-y", 360, 155, "start", "Y")

# r-y is the feedback wrap from the op amp output back down to the
# diode: both ends are pinned by the topology, so it is a long haul.
f.build(long_haul={"r-y"}, extra_evidence=[], density_ref=("OA", 40.9),
        viewbox=(170, 118, 215, 165))
