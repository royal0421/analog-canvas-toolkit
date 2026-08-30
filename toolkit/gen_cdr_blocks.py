# -*- coding: utf-8 -*-
"""CDR architecture: an Alexander phase detector (FF1/FF2/FF3 + latch + two
XORs) into a V/I converter, a loop filter and a VCO, with CK fed back.

Layout re-derived 2026-08-30 from the user's own edit of this figure
(`Downloads\\CDR architecture.icproj.json`).  The rules his edit encodes are
now SOP 3H; the ones that shaped this file:

  * every wire that meets a box ends on a junction sitting **exactly on the
    box edge** (FF1 spans 120..220, so its pins are 120 and 220);
  * a branch between two boxes sits at the **midpoint of the gap**
    (FF1 out 220, FF2 in 280 -> the tap to X1 is at 250);
  * two nets never share a column: net-b detours to x=440 because net-d
    already owns x=420;
  * the feedback enters the dashed block through an arrow drawn over the
    wire, so the reader sees the direction.

FF/Latch/VCO have no symbol in the library, so they are drafting rectangles
with text; every box-edge junction is touched by exactly one route, hence the
long `rail_ends` exemption list.
"""
import os
from icproj import Schematic, name, plain, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic("project-cdr-blocks", "CDR architecture", "CDR",
              out_proj=os.path.join(OUT, "CDR_architecture.icproj.json"),
              out_svg=os.path.join(HERE, "preview_cdr.svg"))

# ---------------------------------------------------------------- placement
#   rows  30 D_out | 110 X1 | 160 upper block row (FF1/FF2/VCO/V-I) |
#         210 X2 | 240 lower block row (FF3/Latch) | 350 CK feedback
#   cols  30 D_in | 120..220 FF1,FF3 | 280..380 FF2,Latch | 480 XORs
#         620 V/I | 700..760 loop filter | 820..920 VCO | 990 CK
f.place("X1", "xor-gate", 480, 110, extra={
    "schematicReference": "X1", "schematicName": name("X_1")})
f.place("X2", "xor-gate", 480, 210, extra={
    "schematicReference": "X2", "schematicName": name("X_2")})
f.place("VI", "comparator-unmarked", 620, 160, extra={
    "schematicReference": "VI", "schematicName": name("A_1")})
f.passive("R", "resistor", 700, 210, "R")
f.passive("C1", "capacitor", 700, 270, "C_1")
f.passive("C2", "capacitor", 760, 210, "C_2")
f.gnd("G1", 700, 300)
f.gnd("G2", 760, 300)   # SOP 3E-4: all grounds on one row
f.port("DIN", 30, 200)
f.port("DOUT", 490, 30, mirror="x")
f.port("CK", 990, 160, mirror="x")

# ------------------------------------------------------------------- boxes
BOX = (("FF1", 170, 160, "FF_1"), ("FF2", 330, 160, "FF_2"),
       ("FF3", 170, 240, "FF_3"), ("LAT", 330, 240, None),
       ("VCO", 870, 160, None))
for rid, cx, cy, lab in BOX:
    f.rect("box-" + rid, cx, cy, 100, 50)
    f.text("t-" + rid, cx, cy + 5, "middle",
           name(lab) if lab else plain("Latch" if rid == "LAT" else "VCO"))
f.rect("box-pd", 290, 190, 460, 220, style="dashed")
f.text("t-pd", 90, 110, "start", plain("Alexander PD"))

# --------------------------------------------------------------- junctions
#   *I / *O ride the box edges; JA / JB / JD are the branch points.
for jid, net, x, y in (
        ("JIN", "net-din", 90, 200),
        ("JF1I", "net-din", 120, 160), ("JF3I", "net-din", 120, 240),
        ("JF1O", "net-a", 220, 160), ("JA", "net-a", 250, 160),
        ("JF2I", "net-a", 280, 160),
        ("JF2O", "net-b", 380, 160), ("JB", "net-b", 400, 160),
        ("JF3O", "net-c", 220, 240), ("JLI", "net-c", 280, 240),
        ("JLO", "net-d", 380, 240), ("JD", "net-d", 420, 220),
        ("JVC", "net-vc", 700, 160), ("JC2", "net-vc", 760, 160),
        ("JVI", "net-vc", 820, 160),
        ("JVO", "net-ck", 920, 160), ("JCK", "net-ck", 960, 160),
        ("JFB", "net-ck", 320, 300)):
    f.junction(jid, net, x, y)

# -------------------------------------------------------------------- nets
f.net("net-din", [("DIN", "P")])
f.net("net-a", [("X1", "A")])                 # FF1 out -> FF2 in, X1 A
f.net("net-b", [("DOUT", "P"), ("X2", "A")])  # FF2 out -> D_out, X2 A
f.net("net-c", [])                            # FF3 out -> Latch in
f.net("net-d", [("X1", "B"), ("X2", "B")])    # Latch out -> both XORs
f.net("net-y", [("X1", "Y"), ("VI", "IN-")])
f.net("net-x", [("X2", "Y"), ("VI", "IN+")])
f.net("net-vc", [("VI", "OUT"), ("R", "1"), ("C2", "1")])
f.net("net-rc", [("R", "2"), ("C1", "1")])
f.net("net-ck", [("CK", "P")])
f.net("net-gnd-1", [("C1", "2"), ("G1", "0"), ("C2", "2"), ("G2", "0")])

