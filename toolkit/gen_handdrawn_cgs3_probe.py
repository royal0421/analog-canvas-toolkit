# -*- coding: utf-8 -*-
"""Impedance probe on a cascode node, with C_GS3 drawn in explicitly.
From a hand drawing (lane 3b).

⚠️ WIRING CORRECTED BY THE USER (2026-08-31).  My first reading had M_1's gate
and drain swapped.  The page actually says:

    M_1.D  -> the V_DD rail          (the long riser, NOT a gate wire)
    M_1.G  -> the probed node        (M_3's drain, where V_x drives)
    M_1.S  -> M_3's gate node        (with C_GS3's bottom plate and I_gm)

and M_1 is MIRRORED, so its gate plate faces right, toward the probe node.
Lesson for lane 3b: on a hand-drawn MOS, decide which stroke is the gate PLATE
and which is the channel BEFORE assigning pins -- a riser that lands on the
device does not have to be its gate.

Geometry, nets and the I_x marker are taken from the user's own export.
"""
import os
from icproj import Schematic, name, plain

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-handdrawn-cgs3-probe",
    "Cascode node impedance probe with C_GS3",
    "CgsProbe",
    out_proj=os.path.join(OUT, "Handdrawn_cascode-node_Cgs3-probe.icproj.json"),
    out_svg=os.path.join(HERE, "preview_cgs3probe.svg"),
    supply_net="net-top", rail_end="jvdd-end", supply_name="VDD",
    nmos_bulk_net="net-gnd")

# ---------------------------------------------------------------- placement
#   cols 120 the left leg | 150 C_GS3 | 200 M_1 drain/source, I_gm, its ground
#        210 M_1 | 250 M_3 | 260 M_3 drain and the probe node | 320 V_x
#   rows 100 the V_DD rail | 140 C_GS3 | 170 M_3 and its gate wire
#        210 M_1 drain | 230 M_1 and the probe node | 250 M_1 source
#        260 the source bus | 290 I_gm and V_x | 320 grounds
f.passive("CGS3", "capacitor", 150, 140, "C_GS3")
f.mos("M3", "pmos", 250, 170, "none", "M_3")
f.mos("M1", "nmos", 210, 230, "x", "M_1")      # mirrored: gate faces the probe
f.isrc("IGM", 200, 290, "I_gm")
f.place("VX", "voltage-source", 320, 290, extra={
    "schematicReference": "VX", "schematicName": name("V_x"),
    "netlist": {"binding": {"kind": "primitive",
                            "deviceClass": "voltage-source"},
                "parameters": {}, "reference": "VX"}})
f.gnd("GI", 200, 320)
f.gnd("GX", 320, 320)

# ---------------------------------------------------------------- junctions
# The page draws the top line thick and running PAST both end taps: that is a
# power rail (SOP §7), and a rail never carries a junction dot.
RAIL = [130, 150, 200, 260, 280]
for jid, net, x, y in (("jvdd-start", "net-top", 130, 100),
                       ("JT", "net-top", 150, 100),     # C_GS3 tap
                       ("JT2", "net-top", 200, 100),    # M_1 drain riser
                       ("JT3", "net-top", 260, 100),    # M_3 source
                       ("jvdd-end", "net-top", 280, 100),
                       ("JG", "net-g3", 150, 170),      # C_GS3 onto M_3's gate
                       ("JS", "net-g3", 120, 260),      # the long left leg
                       ("JS2", "net-g3", 200, 260),     # down to M_1's source
                       ("JX", "net-x", 260, 230)):      # the probed node
    f.junction(jid, net, x, y)

# -------------------------------------------------------------------- nets
f.net("net-top", [("CGS3", "1"), ("M3", "S"), ("M1", "D"), ("M3", "B")])
f.net("net-g3", [("CGS3", "2"), ("M3", "G"), ("M1", "S"), ("IGM", "+")])
f.net("net-x", [("M3", "D"), ("M1", "G"), ("VX", "+")])
f.net("net-gnd", [("IGM", "-"), ("GI", "0"), ("VX", "-"), ("GX", "0"),
                  ("M1", "B")])

# ------------------------------------------------------------------ routes
T, Jn = f.term, f.jn
f.rail("net-top", 100, RAIL, prefix="r-vdd-rail")
f.route("r-t-c", "net-top", Jn("JT"), [("to", T("CGS3", "1"))])
f.route("r-t-m3", "net-top", Jn("JT3"), [("to", T("M3", "S"))])
f.route("r-t-m1d", "net-top", Jn("JT2"), [("to", T("M1", "D"))])

f.route("r-g-c", "net-g3", T("CGS3", "2"), [("to", Jn("JG"))])
f.route("r-g-m3", "net-g3", Jn("JG"), [("to", T("M3", "G"))])
f.route("r-g-down", "net-g3", Jn("JG"),
        [("bend", 120, 170), ("to", Jn("JS"))])
f.route("r-g-bus", "net-g3", Jn("JS"), [("to", Jn("JS2"))])
f.route("r-g-m1s", "net-g3", T("M1", "S"), [("to", Jn("JS2"))])
f.route("r-g-igm", "net-g3", Jn("JS2"), [("to", T("IGM", "+"))])

f.route("r-x-m3", "net-x", T("M3", "D"), [("to", Jn("JX"))])
f.route("r-x-m1g", "net-x", Jn("JX"), [("to", T("M1", "G"))])
f.route("r-x-vx", "net-x", Jn("JX"), [("bend", 320, 230), ("to", T("VX", "+"))])
# I_gm and V_x sit pin-on-pin on their ground symbols, so neither needs a wire

# ------------------------------------------------------------- annotations
f.inst_label("CGS3", -16, 5, "end")
f.inst_label("M3", 18, 5, "start")
f.inst_label("M1", -20, 5, "end")
f.inst_label("VX", 16, 5, "start")
f.power_label("label-vdd", "net-top", "jvdd-end", 12, 6, "V_DD")
# I_x rides the V_x lead -- the test current, taken BEFORE it splits between
# M_3 and M_1.  (The user marks it with the editor's own route-marker at
# t=0.5, normalOffset -14; a drafting arrow on the same leg draws the same.)
f.arrow("arrow-ix", 316, 230, 266, 230)
f.text("n-ix", 290, 216, "middle", name("I_x"))
# 1/g_m5 points at the source below M_1
f.arrow("arrow-gm", 229, 315, 229, 255)
f.text("n-gm", 278, 309, "end",
       {"runs": plain("1/")["runs"] + name("g_m5")["runs"]})

f.build(long_haul={"r-vdd-rail-1",   # 50: rail on to the M_1 riser
                   "r-vdd-rail-2",   # 60: and on to M_3's source
                   "r-t-m3",         # 50: down to M_3's source
                   "r-t-m1d",        # 110: the M_1 drain riser
                   "r-g-m3",         # 80: the gate wire across to M_3
                   "r-g-down",       # 30+90: the long left leg
                   "r-g-bus",        # 80: and back across under M_1
                   "r-x-vx"},        # 60+40: V_x's lead, carrying I_x
        rail_ends={"jvdd-start", "jvdd-end"},
        viewbox=(60, 40, 320, 330),
        # plain on purpose: "1/" is arithmetic, not a device name
        expect_differ=set())
