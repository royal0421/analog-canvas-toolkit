# -*- coding: utf-8 -*-
"""AIC intro (115-1) HSPICE HW4 Fig. (c): cascode stage -- M1 is the input
device (gate driven through R_S), M2 the cascode device (gate at V_b),
resistive load R_D, load C_L.  Both bodies tied to ground.

  columns: V_in 240 | R_S 260 | M1/M2 320 (D/S 330) | C_L 390 | V_out port 440
  rows:    rail 100 | R_D 140 | out node 180 | M2 220 | M1 280 | V_in 320 | grounds 350
"""
import os
from icproj import Schematic, name_suffix, plain, dy_above, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-aicintro-hw4-c",
    "AIC intro HSPICE HW4 Fig. (c) - cascode stage",
    "HW4_Fig_c",
    out_proj=os.path.join(OUT, "AIC-intro_HSPICE-HW4_Fig-c_cascode.icproj.json"),
    out_svg=os.path.join(HERE, "preview_aicintro_hw4_c.svg"))

# ---------------------------------------------------------------- placement
f.passive("RD", "resistor", 330, 140, "R_D")
f.mos("M2", "nmos", 320, 220, "none", "M_2")
f.mos("M1", "nmos", 320, 280, "none", "M_1")
f.passive("RS", "resistor", 260, 280, "R_S", rotation=90)   # pin 1 right, 2 left
f.passive("CL", "capacitor", 390, 220, "C_L")
f.place("VIN", "voltage-source", 240, 320,
        extra={"schematicReference": "VIN"})
f.gnd("GND1", 240, 350)          # pin (240,340) = VIN '-' : pin-on-pin
f.gnd("GND2", 330, 350)
f.gnd("GND3", 390, 250)          # pin (390,240) = C_L '2' : pin-on-pin
f.port("VB", 270, 220)           # circle left of its pin (280,220)
f.port("VOUT", 440, 180, mirror="x")

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("jvdd-start", "net-power-vdd", 310, 100),
        ("JV1", "net-power-vdd", 330, 100),
        ("jvdd-end", "net-power-vdd", 350, 100),
        ("JO", "net-out", 330, 180),
        ("JC", "net-out", 390, 180)):
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
f.net("net-power-vdd", [("RD", "1")])
f.net("net-out", [("RD", "2"), ("M2", "D"), ("CL", "1"), ("VOUT", "P")])
f.net("net-b", [("VB", "P"), ("M2", "G")])
f.net("net-x", [("M2", "S"), ("M1", "D")])
f.net("net-g", [("RS", "1"), ("M1", "G")])
f.net("net-in", [("RS", "2"), ("VIN", "+")])
f.net("net-gnd-1", [("M1", "S"), ("GND2", "0"), ("M1", "B"), ("M2", "B")])
f.net("net-gnd-2", [("VIN", "-"), ("GND1", "0")])
f.net("net-gnd-3", [("CL", "2"), ("GND3", "0")])

# ---------------------------------------------------------------- routes
T, J = f.term, f.jn
f.rail("net-power-vdd", 100, [310, 330, 350])
f.route("r-vdd-rd", "net-power-vdd", J("JV1"), [("to", T("RD", "1"))])

f.route("r-o-rd", "net-out", T("RD", "2"), [("to", J("JO"))])
f.route("r-o-m2", "net-out", J("JO"), [("to", T("M2", "D"))])
f.route("r-o-jc", "net-out", J("JO"), [("to", J("JC"))])
f.route("r-o-cl", "net-out", J("JC"), [("to", T("CL", "1"))])
f.route("r-o-port", "net-out", J("JC"), [("to", T("VOUT", "P"))])

f.route("r-b", "net-b", T("VB", "P"), [("to", T("M2", "G"))])
f.route("r-x", "net-x", T("M2", "S"), [("to", T("M1", "D"))])
f.route("r-g", "net-g", T("RS", "1"), [("to", T("M1", "G"))])
f.route("r-in", "net-in", T("RS", "2"), [("to", T("VIN", "+"))])
f.route("r-gnd2", "net-gnd-1", T("M1", "S"), [("to", T("GND2", "0"))])

# ------------------------------------------------- cell terminals for ports
f.terminal("terminal-vout", "V_out", "net-out", "output", ["VOUT"])
f.terminal("terminal-vb", "V_b", "net-b", "input", ["VB"])

# ---------------------------------------------------------------- annotations
f.inst_label("M2", 18, 5, "start")
f.inst_label("M1", 18, 5, "start")
f.port_label("VOUT", "terminal-vout", LABEL_PORT, 5, "start")
f.power_label("label-vdd", "net-power-vdd", "jvdd-end", 12, 6, "V_DD")
f.annotations[-1]["content"] = name_suffix("V_DD", " = 1.8 V")

for tid, x, y, align, label, owner in (
        ("note-vb", 270 - LABEL_PORT, 225, "end", name_suffix("V_b", " = 1.0 V"), "VB"),
        ("note-rd", 343, 145, "start", name_suffix("R_D", " = 10 k\u03a9"), "RD"),
        ("note-cl", 406, 225, "start", name_suffix("C_L", " = 0.03 pF"), "CL"),
        ("note-rs", 260, int(280 + dy_above(5.37, gap=6)), "middle",
         name_suffix("R_S", " = 5 k\u03a9"), "RS"),
        ("note-vin", 210, 315, "end", "V_in", "VIN"),
        ("note-vin-dc", 210, 335, "end", plain("DC = 0.53 V"), "VIN"),
        ("note-vin-ac", 210, 355, "end", plain("AC = 1"), "VIN")):
    f.text(tid, x, y, align, label, owner)

f.build(long_haul={
            "r-o-port",  # 50: v58 symbols drew 10 less of this run
            "r-o-jc",      # 60: room for the M_2 label between drain and C_L
        },
        rail_ends={"jvdd-start", "jvdd-end"},
        viewbox=(80, 80, 460, 300),
        expect_differ={"label-vdd", "note-vb", "note-rd", "note-cl", "note-rs",
                       "note-vin-dc", "note-vin-ac"})   # value text, upright on purpose (SOP 4)
