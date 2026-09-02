# -*- coding: utf-8 -*-
"""ESD power clamp: R + 3 stacked diodes set V_A/V_B, M_P/M_N and D_O drive
V_TRIG into the P+ of the P-well, next to the device cross-section the paper
draws beside the schematic.

The cross-section (P+/N-WELL/P-WELL/N+) is not a circuit: it is drafting
rectangles plus text, wired to V_TRIG, V_DD and V_SS at three junctions that
only one route touches (hence the rail_ends exemption).
"""
import os
from icproj import Schematic, name, plain

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic("project-esd-rc-clamp", "ESD power clamp with SCR trigger",
              "ESDClamp",
              out_proj=os.path.join(OUT, "ESD_RC-clamp_SCR-trigger.icproj.json"),
              out_svg=os.path.join(HERE, "preview_esdclamp.svg"),
              supply_net="net-vdd", nmos_bulk_net="net-vss",
              rail_end="jvdd-end", supply_name="VDD")

f.passive("R", "resistor", 140, 140, "R")
for iid, cy in (("DS1", 210), ("DS2", 260), ("DS3", 330)):
    f.place(iid, "diode", 140, cy, rotation=90,
            extra={"schematicReference": iid, "schematicName": name("D_S"),
                   "netlist": {"binding": {"kind": "primitive",
                                           "deviceClass": "diode"},
                               "parameters": {}, "reference": iid}})
f.mos("MP", "pmos", 270, 150, "none", "M_P")
f.mos("MN", "nmos", 270, 300, "none", "M_N")
f.place("DO", "diode", 280, 220, rotation=90,
        extra={"schematicReference": "DO", "schematicName": name("D_O"),
               "netlist": {"binding": {"kind": "primitive",
                                       "deviceClass": "diode"},
                           "parameters": {}, "reference": "DO"}})

RAIL_V, RAIL_S = [120, 140, 280, 460, 560], [120, 140, 280, 460, 560]
J = [("jvdd-%d" % i, "net-vdd", x, 100) for i, x in enumerate(RAIL_V)]
J[0] = ("jvdd-start", "net-vdd", RAIL_V[0], 100)
J[-1] = ("jvdd-end", "net-vdd", RAIL_V[-1], 100)
JS = [("jvss-%d" % i, "net-vss", x, 360) for i, x in enumerate(RAIL_S)]
JS[0] = ("jvss-start", "net-vss", RAIL_S[0], 360)
JS[-1] = ("jvss-end", "net-vss", RAIL_S[-1], 360)
for jid, net, x, y in J + JS + [("JA", "net-a", 140, 180),
                                ("JB", "net-b", 140, 300),
                                ("JD", "net-vd", 280, 190),
                                ("JT", "net-trig", 280, 260),
                                ("JW", "net-trig", 380, 260),
                                # the P+ at the top of the cross-section
                                # ties to V_DD, as the paper draws it
                                ("JPP", "net-vdd", 460, 120),
                                # the N+ at the bottom ties to V_SS
                                ("JNP", "net-vss", 460, 340)]:
    f.junction(jid, net, x, y)

f.net("net-vdd", [("R", "1"), ("MP", "S"), ("MP", "B")])
f.net("net-a", [("R", "2"), ("DS1", "A"), ("MP", "G")])
f.net("net-s12", [("DS1", "K"), ("DS2", "A")])
f.net("net-b", [("DS2", "K"), ("DS3", "A"), ("MN", "G")])
f.net("net-vss", [("DS3", "K"), ("MN", "S"), ("MN", "B")])
f.net("net-vd", [("MP", "D"), ("DO", "A")])
f.net("net-trig", [("DO", "K"), ("MN", "D")])

T, Jn = f.term, f.jn
f.rail("net-vdd", 100, RAIL_V)
f.rail("net-vss", 360, RAIL_S, prefix="r-vss-rail")
f.route("r-v-r", "net-vdd", Jn(f._jat(140, 100)), [("to", T("R", "1"))])
f.route("r-v-mp", "net-vdd", Jn(f._jat(280, 100)), [("to", T("MP", "S"))])
f.route("r-v-pp", "net-vdd", Jn(f._jat(460, 100)), [("to", Jn("JPP"))])
f.route("r-s-np", "net-vss", Jn("JNP"), [("to", Jn(f._jat(460, 360)))])
f.route("r-s-d3", "net-vss", T("DS3", "K"), [("to", Jn(f._jat(140, 360)))])
f.route("r-s-mn", "net-vss", T("MN", "S"), [("to", Jn(f._jat(280, 360)))])

