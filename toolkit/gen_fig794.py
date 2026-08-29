# -*- coding: utf-8 -*-
"""Razavi Fig. 7.94: source follower M1 biased through R_G, with the source
node X loaded by R_S and AC-coupled through C_1 into a 50-ohm R_L.

Topology from `python scan_figure.py <screenshot>` (SOP §3C):
  M1 mirror "none" (gate bar left of the channel bar); the only junction dots
  are the gate node, node X and the output node; the 10 px gap in the y=250
  row is the capacitor's two plates, not a break in a wire.

First figure to use a rotated instance: C_1 is `rotation: 90`, which by the
repo's own rotatePointByDegrees puts pin "1" on the RIGHT and pin "2" on the
LEFT.
"""
import os
from icproj import Schematic, name_suffix, plain, dy_above, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-razavi-fig-7-94",
    "Razavi Fig. 7.94 — source follower with AC-coupled 50 ohm load",
    "Fig_7_94",
    out_proj=os.path.join(OUT, "Razavi_Fig_7_94_source-follower.icproj.json"),
    out_svg=os.path.join(HERE, "preview_fig794.svg"))

# ---------------------------------------------------------------- placement
# Columns: V_in 220 | gate node 250 | M1 300 (D/S 310) | C_1 370 | out 430
# Rows:    rail 100 | R_G centre 140 | gate + M1 centre 180 | node X 220
#          | R_S / R_L centre 260 | ground centre 300
# The rail sits 80 above the gate row because R_G's body is 40 tall and needs
# a 20 stub at each end -- that is what makes the drain riser 60.
f.passive("RG", "resistor", 250, 140, "R_G")
f.mos("M1", "nmos", 300, 180, "none", "M_1")
f.passive("RS", "resistor", 310, 260, "R_S")
f.passive("C1", "capacitor", 370, 220, "C_1", rotation=90)
f.passive("RL", "resistor", 430, 260, "R_L")
f.gnd("GND1", 310, 300)
f.gnd("GND2", 430, 300)
f.port("VIN", 220, 180)                 # circle left of its pin
f.port("VOUT", 460, 220, mirror="x")    # circle right of its pin

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("jvdd-start", "net-power-vdd", 230, 100),
        ("JV1", "net-power-vdd", 250, 100),
        ("JV2", "net-power-vdd", 310, 100),
        ("jvdd-end", "net-power-vdd", 330, 100),
        ("JG", "net-g", 250, 180),      # R_G / V_in / M1 gate
        ("JX", "net-x", 310, 220),      # M1 source / R_S / C_1
        ("JO", "net-out", 430, 220)):   # C_1 / R_L / V_out
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
f.net("net-power-vdd", [("RG", "1"), ("M1", "D")])
f.net("net-g", [("RG", "2"), ("M1", "G"), ("VIN", "P")])
f.net("net-x", [("M1", "S"), ("RS", "1"), ("C1", "2")])
f.net("net-out", [("C1", "1"), ("RL", "1"), ("VOUT", "P")])
f.net("net-gnd-1", [("RS", "2"), ("GND1", "0"), ("M1", "B")])
f.net("net-gnd-2", [("RL", "2"), ("GND2", "0")])

# ---------------------------------------------------------------- routes
T, J = f.term, f.jn
f.rail("net-power-vdd", 100, [230, 250, 310, 330])
f.route("r-vdd-rg", "net-power-vdd", J("JV1"), [("to", T("RG", "1"))])
f.route("r-vdd-m1d", "net-power-vdd", J("JV2"), [("to", T("M1", "D"))])

f.route("r-g-rg", "net-g", T("RG", "2"), [("to", J("JG"))])
f.route("r-g-m1", "net-g", J("JG"), [("to", T("M1", "G"))])
f.route("r-g-vin", "net-g", J("JG"), [("to", T("VIN", "P"))])

f.route("r-x-m1s", "net-x", T("M1", "S"), [("to", J("JX"))])
f.route("r-x-rs", "net-x", J("JX"), [("to", T("RS", "1"))])
f.route("r-x-c1", "net-x", J("JX"), [("to", T("C1", "2"))])

f.route("r-o-c1", "net-out", T("C1", "1"), [("to", J("JO"))])
f.route("r-o-rl", "net-out", J("JO"), [("to", T("RL", "1"))])
f.route("r-o-vout", "net-out", J("JO"), [("to", T("VOUT", "P"))])

f.route("r-g1", "net-gnd-1", T("RS", "2"), [("to", T("GND1", "0"))])
f.route("r-g2", "net-gnd-2", T("RL", "2"), [("to", T("GND2", "0"))])

# ------------------------------------------------- cell terminals for ports
f.terminal("terminal-vin", "V_in", "net-g", "input", ["VIN"])
f.terminal("terminal-vout", "V_out", "net-out", "output", ["VOUT"])

# ---------------------------------------------------------------- annotations
# Resistor ink is +/-5.37 wide, so ink+8 puts its label at +/-13; the MOS keeps
# the usual +/-18.  C_1 is labelled ABOVE: box bottom = ink top - 8, and the
# subscript hangs 5.5 below the baseline.  Razavi leaves 5.45 there, not 8,
# so dy = -(8.05 + 5.45 + 5.5) = -19 -- matches the textbook page exactly.
f.inst_label("RG", -13, 5, "end")
f.inst_label("M1", 18, 5, "start")
f.inst_label("RS", 13, 5, "start")
f.inst_label("RL", 13, 5, "start")
f.inst_label("C1", 0, dy_above(8.05), "middle")   # 8.05 = plate half-height
f.port_label("VIN", "terminal-vin", -LABEL_PORT, 5, "end")
f.port_label("VOUT", "terminal-vout", LABEL_PORT, 5, "start")
f.power_label("label-vdd", "net-power-vdd", "jvdd-end", 12, 6, "V_DD")
f.annotations[-1]["content"] = name_suffix("V_DD", " = 1.8 V")

f.text("note-x", 298, 225, "end", "X")
f.drafting.append(dict(f.drafting[-1], id="note-rl-value",
                       alignment="end",
                       anchor={"kind": "free",
                               "position": {"x": 417, "y": 265}},
                       content=plain("50 \u03a9")))
f._text_owner["note-rl-value"] = "RL"   # it is R_L's value, so
                                        # the crowding audit must not
                                        # read it as a stray label

f.build(long_haul={
            "r-vdd-rail-1",   # the V_DD rail itself
            "r-vdd-m1d",      # 60: R_G's 40-unit body plus two 20 stubs set
                              # the rail height, so the drain riser follows
        },
        rail_ends={"jvdd-start", "jvdd-end"},
        viewbox=(165, 80, 365, 250))
