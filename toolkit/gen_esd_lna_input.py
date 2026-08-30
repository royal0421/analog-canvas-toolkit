# -*- coding: utf-8 -*-
"""ESD-protected LNA input stage: IN -> ESD network -> L_g -> cascode
(M_1 with L_deg degeneration, M_2 gated at VDD) -> L_load -> C_tune -> OUT,
with dual-diode CDM protection on the gate node and a diode pair plus a
20 kOhm bleeder on the output node.

Topology from `python scan_figure.py <screenshot>` (SOP 3C) plus three 4x
crops for the parts a scanner cannot classify (SOP 3E: diode orientation is
read off the image, everything else is measured):
  * all four diodes point UP -- anode at the bottom.  So the gate node and the
    output node each get a "node -> VDD" diode and a "GND -> node" diode;
  * the dot at (431,54) is where M_2's gate wire, L_load and the VDD marker
    meet: M_2 is a cascode biased straight at VDD, and its gate wire goes
    left, up and back right, clear of the CDM column;
  * the 20k sits in PARALLEL with the upper output diode, returning to the
    column 10 units ABOVE the output node -- not onto it, or it would overlap
    the OUT lead.

The four VDD markers are deliberately NOT wired to each other: they are power
markers on one net, which is how the page draws them (user, 2026-08-30).
"""
import os
from icproj import Schematic, name, plain, dy_above

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-esd-lna-input",
    "ESD-protected LNA input stage",
    "ESDLNA",
    out_proj=os.path.join(OUT, "ESD-LNA_input-stage_CDM-protection.icproj.json"),
    out_svg=os.path.join(HERE, "preview_esdlna.svg"),
    supply_net="net-vdd", rail_end="VDDT", supply_name="VDD",
    nmos_bulk_net="net-gnd")

# ---------------------------------------------------------------- placement
#   cols  80 IN | 120..240 ESD box | 300 L_g | 360 CDM column | 440 M_1/M_2
#         530 C_tune | 590 output ESD column | 650 the 20k | 680 OUT
#   rows  90 VDD markers | 160 L_load | 200 drain node / output line
#         240 M_2 | 300 gate line | 370 L_deg | 410 grounds
def diode(iid, x, y, ref):
    """rotation 270 puts the anode at the BOTTOM (see the 4x crop)."""
    f.place(iid, "diode", x, y, rotation=270, extra={
        "schematicReference": iid, "schematicName": name(ref),
        "netlist": {"binding": {"kind": "primitive", "deviceClass": "diode"},
                    "parameters": {}, "reference": iid}})


def coil(iid, x, y, ref, rotation=0):
    f.place(iid, "inductor", x, y, rotation=rotation, extra={
        "schematicReference": iid, "schematicName": name(ref),
        "netlist": {"binding": {"kind": "primitive", "deviceClass": "inductor"},
                    "parameters": {}, "reference": iid}})


f.port("IN", 50, 300)
f.port("OUT", 660, 200, mirror="x")
f.rect("box-esd", 150, 300, 120, 140, style="dashed")
for tid, ty, txt in (("t-esd1", 288, "Input ESD"),
                        ("t-esd2", 322, "prot. network")):
    f.text(tid, 150, ty, "middle", plain(txt))

coil("LG", 270, 300, "L_g", rotation=90)
coil("LLOAD", 430, 160, "L_load")
coil("LDEG", 430, 370, "L_deg")
f.mos("M1", "nmos", 420, 300, "none", "M_1")
f.mos("M2", "nmos", 420, 240, "none", "M_2")
f.passive("CT", "capacitor", 510, 200, "C_tune", rotation=90)
f.passive("R20", "resistor", 630, 150, "R_ESD")
diode("DC1", 330, 250, "D_1")      # gate node -> VDD
diode("DC2", 330, 350, "D_2")      # GND -> gate node
diode("DO1", 570, 150, "D_3")      # OUT -> VDD
diode("DO2", 570, 240, "D_4")      # GND -> OUT

for iid, x, y in (("VDDE", 150, 190), ("VDDC", 330, 210),
                  ("VDDT", 430, 90), ("VDDO", 570, 90)):
    f.place(iid, "vdd-port", x, y, extra={"schematicReference": iid})
for iid, x, y in (("GNDE", 150, 410), ("GNDC", 330, 380),
                  ("GNDD", 430, 410), ("GNDO", 570, 270)):
    f.gnd(iid, x, y)

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("JBL", "net-in", 90, 300),      # the dashed box has no pins, so
        ("JBR", "net-lg", 210, 300),      # each wire ends on its edge
        ("JBT", "net-vdd", 150, 230),
        ("JBB", "net-gnd", 150, 370),
        ("JG", "net-g", 330, 300),        # gate node: L_g, both CDM diodes, M_1
        ("JD", "net-d", 430, 200),        # M_2 drain: L_load and C_tune
        ("JR", "net-out", 570, 190),      # the 20k returns just above the node
        ("JO", "net-out", 570, 200)):     # output node
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------------- nets
f.net("net-in", [("IN", "P")])
f.net("net-lg", [("LG", "2")])
f.net("net-g", [("LG", "1"), ("DC1", "A"), ("DC2", "K"), ("M1", "G")])
f.net("net-m", [("M1", "D"), ("M2", "S")])
f.net("net-d", [("M2", "D"), ("LLOAD", "2"), ("CT", "2")])
f.net("net-out", [("CT", "1"), ("DO1", "A"), ("DO2", "K"), ("R20", "2"),
                  ("OUT", "P")])
