# -*- coding: utf-8 -*-
"""Razavi Fig. 8.69: an op amp linearising a common-emitter stage.

The op amp drives Q_1's base and senses the emitter node X through the 100 ohm
degeneration resistor, so the loop forces V_X = V_in and the collector current
is set by V_in / 100.

Topology from `python scan_figure.py <screenshot>` (SOP §3C):
  * the op amp has "+" on TOP -> symbol `opamp-inputs-swapped`
  * dots at the collector node (V_out tap) and at node X; the feedback runs
    from X left, up, and back into IN-
  * the only GAPs in the wire runs sit exactly where the two resistor bodies
    and the transistor are, so nothing is disconnected
"""
import os
from icproj import Schematic, name_suffix, plain, dy_above, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-razavi-fig-8-69",
    "Razavi Fig. 8.69 — op amp linearising a common-emitter stage",
    "Fig_8_69",
    out_proj=os.path.join(OUT, "Razavi_Fig_8_69_opamp-linearized-CE.icproj.json"),
    out_svg=os.path.join(HERE, "preview_fig869.svg"))

# ---------------------------------------------------------------- placement
# Density reference measured off the page: npn height 60 units / figure height
# = 35.6%, aspect 1.46.  Every gap below is the grid-10 floor.
#   column 200 V_in | 330 op amp centre | 420 Q_1 and the supply column
#   rows   100 V_CC | 150 500R | 180 collector node | 220 Q_1 and op amp
#          260 node X | 290 100R | 330 ground
# V_CC and GND1 are placed so their pins land exactly ON the resistor
# pins: coincident terminals need no wire, which is worth 10 units each.
f.place("VCC", "vdd-port", 420, 110, extra={"schematicReference": "VCC"})
f.passive("R500", "resistor", 420, 150, "R_C")
f.bjt("Q1", "npn", 420, 220, "none", "Q_1")
f.passive("R100", "resistor", 420, 290, "R_E")
f.place("OA", "opamp-inputs-swapped", 350, 220,
        extra={"schematicReference": "OA"})
f.place("VIN", "voltage-source", 270, 270,
        extra={"schematicReference": "VIN"})
f.gnd("GND1", 420, 320)
f.gnd("GND2", 270, 310)
f.port("VOUT", 470, 180, mirror="x")

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("JOUT", "net-out", 420, 180),   # collector node: R_C, Q_1.C, V_out
        ("JX", "net-x", 420, 260)):      # emitter node X: R_E, Q_1.E, IN-
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
f.net("net-vcc", [("VCC", "P"), ("R500", "1")])
f.net("net-out", [("R500", "2"), ("Q1", "C"), ("VOUT", "P")])
f.net("net-base", [("OA", "OUT"), ("Q1", "B")])
f.net("net-x", [("Q1", "E"), ("R100", "1"), ("OA", "IN-")])
f.net("net-in", [("VIN", "+"), ("OA", "IN+")])
f.net("net-gnd-1", [("R100", "2"), ("GND1", "0")])
f.net("net-gnd-2", [("VIN", "-"), ("GND2", "0")])

# ---------------------------------------------------------------- routes
T, J = f.term, f.jn
f.route("r-out-rc", "net-out", T("R500", "2"), [("to", J("JOUT"))])
f.route("r-out-c", "net-out", J("JOUT"), [("to", T("Q1", "C"))])
f.route("r-out-port", "net-out", J("JOUT"), [("to", T("VOUT", "P"))])
f.route("r-base", "net-base", T("OA", "OUT"), [("to", T("Q1", "B"))])
f.route("r-x-e", "net-x", T("Q1", "E"), [("to", J("JX"))])
f.route("r-x-re", "net-x", J("JX"), [("to", T("R100", "1"))])
# Feedback X -> IN-: left along the emitter row, then straight up.
f.route("r-x-fb", "net-x", J("JX"), [("bend", 300, 260),
                                     ("to", T("OA", "IN-"))])
f.route("r-in", "net-in", T("VIN", "+"), [("bend", 270, 210),
                                          ("to", T("OA", "IN+"))])
f.route("r-g2", "net-gnd-2", T("VIN", "-"), [("to", T("GND2", "0"))])

# ------------------------------------------------- cell terminals for ports
f.terminal("terminal-vout", "V_out", "net-out", "output", ["VOUT"])

# ---------------------------------------------------------------- annotations
# Razavi labels the passives with VALUES, not names, so they go in as upright
# drafting text (icproj.plain) -- the schematic names R_C / R_E exist only for
# the netlist and carry no label.
f.inst_label("Q1", 8, 5, "start")          # BJT ink sits on the centre line
f.port_label("VOUT", "terminal-vout", LABEL_PORT, 5, "start")

for tid, x, y, align, label, owner in (
        ("note-vcc", 445, 110, "start", name_suffix("V_CC", " = 2.5 V"), "VCC"),
        ("note-rc", 433, 155, "start", plain("500 Ω"), "R500"),
        ("note-re", 433, 295, "start", plain("100 Ω"), "R100"),
        ("note-vin", 242, 275, "end", "V_in", "VIN"),
        ("note-x", 379, 280, "end", "X", None)):
    f.text(tid, x, y, align, label, owner)

f.build(long_haul={
            "r-x-fb",      # node X back to the inverting input, as in the book
            "r-in",        # the source's + terminal across to the + input
        },
        extra_evidence=[],
        density_ref=("Q1", 35.6),
        viewbox=(180, 90, 400, 250),
        # plain text on purpose (values / block titles): the
        # editor's generator italicises everything, we follow the
        # textbook page instead -- SOP 4
        expect_differ={"note-vcc", "note-rc", "note-re"})