f.route("r-a1", "net-a", T("R", "2"), [("to", Jn("JA"))])
f.route("r-a2", "net-a", Jn("JA"), [("to", T("DS1", "A"))])
f.route("r-a3", "net-a", Jn("JA"), [("bend", 200, 180), ("bend", 200, 150),
                                    ("to", T("MP", "G"))])
f.route("r-s12", "net-s12", T("DS1", "K"), [("to", T("DS2", "A"))])
f.route("r-b1", "net-b", T("DS2", "K"), [("to", Jn("JB"))])
f.route("r-b2", "net-b", Jn("JB"), [("to", T("DS3", "A"))])
f.route("r-b3", "net-b", Jn("JB"), [("to", T("MN", "G"))])
f.route("r-d1", "net-vd", T("MP", "D"), [("to", Jn("JD"))])
f.route("r-d2", "net-vd", Jn("JD"), [("to", T("DO", "A"))])
f.route("r-t1", "net-trig", T("DO", "K"), [("to", Jn("JT"))])
f.route("r-t2", "net-trig", Jn("JT"), [("to", T("MN", "D"))])
f.route("r-t3", "net-trig", Jn("JT"), [("to", Jn("JW"))])

# ---- the device cross-section drawn beside the schematic -------------------
for rid, cx, cy, w, h in (("x-pplus", 460, 140, 160, 40),
                          ("x-nwell", 460, 190, 160, 60),
                          ("x-pwell", 460, 260, 160, 80),
                          ("x-nplus", 460, 320, 160, 40),
                          ("x-tap", 400, 260, 40, 32)):
    f.rect(rid, cx, cy, w, h)
for tid, cx, cy, s in (("t-pp", 460, 145, "P+"),
                       ("t-nw", 460, 195, "N-WELL"),
                       ("t-pw", 480, 265, "P-WELL"),
                       ("t-np", 460, 325, "N+"),
                       ("t-tap", 400, 265, "P+")):
    f.text(tid, cx, cy, "middle", plain(s))

f.power_label("label-vdd", "net-vdd", "jvdd-end", 12, 6, "V_DD")
f.power_label("label-vss", "net-vss", "jvss-end", 12, 6, "V_SS")
f.inst_label("R", -13, 5, "end")
for iid in ("DS1", "DS2", "DS3"):
    f.inst_label(iid, -18, 5, "end")
f.inst_label("MP", 18, 5, "start")
f.inst_label("MN", 18, 5, "start")
f.inst_label("DO", -18, 5, "end")
f.text("n-va", 125, 185, "end", "V_A")
f.text("n-vb", 155, 285, "start", "V_B")
f.text("n-vd", 295, 195, "start", "V_D")
f.text("n-vt", 295, 245, "start", "V_TRIG")

f.build(long_haul={"r-vdd-rail-1", "r-vdd-rail-2", "r-vdd-rail-3",
                   "r-vss-rail-1", "r-vss-rail-2", "r-vss-rail-3",
                   "r-a3", "r-b3", "r-t3", "r-s-d3", "r-s-mn"},
        extra_evidence=[
            {"id": "cev-vdd-m", "kind": "name-claim", "netId": "net-vdd",
             "name": "VDD", "owner": {"kind": "power-marker",
                                      "objectId": "jvdd-end"},
             "scope": "global", "powerDomain": "vdd"},
            # powerDomain MUST be "vdd", not "ground": the site's renderer
            # picks the thick powerRail stroke with
            #   presentation === "power-rail" && powerDomain === "vdd"
            # (bundle dist-CE3Pi34B.js), so a "ground" rail draws hairline.
            # The name stays VSS, so the label and the netlist are unaffected.
            {"id": "cev-vss-m", "kind": "name-claim", "netId": "net-vss",
             "name": "VSS", "owner": {"kind": "power-marker",
                                      "objectId": "jvss-end"},
             "scope": "global", "powerDomain": "vdd"}],
        rail_ends={"jvdd-start", "jvdd-end", "jvss-start", "jvss-end",
                   "JW", "JPP", "JNP"},
        viewbox=(85, 85, 520, 305),
        # plain text on purpose (values / block titles): the
        # editor's generator italicises everything, we follow the
        # textbook page instead -- SOP 4
        expect_differ=set())
