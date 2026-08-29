# -*- coding: utf-8 -*-
"""Razavi Fig. 10.35(a): differential pair M1/M2 loaded by a diode-connected
M3/M4 pair, each pair carrying its own tail source.

Topology came from `python scan_figure.py <screenshot>` (SOP §3C), not from
looking: the top bus prints as two runs with a GAP between them, so M3/M4 are
diode-connected rather than cross-coupled; and there is no dot where the I_SS2
riser meets the tail bus, so that is a crossing.

Everything reusable lives in icproj.py -- this file is only the five sections
the SOP says a new figure has to write.
"""
import os
from icproj import Schematic, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-razavi-fig-10-35a",
    "Razavi Fig. 10.35(a) — differential pair with diode-connected load",
    "Fig_10_35a",
    out_proj=os.path.join(OUT, "Razavi_Fig_10_35a_diffpair-diode-load.icproj.json"),
    out_svg=os.path.join(HERE, "preview_fig1035.svg"))

# ---------------------------------------------------------------- placement
# Symmetric about x = 300.  Columns (D/S and gate risers):
#   M1 200 | M3 260 | M3.G 290 | Q 300 | M4.G 310 | M4 340 | M2 400
# Rows: SOP §3A standard stack, with the tail bus dropped to 280 so the node
# label Q sits centred in a 30-unit gap instead of touching the line, and the
# input pair pulled one grid step outward so "M_3" cannot be read as M1's.
f.isrc("I1", 190, 140, "I_1")
f.isrc("I2", 410, 140, "I_2")
f.mos("M1", "nmos", 180, 230, "none", "M_1")      # gates face outward
f.mos("M2", "nmos", 420, 230, "x", "M_2")
f.mos("M3", "nmos", 260, 230, "x", "M_3")         # gates face inward;
f.mos("M4", "nmos", 340, 230, "none", "M_4")      # 80 apart so each gate
                                                  # gets an escape corridor
f.isrc("ISS1", 190, 320, "I_SS1")
f.isrc("ISS2", 300, 320, "I_SS2")
f.gnd("GND1", 190, 360)
f.gnd("GND2", 300, 360)
f.port("VIN1", 130, 230)                          # circle left of its pin
f.port("VIN2", 470, 230, mirror="x")
f.port("VOUTL", 260, 180, mirror="x")             # the two V_out circles face
f.port("VOUTR", 340, 180)                         # each other across the label

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("jvdd-start", "net-power-vdd", 170, 100),
        ("JV1", "net-power-vdd", 190, 100),
        ("JV2", "net-power-vdd", 410, 100),
        ("jvdd-end", "net-power-vdd", 430, 100),
        ("JXA", "net-x", 190, 180),      # V_out tap
        ("JXB", "net-x", 190, 200),      # top bus leaves the column here
        ("JX3", "net-x", 250, 200),      # M3 drain riser / gate riser tee
        ("JYA", "net-y", 410, 180),
        ("JYB", "net-y", 410, 200),
        ("JY4", "net-y", 350, 200),
        ("JP", "net-p", 190, 290),       # tail node P
        ("JQ", "net-q", 300, 260)):      # tail node Q, one step BELOW the source
                                 # pins so each source escapes south first
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
f.net("net-power-vdd", [("I1", "+"), ("I2", "+")])
f.net("net-x", [("I1", "-"), ("M1", "D"), ("M3", "D"), ("M3", "G"),
                ("VOUTL", "P")])
f.net("net-y", [("I2", "-"), ("M2", "D"), ("M4", "D"), ("M4", "G"),
                ("VOUTR", "P")])
f.net("net-p", [("M1", "S"), ("M2", "S"), ("ISS1", "+")])
f.net("net-q", [("M3", "S"), ("M4", "S"), ("ISS2", "+")])
f.net("net-in1", [("M1", "G"), ("VIN1", "P")])
f.net("net-in2", [("M2", "G"), ("VIN2", "P")])
f.net("net-gnd-1", [("GND1", "0"), ("ISS1", "-"),
                    ("M1", "B"), ("M2", "B"), ("M3", "B"), ("M4", "B")])
f.net("net-gnd-2", [("GND2", "0"), ("ISS2", "-")])

# ---------------------------------------------------------------- routes
T, J = f.term, f.jn
f.rail("net-power-vdd", 100, [170, 190, 410, 430])
f.route("r-vdd-drop-1", "net-power-vdd", J("JV1"), [("to", T("I1", "+"))])
f.route("r-vdd-drop-2", "net-power-vdd", J("JV2"), [("to", T("I2", "+"))])

