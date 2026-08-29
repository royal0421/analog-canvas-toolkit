# -*- coding: utf-8 -*-
"""Lab 2 SR latch: two cross-coupled NOR gates.  Source: Lab2 slides p.5.
The X is drawn with construction lines (SOP 3E rule 1)."""
import os
from icproj import Schematic, name, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic("project-lab2-srlatch", "Lab 2 SR latch (cross-coupled NOR)",
              "SRLatch",
              out_proj=os.path.join(OUT, "Lab2_SR-latch_NOR.icproj.json"),
              out_svg=os.path.join(HERE, "preview_srlatch.svg"))

for iid, cx, cy in (("G1", 250, 180), ("G2", 250, 260)):
    f.place(iid, "nor-gate", cx, cy,
            extra={"schematicReference": iid,
                   "schematicName": name(iid[0] + "_" + iid[1:])})
f.port("R", 190, 170)
f.port("S", 190, 270)
f.port("Q", 320, 180, mirror="x")
f.port("QB", 320, 260, mirror="x")

for jid, net, x, y in (("JQ", "net-q", 290, 180),
                       ("JQ2", "net-q", 290, 210),
                       ("JQB", "net-qb", 290, 260),
                       ("JQB2", "net-qb", 290, 230),
                       ("JF1", "net-f1", 210, 210),
                       ("JF2", "net-f2", 210, 230)):
    f.junction(jid, net, x, y)

f.net("net-r", [("R", "P"), ("G1", "A")])
f.net("net-s", [("S", "P"), ("G2", "B")])
f.net("net-q", [("G1", "Y"), ("Q", "P")])
f.net("net-qb", [("G2", "Y"), ("QB", "P")])
f.net("net-f1", [("G1", "B")])
f.net("net-f2", [("G2", "A")])

T, Jn = f.term, f.jn
f.route("r-r", "net-r", T("R", "P"), [("to", T("G1", "A"))])
f.route("r-s", "net-s", T("S", "P"), [("to", T("G2", "B"))])
f.route("r-q1", "net-q", T("G1", "Y"), [("to", Jn("JQ"))])
f.route("r-q2", "net-q", Jn("JQ"), [("to", T("Q", "P"))])
f.route("r-q3", "net-q", Jn("JQ"), [("to", Jn("JQ2"))])
f.route("r-qb1", "net-qb", T("G2", "Y"), [("to", Jn("JQB"))])
f.route("r-qb2", "net-qb", Jn("JQB"), [("to", T("QB", "P"))])
f.route("r-qb3", "net-qb", Jn("JQB"), [("to", Jn("JQB2"))])
f.route("r-f1", "net-f1", T("G1", "B"), [("bend", 210, 190), ("to", Jn("JF1"))])
f.route("r-f2", "net-f2", T("G2", "A"), [("bend", 210, 250), ("to", Jn("JF2"))])
# the X: G1's second input takes Q-bar, G2's takes Q
f.construction("xc-1", 210, 210, 290, 230)
f.construction("xc-2", 210, 230, 290, 210)

f.terminal("t-r", "R", "net-r", "input", ["R"])
f.terminal("t-s", "S", "net-s", "input", ["S"])
f.terminal("t-q", "Q", "net-q", "output", ["Q"])
f.terminal("t-qb", "Q_bar", "net-qb", "output", ["QB"])

f.port_label("R", "t-r", -LABEL_PORT, 5, "end")
f.port_label("S", "t-s", -LABEL_PORT, 5, "end")
f.port_label("Q", "t-q", LABEL_PORT, 5, "start")
f.port_label("QB", "t-qb", LABEL_PORT, 5, "start")

f.build(long_haul={}, extra_evidence=[],
        rail_ends={"JQ2", "JQB2", "JF1", "JF2"},
        viewbox=(140, 140, 250, 160))
