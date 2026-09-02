# -*- coding: utf-8 -*-
"""Razavi Fig. 9.34: a pnp current mirror fed by an npn mirror.

I_REF sets Q_REF1; Q_M copies it up into the diode-connected pnp Q_REF2,
which mirrors into Q_2; Q_1 takes v_in on its base and shares the output node
with Q_2.

2026-09-01: ported from its own hand-written skeleton onto the shared engine.
The coordinates are unchanged; what the port fixes is that the old copy had
drifted -- it still wrote schema v31, its own `explicit-net-property`
evidence, and `sizeScale 0.65` (the label size was settled at 0.58 back on
2026-08-29, so this figure had been printing bigger text than the other 28).
"""
import os
from icproj import Schematic, name

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-razavi-fig-9-34",
    "Razavi Fig. 9.34 — pnp current mirror driven by an npn mirror",
    "Fig_9_34",
    out_proj=os.path.join(OUT, "Razavi_Fig_9_34_pnp-current-mirror.icproj.json"),
    out_svg=os.path.join(HERE, "preview_fig934.svg"),
    supply_net="net-power-vcc", rail_end="jvcc-end", supply_name="VCC")

# ---------------------------------------------------------------- placement
#   columns 170 reference leg | 300 Q_M | 370 Q_REF2 | 500 Q_2 / Q_1
#   rows    100 V_CC rail | 140 I_REF | 150 pnp pair | 200 node rows
#           250 npn row | 300 grounds
f.isrc("IREF", 170, 140, "I_REF")
f.bjt("QREF1", "npn", 170, 250, "x", "Q_REF1")
f.gnd("GND1", 170, 300)
f.bjt("QM", "npn", 300, 250, "none", "Q_M")
f.gnd("GND2", 300, 300)
f.bjt("QREF2", "pnp", 370, 150, "x", "Q_REF2")
f.bjt("Q2", "pnp", 500, 150, "none", "Q_2")
f.bjt("Q1", "npn", 500, 250, "none", "Q_1")
f.gnd("GND3", 500, 300)
f.port("VOUT", 540, 200, mirror="x")
f.port("VIN", 440, 250)          # STUB_PORT floor: the BJT base lead is
                                 # already 23 units, so 10 is right here

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("jvcc-start", "net-power-vcc", 150, 100),
        ("JV_A", "net-power-vcc", 170, 100),
        ("JV_B", "net-power-vcc", 370, 100),
        ("JV_C", "net-power-vcc", 500, 100),
        ("jvcc-end", "net-power-vcc", 520, 100),
        ("JREF", "net-ref1", 170, 200),
        ("JB1", "net-ref1", 230, 250),
        ("JC2", "net-cm", 370, 200),
        ("JB2", "net-cm", 430, 150),
        ("JOUT", "net-out", 500, 200)):
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
f.net("net-power-vcc", [("IREF", "+"), ("QREF2", "E"), ("Q2", "E")])
f.net("net-ref1", [("IREF", "-"), ("QREF1", "C"), ("QREF1", "B"),
                   ("QM", "B")])
f.net("net-cm", [("QM", "C"), ("QREF2", "C"), ("QREF2", "B"), ("Q2", "B")])
f.net("net-out", [("Q2", "C"), ("Q1", "C"), ("VOUT", "P")])
f.net("net-in", [("Q1", "B"), ("VIN", "P")])
f.net("net-gnd-1", [("GND1", "0"), ("QREF1", "E")])
f.net("net-gnd-2", [("GND2", "0"), ("QM", "E")])
f.net("net-gnd-3", [("GND3", "0"), ("Q1", "E")])

# ---------------------------------------------------------------- routes
T, J = f.term, f.jn
f.rail("net-power-vcc", 100, [150, 170, 370, 500, 520], prefix="r-vcc-rail")
f.route("r-vcc-drop-iref", "net-power-vcc", J("JV_A"), [("to", T("IREF", "+"))])
f.route("r-vcc-drop-qref2", "net-power-vcc", J("JV_B"),
        [("to", T("QREF2", "E"))])
f.route("r-vcc-drop-q2", "net-power-vcc", J("JV_C"), [("to", T("Q2", "E"))])

