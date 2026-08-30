# -*- coding: utf-8 -*-
"""Lab 2 NAND2, transistor level: M_P1 || M_P2 pull-up, M_N1 + M_N2 pull-down.

House style for logic gates (user's correction, 2026-08-30): a signal driving
several gates gets ITS OWN PORT AT EACH GATE, pin-on-pin with the gate pin so
there is no wire at all -- not one port with long risers.  That is how the
source figure prints it, and it keeps the drawing narrow.
"""
import os
from icproj import Schematic, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic("project-lab2-nand2", "Lab 2 NAND2 (transistor level)", "NAND2",
              out_proj=os.path.join(OUT, "Lab2_NAND2_transistor-level.icproj.json"),
              out_svg=os.path.join(HERE, "preview_nand2.svg"))

for iid, kind, cx, cy, lab in (("MP1", "pmos", 170, 140, "M_P1"),
                               ("MP2", "pmos", 290, 140, "M_P2"),
                               ("MN1", "nmos", 230, 210, "M_N1"),
                               ("MN2", "nmos", 230, 270, "M_N2")):
    f.mos(iid, kind, cx, cy, "none", lab)
f.gnd("GND", 240, 320)
for iid, x, y in (("A1", 140, 140), ("A2", 200, 210),
                  ("B1", 260, 140), ("B2", 200, 270)):
    f.port(iid, x, y)               # pin lands exactly on the gate pin
f.port("OUT", 330, 170, mirror="x")

RAIL = [160, 180, 300, 320]
J = [("jvdd-%d" % i, "net-power-vdd", x, 100) for i, x in enumerate(RAIL)]
J[0] = ("jvdd-start", "net-power-vdd", RAIL[0], 100)
J[-1] = ("jvdd-end", "net-power-vdd", RAIL[-1], 100)
# the output run is one straight line at y=170; the two devices that
# tee into it each get a junction, or no dot is drawn (SOP 3H).
for jid, net, x, y in J + [("JMN", "net-out", 240, 170),
                           ("JMP2", "net-out", 300, 170)]:
    f.junction(jid, net, x, y)

f.net("net-power-vdd", [("MP1", "S"), ("MP2", "S"), ("MP1", "B"), ("MP2", "B")])
f.net("net-out", [("MP1", "D"), ("MP2", "D"), ("MN1", "D"), ("OUT", "P")])
f.net("net-a", [("A1", "P"), ("MP1", "G"), ("A2", "P"), ("MN1", "G")])
f.net("net-b", [("B1", "P"), ("MP2", "G"), ("B2", "P"), ("MN2", "G")])
f.net("net-mid", [("MN1", "S"), ("MN2", "D")])
f.net("net-gnd-1", [("MN2", "S"), ("GND", "0"), ("MN1", "B"), ("MN2", "B")])

T, Jn = f.term, f.jn
f.rail("net-power-vdd", 100, RAIL)
f.route("r-v1", "net-power-vdd", Jn(f._jat(180, 100)), [("to", T("MP1", "S"))])
f.route("r-v2", "net-power-vdd", Jn(f._jat(300, 100)), [("to", T("MP2", "S"))])
f.route("r-o1", "net-out", T("MP1", "D"), [("bend", 180, 170),
                                           ("to", Jn("JMN"))])
f.route("r-o2", "net-out", Jn("JMN"), [("to", T("MN1", "D"))])
f.route("r-o3", "net-out", Jn("JMN"), [("to", Jn("JMP2"))])
f.route("r-o4", "net-out", Jn("JMP2"), [("to", T("MP2", "D"))])
f.route("r-o5", "net-out", Jn("JMP2"), [("to", T("OUT", "P"))])
f.route("r-mid", "net-mid", T("MN1", "S"), [("to", T("MN2", "D"))])
f.route("r-g", "net-gnd-1", T("MN2", "S"), [("to", T("GND", "0"))])
# A1/A2 and B1/B2 sit pin-on-pin on their gates: no routes needed.

for tid, nm, net, ports in (("t-a1", "A", "net-a", ["A1"]),
                            ("t-a2", "A", "net-a", ["A2"]),
                            ("t-b1", "B", "net-b", ["B1"]),
                            ("t-b2", "B", "net-b", ["B2"])):
    f.terminal(tid, nm, net, "input", ports)
f.terminal("t-out", "Out", "net-out", "output", ["OUT"])

for iid in ("MP1", "MP2", "MN1", "MN2"):
    f.inst_label(iid, 18, 5, "start")
for iid, tid in (("A1", "t-a1"), ("A2", "t-a2"),
                 ("B1", "t-b1"), ("B2", "t-b2")):
    f.port_label(iid, tid, -LABEL_PORT, 5, "end")
f.port_label("OUT", "t-out", LABEL_PORT, 5, "start")
f.power_label("label-vdd", "net-power-vdd", "jvdd-end", 12, 6, "V_DD")

f.build(long_haul={"r-vdd-rail-1", "r-o1", "r-o3"},
        rail_ends={"jvdd-start", "jvdd-end"}, viewbox=(105, 85, 300, 265),
        # the editor's builder subscripts a trailing capital run
        # (IN -> I_N, CK -> C_K, Out -> O_ut); our formatOverride
        # keeps them plain, so they DIFFER on purpose -- SOP 4
        expect_differ={"instance-label-OUT"})
