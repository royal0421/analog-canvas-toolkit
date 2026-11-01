# -*- coding: utf-8 -*-
"""AIC intro (115-1) HSPICE HW4 Fig. (a): common-source stage, resistive load
R_D, source resistance R_S in series with the gate, load capacitor C_L.

No original figure -- topology from the homework netlist (2024 HW4 Fig. (a)
with new values).  Spacing per SOP 3A.  W/L is stated in the problem text,
not on the figure.

  columns: V_in 240 | R_S 260 (horizontal) | M1 320 (D/S 330) | C_L 390 | V_out port 440
  rows:    rail 100 | R_D 140 | out node 180 | M1 220 | V_in 260 | grounds 290
"""
import os
from icproj import Schematic, name_suffix, plain, dy_above, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-aicintro-hw4-a",
    "AIC intro HSPICE HW4 Fig. (a) - common-source stage",
    "HW4_Fig_a",
    out_proj=os.path.join(OUT, "AIC-intro_HSPICE-HW4_Fig-a_CS.icproj.json"),
    out_svg=os.path.join(HERE, "preview_aicintro_hw4_a.svg"))

# ---------------------------------------------------------------- placement
f.passive("RD", "resistor", 330, 140, "R_D")
f.mos("M1", "nmos", 320, 220, "none", "M_1")
f.passive("RS", "resistor", 260, 220, "R_S", rotation=90)   # pin 1 right, 2 left
f.passive("CL", "capacitor", 390, 220, "C_L")
f.place("VIN", "voltage-source", 240, 260,
        extra={"schematicReference": "VIN"})
f.gnd("GND1", 240, 290)          # pin (240,280) = VIN '-' : pin-on-pin
f.gnd("GND2", 330, 290)
f.gnd("GND3", 390, 290)
f.port("VOUT", 440, 180, mirror="x")

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("jvdd-start", "net-power-vdd", 310, 100),
        ("JV1", "net-power-vdd", 330, 100),
        ("jvdd-end", "net-power-vdd", 350, 100),
        ("JO", "net-out", 330, 180),     # R_D / M1 drain / C_L branch
        ("JC", "net-out", 390, 180)):    # C_L / V_out
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
f.net("net-power-vdd", [("RD", "1")])
f.net("net-out", [("RD", "2"), ("M1", "D"), ("CL", "1"), ("VOUT", "P")])
f.net("net-g", [("RS", "1"), ("M1", "G")])
f.net("net-in", [("RS", "2"), ("VIN", "+")])
f.net("net-gnd-1", [("M1", "S"), ("GND2", "0"), ("M1", "B")])
f.net("net-gnd-2", [("VIN", "-"), ("GND1", "0")])
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

f.route("r-g", "net-g", T("RS", "1"), [("to", T("M1", "G"))])
f.route("r-in", "net-in", T("RS", "2"), [("to", T("VIN", "+"))])

f.route("r-gnd2", "net-gnd-1", T("M1", "S"), [("to", T("GND2", "0"))])
f.route("r-gnd3", "net-gnd-3", T("CL", "2"), [("to", T("GND3", "0"))])

# ------------------------------------------------- cell terminals for ports
f.terminal("terminal-vout", "V_out", "net-out", "output", ["VOUT"])

# ---------------------------------------------------------------- annotations
f.inst_label("M1", 18, 5, "start")
f.port_label("VOUT", "terminal-vout", LABEL_PORT, 5, "start")
f.power_label("label-vdd", "net-power-vdd", "jvdd-end", 12, 6, "V_DD")
f.annotations[-1]["content"] = name_suffix("V_DD", " = 1.8 V")

for tid, x, y, align, label, owner in (
        ("note-rd", 343, 145, "start", name_suffix("R_D", " = 10 k\u03a9"), "RD"),
        ("note-cl", 406, 225, "start", name_suffix("C_L", " = 0.03 pF"), "CL"),
        ("note-rs", 260, int(220 + dy_above(5.37, gap=6)), "middle",
         name_suffix("R_S", " = 5 k\u03a9"), "RS"),
        ("note-vin", 210, 255, "end", "V_in", "VIN"),
        ("note-vin-dc", 210, 275, "end", plain("DC = 0.53 V"), "VIN"),
        ("note-vin-ac", 210, 295, "end", plain("AC = 1"), "VIN")):
    f.text(tid, x, y, align, label, owner)

f.build(long_haul={
            "r-o-port",  # 50: v58 symbols drew 10 less of this run
            "r-o-jc",      # 60: room for the M_1 label between drain and C_L
        },
        rail_ends={"jvdd-start", "jvdd-end"},
        viewbox=(80, 80, 460, 240),
        expect_differ={"label-vdd", "note-rd", "note-cl", "note-rs",
                       "note-vin-dc", "note-vin-ac"})   # value text, upright on purpose (SOP 4)
