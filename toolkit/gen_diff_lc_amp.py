# -*- coding: utf-8 -*-
"""Differential amplifier with an LC-coupled load: 2L_1 in parallel with C_B/2
bridges the two R's, L_2/C_2 take each drain out to V_out, and C_1 hangs from
each drain to ground.  Tail current I_in."""
import os
from icproj import Schematic, name, name_suffix, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic("project-diff-lc-amp", "Differential amplifier with LC load",
              "DiffLC",
              out_proj=os.path.join(OUT, "Diff-amp_LC-load.icproj.json"),
              out_svg=os.path.join(HERE, "preview_difflc.svg"))

f.place("L1", "inductor", 390, 100, rotation=90, extra={
    "schematicReference": "L1", "schematicName": name("2L_1"),
    "netlist": {"binding": {"kind": "primitive", "deviceClass": "inductor"},
                "parameters": {}, "reference": "L1"}})
f.passive("CB", "capacitor", 390, 130, "C_B", rotation=90)
f.passive("RL", "resistor", 300, 170, "R")
f.passive("RR", "resistor", 480, 170, "R")
f.place("L2L", "inductor", 220, 210, rotation=90, extra={
    "schematicReference": "L2L", "schematicName": name("L_2"),
    "netlist": {"binding": {"kind": "primitive", "deviceClass": "inductor"},
                "parameters": {}, "reference": "L2L"}})
f.place("L2R", "inductor", 560, 210, rotation=90, extra={
    "schematicReference": "L2R", "schematicName": name("L_2"),
    "netlist": {"binding": {"kind": "primitive", "deviceClass": "inductor"},
                "parameters": {}, "reference": "L2R"}})
f.passive("C2L", "capacitor", 140, 250, "C_2")
f.passive("C2R", "capacitor", 640, 250, "C_2")
f.passive("C1L", "capacitor", 350, 240, "C_1")
f.passive("C1R", "capacitor", 430, 240, "C_1")
f.mos("M1", "nmos", 290, 270, "none", "M_1")
f.mos("M2", "nmos", 490, 270, "x", "M_2")
f.isrc("IIN", 390, 330, "I_in")
for iid, x, y in (("G2L", 140, 280), ("G2R", 640, 280), ("G1L", 350, 270),
                  ("G1R", 430, 270), ("GI", 390, 360)):
    f.gnd(iid, x, y)
f.port("VINP", 230, 270)
f.port("VINN", 550, 270, mirror="x")
f.port("VOUTN", 90, 210)
f.port("VOUTP", 690, 210, mirror="x")

for jid, net, x, y in (("JL1", "net-top", 300, 100), ("JC1", "net-top", 300, 130),
                       ("JL2", "net-top2", 480, 100),
                       ("JC2", "net-top2", 480, 130),
                       ("JD1", "net-dl", 300, 210), ("JO1", "net-dl", 140, 210),
                       ("JD2", "net-dr", 480, 210), ("JO2", "net-dr", 640, 210),
                       ("JS", "net-src", 390, 290)):
    f.junction(jid, net, x, y)

# rotation 90 puts pin 1 on the RIGHT and pin 2 on the LEFT (SOP 2),
# so the LEFT node takes pin 2 -- wiring it to pin 1 draws the wire
# straight through the coil / between the plates.
f.net("net-top", [("L1", "2"), ("CB", "2"), ("RL", "1")])
f.net("net-top2", [("L1", "1"), ("CB", "1"), ("RR", "1")])
f.net("net-dl", [("RL", "2"), ("L2L", "1"), ("M1", "D"), ("C1L", "1"),
                 ("L2L", "2"), ("C2L", "1"), ("VOUTN", "P")])
f.net("net-dr", [("RR", "2"), ("L2R", "2"), ("M2", "D"), ("C1R", "1"),
                 ("L2R", "1"), ("C2R", "1"), ("VOUTP", "P")])
f.net("net-src", [("M1", "S"), ("M2", "S"), ("IIN", "+")])
f.net("net-inp", [("VINP", "P"), ("M1", "G")])
f.net("net-inn", [("VINN", "P"), ("M2", "G")])
f.net("net-gnd-1", [("C2L", "2"), ("G2L", "0"), ("C2R", "2"), ("G2R", "0"),
                    ("C1L", "2"), ("G1L", "0"), ("C1R", "2"), ("G1R", "0"),
                    ("IIN", "-"), ("GI", "0"),
                    ("M1", "B"), ("M2", "B")])

