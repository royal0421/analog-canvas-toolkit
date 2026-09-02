# -*- coding: utf-8 -*-
r"""Differential pair with L_3/R_2 shunt-peaked loads, C_L at each output and a
2R_1 || C_1/2 degeneration network between the two sources, each source sunk by
its own I_0.

Column and row pitch re-derived 2026-08-30 from the user's own edit
(`Downloads\Differential pair with shunt peaking and RC degeneration.icproj.json`):
he pulled the two branches in from x 300/500 to 320/460 and lifted the tail
from y 470 to 420.  The symmetry rule that came with it is SOP 3A:
**the middle of a symmetric figure sits at the exact midpoint of the two
outer columns; if the grid will not allow it, move the two ends, not the
middle.**  Here 320 and 460 -> midpoint 390, which is on the grid."""
import os
from icproj import Schematic, name, name_suffix

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic("project-diff-deg-amp",
              "Differential pair with shunt peaking and RC degeneration",
              "DiffDeg",
              out_proj=os.path.join(OUT, "Diff-amp_shunt-peak_RC-degen.icproj.json"),
              out_svg=os.path.join(HERE, "preview_diffdeg.svg"))

# `vdd-port`, NOT `vdd`: the site has no catalog entry for `vdd`, so a
# project using it fails to import (2026-08-30).  Same pin at (0,+20).
f.place("VDD", "vdd-port", 390, 110,
        extra={"schematicReference": "VDD"})
for iid, cx in (("L3L", 320), ("L3R", 460)):
    f.place(iid, "inductor", cx, 170, extra={
        "schematicReference": iid, "schematicName": name("L_3"),
        "netlist": {"binding": {"kind": "primitive",
                                "deviceClass": "inductor"},
                    "parameters": {}, "reference": iid}})
f.passive("R2L", "resistor", 320, 230, "R_2")
f.passive("R2R", "resistor", 460, 230, "R_2")
f.passive("CLL", "capacitor", 250, 270, "C_L", rotation=90)
f.passive("CLR", "capacitor", 530, 270, "C_L", rotation=90)
f.mos("M1", "nmos", 310, 310, "none", "M_1")
f.mos("M2", "nmos", 470, 310, "x", "M_2")
# the variable symbols keep the PLAIN deviceClass -- "variable-resistor" is
# a symbolId, not a value the netlist schema accepts
for iid, sym_id, cy, dev, lab in (("R1", "variable-resistor", 350,
                                   "resistor", "R_1"),
                                  ("C1", "variable-capacitor", 390,
                                   "capacitor", "C_1")):
    f.place(iid, sym_id, 390, cy, rotation=90, extra={
        "schematicReference": iid, "schematicName": name(lab),
        "netlist": {"binding": {"kind": "primitive", "deviceClass": dev},
                    "parameters": {}, "reference": iid}})
f.isrc("I0L", 320, 420, "I_0")
f.isrc("I0R", 460, 420, "I_0")
# rot 90 puts the ground pin on its RIGHT and the body to the left; rot 270
# is the mirror of that -- so the body always points away from the circuit.
f.place("GCL", "ground", 220, 270, rotation=90,
        extra={"schematicReference": "GCL"})
f.place("GCR", "ground", 560, 270, rotation=270,
        extra={"schematicReference": "GCR"})
f.gnd("GIL", 320, 450)
f.gnd("GIR", 460, 450)
f.port("VIP", 250, 310)
f.port("VIN", 530, 310, mirror="x")
f.port("VOL", 360, 270, mirror="x")
f.port("VOR", 420, 270)

# no junction on the V_DD bus: the port pin sits ON the bus at (390,130),
# and a junction may not share a terminal's coordinate (SOP 6).
for jid, net, x, y in (("JDL", "net-ol", 320, 270),
                       ("JDR", "net-or", 460, 270),
                       ("JS1", "net-sl", 320, 350),
                       ("JS1B", "net-sl", 320, 390),
                       ("JS2", "net-sr", 460, 350),
                       ("JS2B", "net-sr", 460, 390)):
    f.junction(jid, net, x, y)

f.net("net-vdd", [("VDD", "P"), ("L3L", "1"), ("L3R", "1")])
f.net("net-ml", [("L3L", "2"), ("R2L", "1")])
f.net("net-mr", [("L3R", "2"), ("R2R", "1")])
f.net("net-ol", [("R2L", "2"), ("M1", "D"), ("CLL", "1"), ("VOL", "P")])
f.net("net-or", [("R2R", "2"), ("M2", "D"), ("CLR", "2"), ("VOR", "P")])
f.net("net-sl", [("M1", "S"), ("R1", "P2"), ("C1", "P2"), ("I0L", "+")])
f.net("net-sr", [("M2", "S"), ("R1", "P1"), ("C1", "P1"), ("I0R", "+")])
f.net("net-ip", [("VIP", "P"), ("M1", "G")])
f.net("net-in", [("VIN", "P"), ("M2", "G")])
f.net("net-gnd-1", [("CLL", "2"), ("GCL", "0"), ("CLR", "1"), ("GCR", "0"),
                    ("I0L", "-"), ("GIL", "0"), ("I0R", "-"), ("GIR", "0"),
                    ("M1", "B"), ("M2", "B")])

