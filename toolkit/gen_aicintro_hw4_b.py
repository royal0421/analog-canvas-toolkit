# -*- coding: utf-8 -*-
"""AIC intro (115-1) HSPICE HW4 Fig. (b): common-gate stage, resistive load
R_D, gate held at V_b, input applied to the source through R_S, load C_L.
Body tied to ground (same transistor as Fig. (a)).

  columns: V_b port 270 | M1 320 (D/S 330) | C_L 390 | V_out port 440
  rows:    rail 100 | R_D 140 | out node 180 | M1 220 | R_S 290 | V_in 350
"""
import os
from icproj import Schematic, name_suffix, plain, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-aicintro-hw4-b",
    "AIC intro HSPICE HW4 Fig. (b) - common-gate stage",
    "HW4_Fig_b",
    out_proj=os.path.join(OUT, "AIC-intro_HSPICE-HW4_Fig-b_CG.icproj.json"),
    out_svg=os.path.join(HERE, "preview_aicintro_hw4_b.svg"))

# ---------------------------------------------------------------- placement
f.passive("RD", "resistor", 330, 140, "R_D")
f.mos("M1", "nmos", 320, 220, "none", "M_1")
f.passive("RS", "resistor", 330, 290, "R_S")
f.passive("CL", "capacitor", 390, 220, "C_L")
f.place("VIN", "voltage-source", 330, 350,
        extra={"schematicReference": "VIN"})
f.gnd("GND1", 330, 380)          # pin (330,370) = VIN '-' : pin-on-pin
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
f.net("net-out", [("RD", "2"), ("M1", "D"), ("CL", "1"), ("VOUT", "P")])
f.net("net-b", [("VB", "P"), ("M1", "G")])
f.net("net-s", [("M1", "S"), ("RS", "1")])
f.net("net-in", [("RS", "2"), ("VIN", "+")])
f.net("net-gnd-1", [("VIN", "-"), ("GND1", "0"), ("M1", "B")])
f.net("net-gnd-3", [("CL", "2"), ("GND3", "0")])

# ---------------------------------------------------------------- routes
T, J = f.term, f.jn
f.rail("net-power-vdd", 100, [310, 330, 350])
f.route("r-vdd-rd", "net-power-vdd", J("JV1"), [("to", T("RD", "1"))])

f.route("r-o-rd", "net-out", T("RD", "2"), [("to", J("JO"))])
f.route("r-o-m1", "net-out", J("JO"), [("to", T("M1", "D"))])
f.route("r-o-jc", "net-out", J("JO"), [("to", J("JC"))])
f.route("r-o-cl", "net-out", J("JC"), [("to", T("CL", "1"))])
f.route("r-o-port", "net-out", J("JC"), [("to", T("VOUT", "P"))])

f.route("r-b", "net-b", T("VB", "P"), [("to", T("M1", "G"))])
f.route("r-s", "net-s", T("M1", "S"), [("to", T("RS", "1"))])
f.route("r-in", "net-in", T("RS", "2"), [("to", T("VIN", "+"))])

# ------------------------------------------------- cell terminals for ports
f.terminal("terminal-vout", "V_out", "net-out", "output", ["VOUT"])
f.terminal("terminal-vb", "V_b", "net-b", "input", ["VB"])

# ---------------------------------------------------------------- annotations
f.inst_label("M1", 18, 5, "start")
f.port_label("VOUT", "terminal-vout", LABEL_PORT, 5, "start")
f.power_label("label-vdd", "net-power-vdd", "jvdd-end", 12, 6, "V_DD")
f.annotations[-1]["content"] = name_suffix("V_DD", " = 1.8 V")

for tid, x, y, align, label, owner in (
        ("note-vb", 270 - LABEL_PORT, 225, "end", name_suffix("V_b", " = 1.2 V"), "VB"),
        ("note-rd", 343, 145, "start", name_suffix("R_D", " = 10 k\u03a9"), "RD"),
        ("note-cl", 406, 225, "start", name_suffix("C_L", " = 0.03 pF"), "CL"),
        ("note-rs", 343, 295, "start", name_suffix("R_S", " = 5 k\u03a9"), "RS"),
        ("note-vin", 358, 340, "start", "V_in", "VIN"),
        ("note-vin-dc", 358, 365, "start", plain("DC = 0.2 V"), "VIN"),
        ("note-vin-ac", 358, 387, "start", plain("AC = 1"), "VIN")):
    f.text(tid, x, y, align, label, owner)

f.build(long_haul={
            "r-o-jc",      # 60: room for the M_1 label between drain and C_L
        },
        rail_ends={"jvdd-start", "jvdd-end"},
        viewbox=(150, 80, 370, 330),
        expect_differ={"label-vdd", "note-vb", "note-rd", "note-cl", "note-rs",
                       "note-vin-dc", "note-vin-ac"})   # value text, upright on purpose (SOP 4)
