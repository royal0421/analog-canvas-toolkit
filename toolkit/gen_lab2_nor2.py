# -*- coding: utf-8 -*-
"""Lab 2 NOR2, transistor level: M_P1 + M_P2 in series pull-up, M_N1 || M_N2
pull-down.  Same house style as the NAND2: one port per gate, pin-on-pin."""
import os
from icproj import Schematic, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic("project-lab2-nor2", "Lab 2 NOR2 (transistor level)", "NOR2",
              out_proj=os.path.join(OUT, "Lab2_NOR2_transistor-level.icproj.json"),
              out_svg=os.path.join(HERE, "preview_nor2.svg"))

for iid, kind, cx, cy, lab in (("MP1", "pmos", 240, 160, "M_P1"),
                               ("MP2", "pmos", 240, 210, "M_P2"),
                               ("MN1", "nmos", 180, 290, "M_N1"),
                               ("MN2", "nmos", 300, 290, "M_N2")):
    f.mos(iid, kind, cx, cy, "none", lab)
f.gnd("GND", 250, 350)
for iid, x, y in (("A1", 210, 160), ("A2", 150, 290),
                  ("B1", 210, 210), ("B2", 270, 290)):
    f.port(iid, x, y)
f.port("OUT", 330, 250, mirror="x")

RAIL = [190, 250, 310]
J = [("jvdd-%d" % i, "net-power-vdd", x, 120) for i, x in enumerate(RAIL)]
J[0] = ("jvdd-start", "net-power-vdd", RAIL[0], 120)
J[-1] = ("jvdd-end", "net-power-vdd", RAIL[-1], 120)
# same as NAND2: M_N2 tees into the output run, so it needs its own
# junction or the dot is missing (SOP 3H).
for jid, net, x, y in J + [("JO", "net-out", 250, 250),
                           ("JMN2", "net-out", 310, 250)]:
    f.junction(jid, net, x, y)

f.net("net-power-vdd", [("MP1", "S"), ("MP1", "B"), ("MP2", "B")])
f.net("net-mid", [("MP1", "D"), ("MP2", "S")])
f.net("net-out", [("MP2", "D"), ("MN1", "D"), ("MN2", "D"), ("OUT", "P")])
f.net("net-a", [("A1", "P"), ("MP1", "G"), ("A2", "P"), ("MN1", "G")])
f.net("net-b", [("B1", "P"), ("MP2", "G"), ("B2", "P"), ("MN2", "G")])
f.net("net-gnd-1", [("MN1", "S"), ("MN2", "S"), ("GND", "0"),
                    ("MN1", "B"), ("MN2", "B")])

T, Jn = f.term, f.jn
f.rail("net-power-vdd", 120, RAIL)
f.route("r-v1", "net-power-vdd", Jn(f._jat(250, 120)), [("to", T("MP1", "S"))])
f.route("r-mid", "net-mid", T("MP1", "D"), [("to", T("MP2", "S"))])
f.route("r-o1", "net-out", T("MP2", "D"), [("to", Jn("JO"))])
f.route("r-o2", "net-out", Jn("JO"), [("bend", 190, 250), ("to", T("MN1", "D"))])
f.route("r-o3", "net-out", Jn("JO"), [("to", Jn("JMN2"))])
f.route("r-o4", "net-out", Jn("JMN2"), [("to", T("MN2", "D"))])
f.route("r-o5", "net-out", Jn("JMN2"), [("to", T("OUT", "P"))])
f.route("r-g1", "net-gnd-1", T("MN1", "S"), [("bend", 190, 340),
                                             ("to", T("GND", "0"))])
f.route("r-g2", "net-gnd-1", T("MN2", "S"), [("bend", 310, 340),
                                             ("to", T("GND", "0"))])

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

f.build(long_haul={"r-vdd-rail-0", "r-vdd-rail-1", "r-o2", "r-o3", "r-o4",
                   "r-g1", "r-g2"},
        rail_ends={"jvdd-start", "jvdd-end"}, viewbox=(110, 105, 290, 275),
        # the editor's builder subscripts a trailing capital run
        # (IN -> I_N, CK -> C_K, Out -> O_ut); our formatOverride
        # keeps them plain, so they DIFFER on purpose -- SOP 4
        expect_differ={"instance-label-OUT"})
