# -*- coding: utf-8 -*-
"""Impedance probe on a cascode node: V_x / I_x drive the M_3 / M_5 drain node,
with C_GS3 drawn in explicitly between M_3's source and its gate, and M_3's
gate tied down to M_5's source.  From a hand drawing (lane 3b).

Read off the page with 2.4x crops (SOP 3I-b):
  * the top rail carries C_GS3's top plate, M_3's SOURCE and M_5's GATE;
  * C_GS3's bottom plate, M_3's GATE and M_5's SOURCE are one node -- the long
    left-hand wire is what ties them together;
  * M_3's drain doglegs right and down onto M_5's drain, which is the node the
    V_x source drives and I_x flows into;
  * the 1/g_m5 current source hangs from M_5's source down to ground.
Arrow positions decide the symbol: M_3's arrow is on its TOP terminal (so the
`pmos` symbol reproduces the page), M_5's is on its BOTTOM one (`nmos`).

The page uses red pen for the analysis annotations (C_GS3, 1/g_m5).  That is
NOT reproduced: the site colours instances and arrows but silently ignores the
colour on ordinary drafting TEXT, and a red part with a black name looks
half-finished (user, 2026-08-30).  Everything is black.
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
#   cols 100 the left wire (M_3 gate down to M_5 source) | 150 C_GS3
#        190 the M_5 gate riser | 210 M_5 | 250 M_3 | 300 the X bus corner
#        320 V_x                                   (pitch 60/10/30/70)
#   rows 100 top rail | 140 C_GS3 | 170 M_3 and its gate wire | 250 the X bus
#        270 M_5 | 330 the M_5 source bus | 300 V_x | 370 I_gm | 350/400 grounds
f.passive("CGS3", "capacitor", 150, 140, "C_GS3")
f.mos("M3", "pmos", 250, 170, "none", "M_3")
f.mos("M5", "nmos", 210, 270, "none", "M_5")
f.isrc("IGM", 220, 330, "I_gm")
f.place("VX", "voltage-source", 330, 300, extra={
    "schematicReference": "VX", "schematicName": name("V_x"),
    "netlist": {"binding": {"kind": "primitive",
                            "deviceClass": "voltage-source"},
                "parameters": {}, "reference": "VX"}})
f.gnd("GI", 220, 360)
# The page draws the top line thick and running PAST both end taps: that is
# a power rail, not a vdd-port (user, 2026-08-30; SOP 7 already said "if
# there is a rail, do not use vdd-port" -- I used one anyway).
f.gnd("GX", 330, 330)

# ---------------------------------------------------------------- junctions
RAIL = [130, 150, 190, 260, 280]      # 20 of overhang past each end tap
for jid, net, x, y in (("jvdd-start", "net-top", 130, 100),
                       ("JT", "net-top", 150, 100),   # rail: C_GS3 tap
                       ("JT2", "net-top", 190, 100),  # rail: M_5 gate riser
                       ("JT3", "net-top", 260, 100),  # rail: M_3 source
                       ("jvdd-end", "net-top", 280, 100),
                       ("JG", "net-g3", 150, 170),    # C_GS3 down onto the
                       ("JS", "net-g3", 100, 300),    # M_3 gate wire, and that
                       ("JS2", "net-g3", 220, 300),   # wire down to M_5 src
                       ("JX", "net-x", 270, 250)):    # wire down to M_5's src
    f.junction(jid, net, x, y)

# -------------------------------------------------------------------- nets
f.net("net-top", [("CGS3", "1"), ("M3", "S"), ("M5", "G"), ("M3", "B")])
f.net("net-g3", [("CGS3", "2"), ("M3", "G"), ("M5", "S"), ("IGM", "+")])
f.net("net-x", [("M3", "D"), ("M5", "D"), ("VX", "+")])
f.net("net-gnd", [("IGM", "-"), ("GI", "0"), ("VX", "-"), ("GX", "0"),
                  ("M5", "B")])

# ------------------------------------------------------------------ routes
T, Jn = f.term, f.jn
f.rail("net-top", 100, RAIL, prefix="r-vdd-rail")
f.route("r-t-c", "net-top", Jn("JT"), [("to", T("CGS3", "1"))])
f.route("r-t-m3", "net-top", Jn("JT3"), [("to", T("M3", "S"))])
f.route("r-t-m5g", "net-top", Jn("JT2"), [("to", T("M5", "G"))])

f.route("r-g-c", "net-g3", T("CGS3", "2"), [("to", Jn("JG"))])
f.route("r-g-m3", "net-g3", Jn("JG"), [("to", T("M3", "G"))])
f.route("r-g-down", "net-g3", Jn("JG"),
        [("bend", 100, 170), ("to", Jn("JS"))])
f.route("r-g-bus", "net-g3", Jn("JS"), [("to", Jn("JS2"))])
f.route("r-g-m5s", "net-g3", T("M5", "S"), [("to", Jn("JS2"))])
f.route("r-g-igm", "net-g3", Jn("JS2"), [("to", T("IGM", "+"))])

f.route("r-x-m3", "net-x", T("M3", "D"),
        [("bend", 270, 190), ("to", Jn("JX"))])
f.route("r-x-m5", "net-x", T("M5", "D"), [("to", Jn("JX"))])
f.route("r-x-vx", "net-x", Jn("JX"),
        [("bend", 330, 250), ("to", T("VX", "+"))])
# I_gm and V_x sit pin-on-pin on their ground symbols, so neither needs a wire

# ------------------------------------------------------------- annotations
f.inst_label("CGS3", -16, 5, "end")
f.inst_label("M3", 18, 5, "start")
f.inst_label("M5", 18, 5, "start")
f.inst_label("VX", 16, 5, "start")
f.power_label("label-vdd", "net-top", "jvdd-end", 12, 6, "V_DD")
# I_x is the test current V_x pushes in, so it belongs on V_x's OWN lead --
# not on M_5's drain branch, where the current has already split
# (user, 2026-08-31).  That is where the page puts it too.
f.arrow("arrow-ix", 320, 250, 280, 250)
f.text("n-ix", 300, 238, "middle", name("I_x"))
# the red pen: 1/g_m5 is what the source below M_5 stands for
# hard up against the source it annotates: the space on its right
# belongs to V_x's ground, so the note goes on the left
f.arrow("arrow-gm", 196, 346, 196, 322)
f.text("n-gm", 188, 346, "end",
       {"runs": plain("1/")["runs"] + name("g_m5")["runs"]})

f.build(long_haul={"r-vdd-rail-2",  # 70: the rail on to M_3's source
                   "r-t-m3",       # 50: and down to it
                   "r-t-m5g",      # 170: the gate riser down to M_5
                   "r-g-m3",       # 80: the gate wire across to M_3
                   "r-g-down",     # 50+150: the long left leg, as the page
                                   #         draws it
                   "r-g-bus",      # 120: and back across under M_5
                   "r-x-m3",       # 50+60: M_3's drain doglegs onto the bus
                   "r-x-m5",       # 50: the bus over to the corner
                   "r-x-vx"},      # 60: V_x's lead, long enough to
                                   #     carry the I_x arrow
        rail_ends={"jvdd-start", "jvdd-end"},
        viewbox=(50, 40, 340, 350),
        # plain on purpose: "1/" is arithmetic, not a device name
        expect_differ={"n-gm"})
