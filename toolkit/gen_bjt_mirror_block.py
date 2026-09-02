# -*- coding: utf-8 -*-
"""BJT current mirror biasing a load block: I_REF sets Q_REF (diode-connected),
Q_1 copies it as I_1 into a "Circuit" block hanging from the V_CC = 2.5 V rail.

Topology from `python scan_figure.py <screenshot>` (SOP 3C):
  * rail y=45 spans x 138..387 (thick 6) -- a real power rail, not a vdd-port;
  * x=160 drops from the rail with a 43 px GAP (the I_REF circle) onto the
    collector node, which runs right at y=249 to x=228 and down to the base
    bus at y=295: the diode tie, so Q_REF's base plate faces RIGHT (mirrored)
    and Q_1's faces left;
  * x=364 drops from the rail into the box (y 90..181) and out again to Q_1's
    collector, with the I_1 arrow on that lead.

Density: this page is drawn loose (a big block and big labels put the BJT at
~16% of the figure height, against Razavi's 35-40%), so the spacing here is
SOP 3A's absolute constants and the check is the aspect, not the percentage.
"""
import os
from icproj import Schematic, name, name_suffix, plain

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-bjt-mirror-block",
    "BJT current mirror driving a circuit block",
    "MirrorBlock",
    out_proj=os.path.join(OUT, "BJT-current-mirror_circuit-block.icproj.json"),
    out_svg=os.path.join(HERE, "preview_mirrorblock.svg"),
    supply_net="net-vcc", rail_end="jvcc-end", supply_name="VCC")

# ---------------------------------------------------------------- placement
#   cols 180 I_REF / Q_REF | 240 diode tie | 320 Q_1 and the block
#   rows 100 V_CC rail | 140 I_REF centre (+120 / -160) | 180 collector node
#        200 C pins | 230 device centres = base bus | 260 E pins | 270 grounds
#        block 100x50 centred (320,145) -> edges 120 and 170
f.isrc("IREF", 180, 140, "I_REF")
f.bjt("QREF", "npn", 180, 230, "x", "Q_REF")      # base plate faces right
f.bjt("Q1", "npn", 320, 230, "none", "Q_1")
f.gnd("GNDR", 180, 270)                           # pin-on-pin under each E
f.gnd("GND1", 320, 270)
f.rect("box-circuit", 320, 145, 100, 50)
f.text("t-circuit", 320, 150, "middle", plain("Circuit"))

# ---------------------------------------------------------------- junctions
RAIL = [160, 180, 320, 340]
J = [("jvcc-start", "net-vcc", 160, 100), ("jvcc-1", "net-vcc", 180, 100),
     ("jvcc-2", "net-vcc", 320, 100), ("jvcc-end", "net-vcc", 340, 100)]
for jid, net, x, y in J + [
        ("JBT", "net-vcc", 320, 120),   # the block has no pins: every wire
        ("JBB", "net-c1", 320, 170),    # that meets it ends on its edge
        ("JA", "net-b", 180, 180),      # I_REF / Q_REF collector / diode tie
        ("JB", "net-b", 240, 230)]:     # the tie lands on the base bus
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
f.net("net-vcc", [("IREF", "+")])
f.net("net-b", [("IREF", "-"), ("QREF", "C"), ("QREF", "B"), ("Q1", "B")])
f.net("net-c1", [("Q1", "C")])
f.net("net-gnd-1", [("QREF", "E"), ("GNDR", "0")])
f.net("net-gnd-2", [("Q1", "E"), ("GND1", "0")])

# ---------------------------------------------------------------- routes
T, Jn = f.term, f.jn
f.rail("net-vcc", 100, RAIL, prefix="r-vcc-rail")
f.route("r-v-iref", "net-vcc", Jn("jvcc-1"), [("to", T("IREF", "+"))])
f.route("r-v-box", "net-vcc", Jn("jvcc-2"), [("to", Jn("JBT"))])
f.route("r-c1", "net-c1", Jn("JBB"), [("to", T("Q1", "C"))])

f.route("r-a-iref", "net-b", T("IREF", "-"), [("to", Jn("JA"))])
f.route("r-a-qc", "net-b", Jn("JA"), [("to", T("QREF", "C"))])
f.route("r-tie", "net-b", Jn("JA"), [("bend", 240, 180), ("to", Jn("JB"))])
f.route("r-b-ref", "net-b", T("QREF", "B"), [("to", Jn("JB"))])
f.route("r-b-q1", "net-b", Jn("JB"), [("to", T("Q1", "B"))])

# ---------------------------------------------------------------- annotations
f.inst_label("IREF", -18, 5, "end")
f.inst_label("QREF", -8, 5, "end")
f.inst_label("Q1", 8, 5, "start")
f.power_label("label-vcc", "net-vcc", "jvcc-end", 12, 6,
              name_suffix("V_CC", " = 2.5 V"))
# I_1 flows DOWN out of the block into Q_1's collector (SOP 6B: drafting,
# 20 units long, no strokeScale of its own).
f.arrow("arrow-i1", 320, 175, 320, 195)
f.text("note-i1", 332, 190, "start", "I_1")

f.build(long_haul={"r-vcc-rail-1",             # 140: the rail itself
                   "r-tie",                    # 60: collector node to the bus
                   "r-b-q1"},                  # 40 is the budget, this is 40
        rail_ends={"jvcc-start", "jvcc-end", "JBT", "JBB"},
        viewbox=(115, 85, 380, 215),
        # plain text on purpose: the rail's "= 2.5 V" and the block title
        # follow the textbook page, not the editor's italics -- SOP 4
        expect_differ=set())