for side, cs, mD, mG, jA, jB, jT, vo, bend in (
        ("x", "I1", "M1", "M3", "JXA", "JXB", "JX3", "VOUTL", 290),
        ("y", "I2", "M2", "M4", "JYA", "JYB", "JY4", "VOUTR", 310)):
    n = "net-" + side
    f.route("r-%s-1" % side, n, T(cs, "-"), [("to", J(jA))])
    f.route("r-%s-vout" % side, n, J(jA), [("to", T(vo, "P"))])
    f.route("r-%s-2" % side, n, J(jA), [("to", J(jB))])
    f.route("r-%s-d" % side, n, J(jB), [("to", T(mD, "D"))])
    f.route("r-%s-bus" % side, n, J(jB), [("to", J(jT))])
    f.route("r-%s-dg" % side, n, J(jT), [("to", T(mG, "D"))])
    # A gate escapes sideways, so the wire drops in its own corridor and
    # only then turns into the pin (the editor paints a wrong-way
    # departure red).
    f.route("r-%s-g" % side, n, J(jT), [("bend", bend, 200),
                                        ("bend", bend, 230),
                                        ("to", T(mG, "G"))])

f.route("r-p-m1s", "net-p", T("M1", "S"), [("to", J("JP"))])
f.route("r-p-bus", "net-p", T("M2", "S"), [("bend", 410, 290),
                                           ("to", J("JP"))])
f.route("r-p-iss1", "net-p", J("JP"), [("to", T("ISS1", "+"))])
# The Q riser crosses the tail bus at (300,290) with no junction -- a crossing,
# exactly as the textbook draws it.
f.route("r-q-m3s", "net-q", T("M3", "S"), [("bend", 250, 260),
                                           ("to", J("JQ"))])
f.route("r-q-m4s", "net-q", T("M4", "S"), [("bend", 350, 260),
                                           ("to", J("JQ"))])
f.route("r-q-iss2", "net-q", J("JQ"), [("to", T("ISS2", "+"))])
f.route("r-in1", "net-in1", T("M1", "G"), [("to", T("VIN1", "P"))])
f.route("r-in2", "net-in2", T("M2", "G"), [("to", T("VIN2", "P"))])
f.route("r-g1", "net-gnd-1", T("ISS1", "-"), [("to", T("GND1", "0"))])
f.route("r-g2", "net-gnd-2", T("ISS2", "-"), [("to", T("GND2", "0"))])

# ------------------------------------------------- cell terminals for ports
# Ws() keeps the case when there is an underscore, so "V_in1" stays a capital
# italic V.  The two V_out terminals carry no label: the figure prints one
# centred "V_out" between the circles, drawn as drafting text below.
f.terminal("terminal-vin1", "V_in1", "net-in1", "input", ["VIN1"])
f.terminal("terminal-vin2", "V_in2", "net-in2", "input", ["VIN2"])
f.terminal("terminal-voutl", "V_out1", "net-x", "output", ["VOUTL"])
f.terminal("terminal-voutr", "V_out2", "net-y", "output", ["VOUTR"])

# ---------------------------------------------------------------- annotations
# MOS ink stops at centre +/-10.6, so +/-18 leaves the standard 8-unit gap; the
# label always sits on the drain/source side (the LEFT side when mirrored).
# M1/M2 are unlabelled in the textbook figure.
f.inst_label("M3", -18, 5, "end")
f.inst_label("M4", 18, 5, "start")
f.inst_label("ISS1", 18, 5, "start")
f.inst_label("ISS2", 18, 5, "start")
f.port_label("VIN1", "terminal-vin1", -LABEL_PORT, 5, "end")
f.port_label("VIN2", "terminal-vin2", LABEL_PORT, 5, "start")
f.power_label("label-vdd", "net-power-vdd", "jvdd-end", 12, 6, "V_DD")

f.text("note-vout", 300, 185, "middle", "V_out")
f.text("note-p", 178, 291, "end", "P")
f.text("note-q", 292, 281, "end", "Q")   # centred in the 260..290 gap

f.build(long_haul={
            "r-vdd-rail-1",     # the V_DD rail itself
            "r-p-bus",          # M2 source -> node P: the tail bus
            # Label-driven spans.  Our labels render 1.21x the size of
            # Razavi's print, so every clearance the text sets is ~1.2x his:
            "r-x-bus", "r-y-bus",     # 60: input pair pulled out so "M_3"/
                                      # "M_4" cannot be misread as M1/M2
            "r-x-vout", "r-y-vout",   # the two V_out circles must clear
            "r-q-m3s", "r-q-m4s",     # 50: the shared-source bus, widened
                                      # by the gates' escape corridors
                                      # the centred "V_out" caption
        },
        rail_ends={"jvdd-start", "jvdd-end"},
        viewbox=(80, 85, 450, 300))