f.net("net-vdd", [("VDDE", "P"), ("VDDC", "P"), ("VDDT", "P"), ("VDDO", "P"),
                  ("LLOAD", "1"), ("M2", "G"), ("DC1", "K"), ("DO1", "K"),
                  ("R20", "1")])
f.net("net-s", [("M1", "S"), ("LDEG", "1")])
f.net("net-gnd", [("GNDE", "0"), ("GNDC", "0"), ("GNDD", "0"), ("GNDO", "0"),
                  ("DC2", "A"), ("DO2", "A"), ("LDEG", "2"),
                  ("M1", "B"), ("M2", "B")])

# -------------------------------------------------------------------- routes
T, Jn = f.term, f.jn
f.route("r-in", "net-in", T("IN", "P"), [("to", Jn("JBL"))])
f.route("r-lg", "net-lg", Jn("JBR"), [("to", T("LG", "2"))])
f.route("r-eb-v", "net-vdd", T("VDDE", "P"), [("to", Jn("JBT"))])
f.route("r-eb-g", "net-gnd", Jn("JBB"), [("to", T("GNDE", "0"))])

f.route("r-g-lg", "net-g", T("LG", "1"), [("to", Jn("JG"))])
f.route("r-g-d1", "net-g", Jn("JG"), [("to", T("DC1", "A"))])
f.route("r-g-d2", "net-g", Jn("JG"), [("to", T("DC2", "K"))])
f.route("r-g-m1", "net-g", Jn("JG"), [("to", T("M1", "G"))])

f.route("r-m", "net-m", T("M1", "D"), [("to", T("M2", "S"))])
f.route("r-d-m2", "net-d", T("M2", "D"), [("to", Jn("JD"))])
f.route("r-d-ll", "net-d", Jn("JD"), [("to", T("LLOAD", "2"))])
f.route("r-d-ct", "net-d", Jn("JD"), [("to", T("CT", "2"))])

f.route("r-v-ll", "net-vdd", T("VDDT", "P"), [("to", T("LLOAD", "1"))])
f.route("r-v-m2g", "net-vdd", T("M2", "G"),
        [("bend", 360, 240), ("bend", 360, 110), ("to", T("VDDT", "P"))])
# VDDC.P and DC1.K are the same point: pin-on-pin, no wire (SOP 3D trick 2)
f.route("r-v-do1", "net-vdd", T("VDDO", "P"), [("to", T("DO1", "K"))])
f.route("r-v-r20", "net-vdd", T("VDDO", "P"),
        [("bend", 630, 110), ("to", T("R20", "1"))])

f.route("r-o-ct", "net-out", T("CT", "1"), [("to", Jn("JO"))])
f.route("r-o-d1", "net-out", T("DO1", "A"), [("to", Jn("JR"))])
f.route("r-o-jr", "net-out", Jn("JR"), [("to", Jn("JO"))])
f.route("r-o-r20", "net-out", T("R20", "2"),
        [("bend", 630, 190), ("to", Jn("JR"))])
f.route("r-o-d2", "net-out", Jn("JO"), [("to", T("DO2", "K"))])
f.route("r-o-port", "net-out", Jn("JO"), [("to", T("OUT", "P"))])

f.route("r-s-ldeg", "net-s", T("M1", "S"), [("to", T("LDEG", "1"))])
# every ground symbol sits pin-on-pin under its device, so none needs a wire

f.terminal("t-in", "IN", "net-in", "input", ["IN"])
f.terminal("t-out", "OUT", "net-out", "output", ["OUT"])

# --------------------------------------------------------------- annotations
f.port_label("IN", "t-in", -14, 5, "end")
f.port_label("OUT", "t-out", 14, 5, "start")
f.inst_label("LG", 0, dy_above(30), "middle")
f.inst_label("LLOAD", -16, 5, "end")
f.inst_label("LDEG", 16, 5, "start")
f.inst_label("M1", 18, 5, "start")
f.inst_label("M2", 18, 5, "start")
f.inst_label("CT", 0, dy_above(8.05), "middle")
f.power_label("label-vdde", "net-vdd", "VDDE", 0, -8, "V_DD", "middle")
f.power_label("label-vddt", "net-vdd", "VDDT", 0, -8, "V_DD", "middle")
f.text("v-r20", 643, 155, "start", plain("20 k\u03a9"), owner="R20")
# the page points at the CDM pair with an arrow, so keep it
f.arrow("arrow-cdm", 270, 400, 308, 366)
f.text("t-cdm", 266, 418, "middle", plain("CDM protection"))

f.build(long_haul={"r-d-ct",        # 60: C_tune is pinned by both nodes
                   "r-g-m1",        # 70: the CDM column has to stand clear
                                    #     of the cascode gate wire at x=360
                   "r-v-m2g",       # 130: the cascode gate wraps to VDD
                   "r-v-r20",       # 60: the 20k hangs off the VDD marker
                   "r-o-r20",       # 60: and returns above the output node
                   "r-o-port"},     # 80: OUT has to clear the 20k column
        rail_ends={"JBL", "JBR", "JBT", "JBB"},
        viewbox=(10, 60, 710, 390),
        # plain text on purpose: block titles and the resistor value follow
        # the page, not the editor's italics -- SOP 4
        expect_differ={"t-esd1", "t-esd2", "t-cdm", "v-r20",
                       # IN / OUT must NOT be subscripted (user, 2026-08-30)
                       "instance-label-IN", "instance-label-OUT"})