f.route("r-ref-1", "net-ref1", T("IREF", "-"), [("to", J("JREF"))])
f.route("r-ref-2", "net-ref1", J("JREF"), [("to", T("QREF1", "C"))])
f.route("r-ref-3", "net-ref1", J("JREF"), [("bend", 230, 200),
                                           ("to", J("JB1"))])
f.route("r-ref-4", "net-ref1", J("JB1"), [("to", T("QREF1", "B"))])
f.route("r-ref-5", "net-ref1", J("JB1"), [("to", T("QM", "B"))])

f.route("r-cm-1", "net-cm", T("QM", "C"), [("bend", 300, 200),
                                           ("to", J("JC2"))])
f.route("r-cm-2", "net-cm", J("JC2"), [("to", T("QREF2", "C"))])
f.route("r-cm-3", "net-cm", J("JC2"), [("bend", 430, 200), ("to", J("JB2"))])
f.route("r-cm-4", "net-cm", J("JB2"), [("to", T("QREF2", "B"))])
f.route("r-cm-5", "net-cm", J("JB2"), [("to", T("Q2", "B"))])

f.route("r-out-1", "net-out", T("Q2", "C"), [("to", J("JOUT"))])
f.route("r-out-2", "net-out", J("JOUT"), [("to", T("Q1", "C"))])
f.route("r-out-3", "net-out", J("JOUT"), [("to", T("VOUT", "P"))])
f.route("r-in-1", "net-in", T("Q1", "B"), [("to", T("VIN", "P"))])
f.route("r-g1", "net-gnd-1", T("QREF1", "E"), [("to", T("GND1", "0"))])
f.route("r-g2", "net-gnd-2", T("QM", "E"), [("to", T("GND2", "0"))])
f.route("r-g3", "net-gnd-3", T("Q1", "E"), [("to", T("GND3", "0"))])

# ------------------------------------------------- cell terminals for ports
# Razavi's small-signal notation keeps the v lowercase, so the names are
# `v_out` / `v_in` and not `V_out` / `V_in`.
f.terminal("terminal-vout", "v_out", "net-out", "output", ["VOUT"])
f.terminal("terminal-vin", "v_in", "net-in", "input", ["VIN"])

# ---------------------------------------------------------------- annotations
# The label gap is measured from the DRAWN INK.  A MOS stops at centre +/-10.6
# so its label sits at +/-18; a BJT's C/E column IS the instance centre, so
# the same 8-unit gap lands at +/-8.
f.inst_label("IREF", -18, 5, "end")
f.inst_label("QREF1", -8, 5, "end")
f.inst_label("QM", 8, 5, "start")
f.inst_label("QREF2", -8, 5, "end")
f.inst_label("Q2", 8, 5, "start")
f.inst_label("Q1", 8, 5, "start")
f.port_label("VOUT", "terminal-vout", 11, 5, "start")
f.port_label("VIN", "terminal-vin", -11, 5, "end")
f.power_label("label-vcc", "net-power-vcc", "jvcc-end", 12, 6, "V_CC")

# ---------------------------------------------------------------- drafting
# I_C,M sits on the VERTICAL collector lead pointing the way the current
# flows (down, into Q_M's collector), with its label to the left at the same
# height -- drafting geometry, not a route-marker (SOP §6B).
f.arrow("arrow-icm", 300, 200, 300, 220)
f.text("note-icm", 287, 224, "end", name("I_C,M"), owner="QM")
# X_1 / X_2 are the device-count annotations Razavi prints beside each leg
# right-aligned so the text leans back toward its own leg: at
# "start" it reached toward Q_M and the ambiguity audit called it
f.text("note-x1", 224, 284, "end", name("X_1"), owner="QREF1")
f.text("note-x2", 436, 190, "start", name("X_2"), owner="Q2")

f.build(long_haul={"r-vcc-rail-0", "r-vcc-rail-1", "r-vcc-rail-2",
                   "r-vcc-rail-3",   # the V_CC rail itself
                   "r-ref-3",        # 60+50: reference node across to Q_M
                   "r-cm-1",         # 50: Q_M collector up to the pnp node
                   "r-cm-3"},        # 60+50: pnp node across to Q_2's base
        rail_ends={"jvcc-start", "jvcc-end"},
        viewbox=(120, 75, 470, 260))