T, Jn = f.term, f.jn
f.route("r-t1", "net-top", T("RL", "1"), [("to", Jn("JC1"))])
f.route("r-t2", "net-top", Jn("JC1"), [("to", T("CB", "2"))])
f.route("r-t3", "net-top", Jn("JC1"), [("to", Jn("JL1"))])
f.route("r-t4", "net-top", Jn("JL1"), [("to", T("L1", "2"))])
f.route("r-u1", "net-top2", T("RR", "1"), [("to", Jn("JC2"))])
f.route("r-u2", "net-top2", Jn("JC2"), [("to", T("CB", "1"))])
f.route("r-u3", "net-top2", Jn("JC2"), [("to", Jn("JL2"))])
f.route("r-u4", "net-top2", Jn("JL2"), [("to", T("L1", "1"))])

for side, R, JD, JO, L2, L2in, L2out, C2, C1, M, cx in (
        ("l", "RL", "JD1", "JO1", "L2L", "1", "2", "C2L", "C1L", "M1", 350),
        ("r", "RR", "JD2", "JO2", "L2R", "2", "1", "C2R", "C1R", "M2", 430)):
    f.route("r-%s-r" % side, "net-d%s" % side, T(R, "2"), [("to", Jn(JD))])
    f.route("r-%s-l2" % side, "net-d%s" % side, Jn(JD),
            [("to", T(L2, L2in))])
    f.route("r-%s-m" % side, "net-d%s" % side, Jn(JD), [("to", T(M, "D"))])
    f.route("r-%s-c1" % side, "net-d%s" % side, Jn(JD),
            [("bend", cx, 210), ("to", T(C1, "1"))])
    f.route("r-%s-o" % side, "net-d%s" % side, T(L2, L2out), [("to", Jn(JO))])
    f.route("r-%s-c2" % side, "net-d%s" % side, Jn(JO), [("to", T(C2, "1"))])
    f.route("r-%s-p" % side, "net-d%s" % side, Jn(JO), [("to", T("V" + (
        "OUTN" if side == "l" else "OUTP"), "P"))])

f.route("r-s1", "net-src", T("M1", "S"), [("to", Jn("JS"))])
f.route("r-s2", "net-src", T("M2", "S"), [("to", Jn("JS"))])
f.route("r-s3", "net-src", Jn("JS"), [("to", T("IIN", "+"))])
f.route("r-in1", "net-inp", T("VINP", "P"), [("to", T("M1", "G"))])
f.route("r-in2", "net-inn", T("VINN", "P"), [("to", T("M2", "G"))])
# every cap and the tail source sit pin-on-pin on their ground symbol

for tid, nm, net, ports in (("t-inp", "V_in+", "net-inp", ["VINP"]),
                            ("t-inn", "V_in-", "net-inn", ["VINN"]),
                            ("t-on", "V_out-", "net-dl", ["VOUTN"]),
                            ("t-op", "V_out+", "net-dr", ["VOUTP"])):
    f.terminal(tid, nm, net, "input" if "in" in tid else "output", ports)

f.inst_label("L1", 0, -14, "middle")
f.inst_label("RL", -13, 5, "end")
f.inst_label("RR", 13, 5, "start")
f.inst_label("L2L", 0, -14, "middle")
f.inst_label("L2R", 0, -14, "middle")
f.inst_label("C2L", -13, 5, "end")
f.inst_label("C2R", 13, 5, "start")
f.inst_label("C1L", -13, 5, "end")
f.inst_label("C1R", 13, 5, "start")
f.inst_label("IIN", -18, 5, "end")
f.port_label("VINP", "t-inp", -LABEL_PORT, 5, "end")
f.port_label("VINN", "t-inn", LABEL_PORT, 5, "start")
f.port_label("VOUTN", "t-on", -LABEL_PORT, 5, "end")
f.port_label("VOUTP", "t-op", LABEL_PORT, 5, "start")
f.text("v-cb", 390, 152, "middle", name_suffix("C_B", "/2"), owner="CB")

f.build(long_haul={"r-t3", "r-t4", "r-u3", "r-u4",
                   "r-l-m", "r-r-m", "r-l-c1", "r-r-c1",
                   "r-l-o", "r-r-o", "r-l-p", "r-r-p",
                   "r-s1", "r-s2",
                   "r-t2", "r-u2",      # the C_B/2 bridge
                   "r-l-l2", "r-r-l2"},  # drain node out to L_2
        extra_evidence=[],
        viewbox=(40, 65, 700, 330),
        # plain text on purpose (values / block titles): the
        # editor's generator italicises everything, we follow the
        # textbook page instead -- SOP 4
        expect_differ={"v-cb"})