T, Jn = f.term, f.jn
f.route("r-v1", "net-vdd", T("VDD", "P"),
        [("bend", 320, 130), ("to", T("L3L", "1"))])
f.route("r-v2", "net-vdd", T("VDD", "P"),
        [("bend", 460, 130), ("to", T("L3R", "1"))])
f.route("r-ml", "net-ml", T("L3L", "2"), [("to", T("R2L", "1"))])
f.route("r-mr", "net-mr", T("L3R", "2"), [("to", T("R2R", "1"))])

for s, R2, JD, CL, CLp, M, VO in (("l", "R2L", "JDL", "CLL", "1", "M1", "VOL"),
                                  ("r", "R2R", "JDR", "CLR", "2", "M2", "VOR")):
    f.route("r-%s1" % s, "net-o%s" % s, T(R2, "2"), [("to", Jn(JD))])
    f.route("r-%s2" % s, "net-o%s" % s, Jn(JD), [("to", T(M, "D"))])
    f.route("r-%s3" % s, "net-o%s" % s, Jn(JD), [("to", T(CL, CLp))])
    f.route("r-%s4" % s, "net-o%s" % s, Jn(JD), [("to", T(VO, "P"))])

f.route("r-s1", "net-sl", T("M1", "S"), [("to", Jn("JS1"))])
f.route("r-s2", "net-sl", Jn("JS1"), [("to", T("R1", "P2"))])
f.route("r-s3", "net-sl", Jn("JS1"), [("to", Jn("JS1B"))])
f.route("r-s4", "net-sl", Jn("JS1B"), [("to", T("C1", "P2"))])
f.route("r-s5", "net-sl", Jn("JS1B"), [("to", T("I0L", "+"))])
f.route("r-t1", "net-sr", T("M2", "S"), [("to", Jn("JS2"))])
f.route("r-t2", "net-sr", Jn("JS2"), [("to", T("R1", "P1"))])
f.route("r-t3", "net-sr", Jn("JS2"), [("to", Jn("JS2B"))])
f.route("r-t4", "net-sr", Jn("JS2B"), [("to", T("C1", "P1"))])
f.route("r-t5", "net-sr", Jn("JS2B"), [("to", T("I0R", "+"))])
f.route("r-ip", "net-ip", T("VIP", "P"), [("to", T("M1", "G"))])
f.route("r-in", "net-in", T("VIN", "P"), [("to", T("M2", "G"))])
# C_L caps and the two I_0 sit pin-on-pin on their ground symbols

for tid, nm, net, ports, d in (("t-ip", "V_in+", "net-ip", ["VIP"], "input"),
                               ("t-in", "V_in-", "net-in", ["VIN"], "input"),
                               ("t-ol", "V_o+", "net-ol", ["VOL"], "output"),
                               ("t-or", "V_o-", "net-or", ["VOR"], "output")):
    f.terminal(tid, nm, net, d, ports)

f.inst_label("L3L", -16, 5, "end")
f.inst_label("L3R", 16, 5, "start")
f.inst_label("R2L", -13, 5, "end")
f.inst_label("R2R", 13, 5, "start")
f.inst_label("CLL", 0, -16, "middle")
f.inst_label("CLR", 0, -16, "middle")
f.inst_label("I0L", -18, 5, "end")
f.inst_label("I0R", 18, 5, "start")
f.text("v-r1", 390, 332, "middle", name("2R_1"), owner="R1")
f.text("v-c1", 390, 420, "middle", name_suffix("C_1", "/2"), owner="C1")
# the user's export has this at y=270; that is the editor snapping a drag
# to the 10-unit grid -- the calibrated value is centre + 5 (SOP 4).
f.text("n-vo", 390, 275, "middle", "V_o")
f.power_label("label-vdd", "net-vdd", "VDD", 20, 5, "V_DD")

f.build(long_haul={"r-v1", "r-v2", "r-l3", "r-r3", "r-s2", "r-s4",
                   "r-t2", "r-t4"},
        extra_evidence=[
            {"id": "cev-vdd-marker", "kind": "name-claim", "netId": "net-vdd",
             "name": "VDD", "owner": {"kind": "power-marker",
                                      "objectId": "VDD"},
             "scope": "global", "powerDomain": "vdd"}],
        viewbox=(180, 85, 420, 400),
        # plain text on purpose (values / block titles): the
        # editor's generator italicises everything, we follow the
        # textbook page instead -- SOP 4
        expect_differ=set())