# ------------------------------------------------------------------ routes
T, Jn = f.term, f.jn
f.route("r-in0", "net-din", T("DIN", "P"), [("to", Jn("JIN"))])
f.route("r-in1", "net-din", Jn("JIN"), [("bend", 90, 160), ("to", Jn("JF1I"))])
f.route("r-in2", "net-din", Jn("JIN"), [("bend", 90, 240), ("to", Jn("JF3I"))])

f.route("r-a1", "net-a", Jn("JF1O"), [("to", Jn("JA"))])
f.route("r-a2", "net-a", Jn("JA"), [("to", Jn("JF2I"))])
f.route("r-a3", "net-a", Jn("JA"), [("bend", 250, 100), ("to", T("X1", "A"))])

f.route("r-b1", "net-b", Jn("JF2O"), [("to", Jn("JB"))])
f.route("r-b2", "net-b", Jn("JB"), [("bend", 400, 30), ("to", T("DOUT", "P"))])
f.route("r-b3", "net-b", Jn("JB"), [("bend", 440, 160), ("bend", 440, 200),
                                    ("to", T("X2", "A"))])

f.route("r-c1", "net-c", Jn("JF3O"), [("to", Jn("JLI"))])

f.route("r-d1", "net-d", Jn("JLO"), [("bend", 420, 240), ("to", Jn("JD"))])
f.route("r-d2", "net-d", Jn("JD"), [("to", T("X2", "B"))])
f.route("r-d3", "net-d", Jn("JD"), [("bend", 420, 120), ("to", T("X1", "B"))])

f.route("r-y", "net-y", T("X1", "Y"), [("bend", 550, 110), ("bend", 550, 150),
                                       ("to", T("VI", "IN-"))])
f.route("r-x", "net-x", T("X2", "Y"), [("bend", 550, 210), ("bend", 550, 170),
                                       ("to", T("VI", "IN+"))])

f.route("r-v1", "net-vc", T("VI", "OUT"), [("to", Jn("JVC"))])
f.route("r-v2", "net-vc", Jn("JVC"), [("to", T("R", "1"))])
f.route("r-v3", "net-vc", Jn("JVC"), [("to", Jn("JC2"))])
f.route("r-v4", "net-vc", Jn("JC2"), [("to", T("C2", "1"))])
f.route("r-v5", "net-vc", Jn("JC2"), [("to", Jn("JVI"))])
f.route("r-rc", "net-rc", T("R", "2"), [("to", T("C1", "1"))])
f.route("r-g2", "net-gnd-1", T("C2", "2"), [("to", T("G2", "0"))])

f.route("r-k1", "net-ck", Jn("JVO"), [("to", Jn("JCK"))])
f.route("r-k2", "net-ck", Jn("JCK"), [("to", T("CK", "P"))])
f.route("r-k3", "net-ck", Jn("JCK"), [("bend", 960, 350), ("bend", 320, 350),
                                      ("to", Jn("JFB"))])

# ------------------------------------------------------------- annotations
f.terminal("t-din", "D_in", "net-din", "input", ["DIN"])
f.terminal("t-dout", "D_out", "net-b", "output", ["DOUT"])
f.terminal("t-ck", "CK", "net-ck", "output", ["CK"])
f.port_label("DIN", "t-din", -LABEL_PORT, 5, "end")
f.port_label("DOUT", "t-dout", LABEL_PORT, 5, "start")
f.port_label("CK", "t-ck", LABEL_PORT, 5, "start")
f.inst_label("R", 13, 5, "start")
f.inst_label("C1", 13, 5, "start")
f.inst_label("C2", 13, 5, "start")
# X / Y sit in the notch between the comparator input leads: the box model
# sees the whole triangle+leads rectangle, so declare VI as their owner or
# the crowding audit reports a gap that is not there.
f.text("n-y", 575, 134, "end", "Y", owner="VI")
f.text("n-x", 575, 200, "end", "X", owner="VI")
f.text("n-vc", 715, 146, "start", "V_cont")
f.text("t-vi", 635, 134, "middle", plain("V/I"), owner="VI")
# the feedback arrow rides the last leg, pointing into the dashed block
f.arrow("arrow-fb", 320, 348, 320, 300)

f.build(long_haul={"r-in0", "r-a3", "r-c1", "r-b2", "r-b3", "r-d1", "r-d3",
                   "r-y", "r-x", "r-v1", "r-v3", "r-v5", "r-k1", "r-k3",
                   "r-g2"},
        extra_evidence=[],
        rail_ends={"JF1I", "JF3I", "JF1O", "JF2I", "JF2O", "JF3O", "JLI",
                   "JLO", "JVI", "JVO", "JFB"},
        viewbox=(-20, 10, 1080, 370),
        # plain text on purpose (values / block titles): the
        # editor's generator italicises everything, we follow the
        # textbook page instead -- SOP 4
        expect_differ={"instance-label-CK", "t-LAT", "t-VCO", "t-pd", "t-vi"})
