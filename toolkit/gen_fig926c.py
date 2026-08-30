# -*- coding: utf-8 -*-
"""Razavi Fig. 9.26(c): a BJT current mirror whose three output devices are
tied together, so the copied current is 3 I_REF.

Topology from `python scan_figure.py <screenshot>` (SOP §3C):
  * Q_REF's collector column sits LEFT of its base plate while Q_1..Q_3's sit
    right of theirs -- Q_REF is mirrored, the outputs are not;
  * the diode tie leaves the collector node, runs right and drops onto the
    base bus (dot between Q_REF and Q_1), so collector and base share one net;
  * the three collectors share a bus with a single dot at Q_2's column, where
    the I_copy arrow feeds in; the grounds sit pin-on-pin under each emitter.
Scale of the page: the base plate prints 40 px for the symbol's 26.67 units,
i.e. 1.50 px/unit, so the BJT is 60/149 = 40.2% of the figure height.
"""
import os
from icproj import Schematic, name, plain, dy_above

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-razavi-fig-9-26c",
    "Razavi Fig. 9.26(c) — BJT current mirror with combined outputs",
    "Fig_9_26c",
    out_proj=os.path.join(OUT, "Razavi_Fig_9_26c_BJT-mirror-combined-outputs.icproj.json"),
    out_svg=os.path.join(HERE, "preview_fig926c.svg"),
    supply_net="net-vcc", rail_end="VDD", supply_name="VCC")

# ---------------------------------------------------------------- placement
#   cols 180 V_CC / I_REF / Q_REF | 240 diode tie | 300 Q_1 | 400 Q_2 | 500 Q_3
#   rows 100 V_CC bar | 120 I_REF top pin (pin on pin, no wire) | 140 I_REF
#        centre and the collector bus | 170 node A | 180 C pins
#        210 transistor centres = base bus | 240 E pins | 250 grounds
# No power rail in this figure: the book draws the short V_CC bar, so the
# vdd-port is right here (SOP §2 bans it only when there IS a rail).
f.place("VDD", "vdd-port", 180, 100, extra={"schematicReference": "VDD"})
f.isrc("IREF", 180, 140, "I_REF")
f.bjt("QREF", "npn", 180, 210, "x", "Q_REF")      # base plate faces right
f.bjt("Q1", "npn", 300, 210, "none", "Q_1")
f.bjt("Q2", "npn", 400, 210, "none", "Q_2")
f.bjt("Q3", "npn", 500, 210, "none", "Q_3")
for iid, x in (("GNDR", 180), ("GND1", 300), ("GND2", 400), ("GND3", 500)):
    f.gnd(iid, x, 250)                            # pin on each emitter pin

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("JA", "net-b", 180, 170),      # I_REF / Q_REF collector / diode tie
        ("JB", "net-b", 240, 210),      # the tie lands on the base bus
        ("JC1", "net-c", 300, 140),     # collector bus: two directions only,
        ("JC2", "net-c", 400, 140),     # so only JC2 draws a dot -- which is
        ("JC3", "net-c", 500, 140)):    # where I_copy is taken, as in the book
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
f.net("net-vcc", [("VDD", "P"), ("IREF", "+")])
f.net("net-b", [("IREF", "-"), ("QREF", "C"), ("QREF", "B"),
                ("Q1", "B"), ("Q2", "B"), ("Q3", "B")])
f.net("net-c", [("Q1", "C"), ("Q2", "C"), ("Q3", "C")])
f.net("net-gnd-1", [("QREF", "E"), ("GNDR", "0")])
f.net("net-gnd-2", [("Q1", "E"), ("GND1", "0")])
f.net("net-gnd-3", [("Q2", "E"), ("GND2", "0")])
f.net("net-gnd-4", [("Q3", "E"), ("GND3", "0")])

# ---------------------------------------------------------------- routes
T, J = f.term, f.jn
# V_CC bar sits pin-on-pin on I_REF's top terminal, and every ground sits
# pin-on-pin under its emitter: neither needs a wire (SOP §3D trick 2).
f.route("r-a-iref", "net-b", T("IREF", "-"), [("to", J("JA"))])
f.route("r-a-qc", "net-b", J("JA"), [("to", T("QREF", "C"))])
f.route("r-tie", "net-b", J("JA"), [("bend", 240, 170), ("to", J("JB"))])
f.route("r-b-ref", "net-b", T("QREF", "B"), [("to", J("JB"))])
f.route("r-b-q1", "net-b", J("JB"), [("to", T("Q1", "B"))])
f.route("r-b-q2", "net-b", T("Q1", "B"), [("to", T("Q2", "B"))])
f.route("r-b-q3", "net-b", T("Q2", "B"), [("to", T("Q3", "B"))])
f.route("r-c-q1", "net-c", T("Q1", "C"), [("to", J("JC1"))])
f.route("r-c-b1", "net-c", J("JC1"), [("to", J("JC2"))])
f.route("r-c-q2", "net-c", J("JC2"), [("to", T("Q2", "C"))])
f.route("r-c-b2", "net-c", J("JC2"), [("to", J("JC3"))])
f.route("r-c-q3", "net-c", J("JC3"), [("to", T("Q3", "C"))])

# ---------------------------------------------------------------- annotations
# BJT ink sits on the centre line, so the device labels take the +/-8 offset;
# Q_1..Q_3 go ABOVE instead, because the base bus runs through their own row.
f.inst_label("IREF", -18, 5, "end")
f.inst_label("QREF", -8, 5, "end")
for iid in ("Q1", "Q2", "Q3"):
    f.inst_label(iid, -8, dy_above(30), "end")
f.power_label("label-vcc", "net-vcc", "VDD", 18, 5, "V_CC")

# I_copy flows DOWN into the shared collector node; the shaft starts at the
# V_CC bar's row, exactly as the book draws it.
f.arrow("arrow-icopy", 400, 100, 400, 140)
f.text("note-icopy", 412, 122, "start",
       {"runs": name("I_copy")["runs"] + plain(" = 3 ")["runs"]
        + name("I_REF")["runs"]})

f.build(long_haul={"r-tie",                    # 60: collector node to the bus
                   "r-b-q2", "r-b-q3",         # 100: the mirror base bus
                   "r-c-b1", "r-c-b2"},        # 100: the shared collector bus
        density_ref=("Q1", 40.2),
        viewbox=(110, 85, 425, 190),
        # plain text on purpose (values / block titles): the
        # editor's generator italicises everything, we follow the
        # textbook page instead -- SOP 4
        expect_differ={"note-icopy"})
