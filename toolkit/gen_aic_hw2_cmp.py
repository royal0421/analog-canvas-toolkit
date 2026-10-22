# -*- coding: utf-8 -*-
"""AIC HW2 Fig. 1: double-tail dynamic comparator (M1..M13) + two output
inverters, redrawn for the report's Circuit Diagram (sizes go in a table
next to it, Table 1 format).

v2 (2026-10-22): v1 was rejected as "too fat"; spacing now copies the
handout figure (`HW2\\AI\\pages\\fig1_comparator.png`, ~1.45 px/unit by the
MOS D-S height): stage-1 columns 120 apart, latch columns 120 apart, the
latch tucked under stage 1's right half, Vap/Van trunks hugging the edges.

  stage 1:  rail 60 | M3/M4 100 | Vap/Van 140 | M1/M2 180 | tail 220 |
            M5 260 | ground 290
  latch:    rail 240 | M6/M7 280 | M8/M9 340 | Vsp row 370 / Vsn row 390 |
            M10..M13 420 | ground bus 460
  x below is the drawing coordinate before the +60 shift X().
"""
# publish: AIC-HW2_Fig1_double-tail-comparator preview_aic_hw2_cmp.svg
import os
import shutil
from icproj import Schematic, plain, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir, "out")   # analog-canvas root
# working copy for the course folder (only on the author's machine)
HW2_AI = os.path.join(os.path.expanduser("~"), "OneDrive", "桌面", "碩士班", "修課",
                      "類比積體電路", "HW", "HW2", "AI")
OUT = os.path.join(ROOT, "AIC-HW2_Fig1_double-tail-comparator.icproj.json")
f = Schematic("project-aic-hw2-cmp", "AIC HW2 Fig. 1 double-tail comparator",
              "CMP", out_proj=OUT,
              out_svg=os.path.join(HERE, "preview_aic_hw2_cmp.svg"))


def X(x):
    return x + 60


# ---------------------------------------------------------------- placement
f.mos("M3", "pmos", X(100), 100, "x", "M_3")      # S/D col 90, G 120
f.mos("M4", "pmos", X(200), 100, "none", "M_4")   # S/D col 210, G 180
f.mos("M1", "nmos", X(80), 180, "none", "M_1")    # D/S col 90, G 60
f.mos("M2", "nmos", X(220), 180, "x", "M_2")      # D/S col 210, G 240
f.mos("M5", "nmos", X(140), 260, "none", "M_5")   # D/S col 150, G 120
f.gnd("G5", X(150), 290)                          # pin-on-pin with M5.S

f.mos("M6", "pmos", X(320), 280, "x", "M_6")      # col 310, G 340
f.mos("M7", "pmos", X(420), 280, "none", "M_7")   # col 430, G 400
f.mos("M8", "pmos", X(300), 340, "none", "M_8")   # col 310, G 280
f.mos("M9", "pmos", X(440), 340, "x", "M_9")      # col 430, G 460
f.mos("M10", "nmos", X(220), 420, "none", "M_10")  # col 230, G 200
f.mos("M11", "nmos", X(320), 420, "x", "M_11")     # col 310, G 340
f.mos("M12", "nmos", X(420), 420, "none", "M_12")  # col 430, G 400
f.mos("M13", "nmos", X(520), 420, "x", "M_13")     # col 510, G 540
f.gnd("GL", X(370), 480)                           # pin (370,470)

f.place("INV1", "inverter", X(30), 390, extra={"schematicReference": "INV1"})
f.place("INV2", "inverter", X(30), 450, extra={"schematicReference": "INV2"})

# ports on every named lead: (id, pin x, pin y, circle side)
PORTS = (("P-VIP", X(50), 180, "left"), ("P-VIN", X(250), 180, "right"),
         ("P-CLK", X(110), 260, "left"),
         ("P-VAP2", X(190), 420, "left"), ("P-VAN2", X(550), 420, "right"),
         ("P-VSN", X(0), 390, "left"), ("P-VOP", X(60), 390, "right"),
         ("P-VSP", X(0), 450, "left"), ("P-VON", X(60), 450, "right"))
for pid, x, y, side in PORTS:
    if side == "left":
        f.port(pid, x - 10, y)
    else:
        f.port(pid, x + 10, y, mirror="x")
    assert f.pin(pid, "P") == (x, y), pid

# --------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("jvdd-start", "net-power-vdd", X(70), 60), ("JV3", "net-power-vdd", X(90), 60),
        ("JV4", "net-power-vdd", X(210), 60), ("jvdd-end", "net-power-vdd", X(230), 60),
        ("jvdd2-start", "net-power-vdd", X(290), 240), ("JV6", "net-power-vdd", X(310), 240),
        ("JV7", "net-power-vdd", X(430), 240), ("jvdd2-end", "net-power-vdd", X(450), 240),
        ("JAP", "net-vap", X(90), 140), ("JAN", "net-van", X(210), 140),
        ("JT", "net-tail", X(150), 220),
        ("JSP", "net-vsp", X(310), 370), ("JSP2", "net-vsp", X(380), 370),
        ("JSP3", "net-vsp", X(380), 280),
        ("JSN", "net-vsn", X(430), 390), ("JSN3", "net-vsn", X(360), 390),
        ("JG1", "net-gnd-2", X(310), 460), ("JG2", "net-gnd-2", X(370), 460),
        ("JG3", "net-gnd-2", X(430), 460)):
    f.junction(jid, net, x, y)

# -------------------------------------------------------------------- nets
PM = ("M3", "M4", "M6", "M7", "M8", "M9")
NM = ("M1", "M2", "M5", "M10", "M11", "M12", "M13")
f.net("net-power-vdd", [("M3", "S"), ("M4", "S"), ("M6", "S"), ("M7", "S")]
      + [(m, "B") for m in PM])
f.net("net-gnd-1", [("M5", "S"), ("G5", "0")] + [(m, "B") for m in NM])
f.net("net-gnd-2", [("M10", "S"), ("M11", "S"), ("M12", "S"), ("M13", "S"),
                    ("GL", "0")])
f.net("net-clk", [("M3", "G"), ("M4", "G")])
f.net("net-clk2", [("M5", "G"), ("P-CLK", "P")])
f.net("net-vip", [("M1", "G"), ("P-VIP", "P")])
f.net("net-vin", [("M2", "G"), ("P-VIN", "P")])
f.net("net-vap", [("M3", "D"), ("M1", "D"), ("M8", "G")])
f.net("net-van", [("M4", "D"), ("M2", "D"), ("M9", "G")])
f.net("net-vap2", [("M10", "G"), ("P-VAP2", "P")])
f.net("net-van2", [("M13", "G"), ("P-VAN2", "P")])
f.net("net-tail", [("M1", "S"), ("M2", "S"), ("M5", "D")])
f.net("net-p6", [("M6", "D"), ("M8", "S")])
f.net("net-p7", [("M7", "D"), ("M9", "S")])
f.net("net-vsp", [("M8", "D"), ("M10", "D"), ("M11", "D"), ("M12", "G"),
                  ("M7", "G")])
f.net("net-vsn", [("M9", "D"), ("M12", "D"), ("M13", "D"), ("M11", "G"),
                  ("M6", "G")])
f.net("net-inv1-in", [("INV1", "A"), ("P-VSN", "P")])
f.net("net-inv1-out", [("INV1", "Y"), ("P-VOP", "P")])
f.net("net-inv2-in", [("INV2", "A"), ("P-VSP", "P")])
f.net("net-inv2-out", [("INV2", "Y"), ("P-VON", "P")])

# ------------------------------------------------------------------ routes
T, J = f.term, f.jn
f.rail("net-power-vdd", 60, [X(70), X(90), X(210), X(230)])
f.rail("net-power-vdd", 240, [X(290), X(310), X(430), X(450)], prefix="r-vdd2-rail")
for r, jid, m in (("r-v3", "JV3", "M3"), ("r-v4", "JV4", "M4"),
                  ("r-v6", "JV6", "M6"), ("r-v7", "JV7", "M7")):
    f.route(r, "net-power-vdd", J(jid), [("to", T(m, "S"))])

f.route("r-clk", "net-clk", T("M3", "G"), [("to", T("M4", "G"))])
f.route("r-clk2", "net-clk2", T("P-CLK", "P"), [("to", T("M5", "G"))])
f.route("r-vip", "net-vip", T("P-VIP", "P"), [("to", T("M1", "G"))])
f.route("r-vin", "net-vin", T("P-VIN", "P"), [("to", T("M2", "G"))])

f.route("r-ap1", "net-vap", T("M3", "D"), [("to", J("JAP"))])
f.route("r-ap2", "net-vap", J("JAP"), [("to", T("M1", "D"))])
f.route("r-ap3", "net-vap", J("JAP"), [("bend", X(-40), 140), ("bend", X(-40), 340),
                                       ("to", T("M8", "G"))])
f.route("r-an1", "net-van", T("M4", "D"), [("to", J("JAN"))])
f.route("r-an2", "net-van", J("JAN"), [("to", T("M2", "D"))])
f.route("r-an3", "net-van", J("JAN"), [("bend", X(520), 140), ("bend", X(520), 340),
                                       ("to", T("M9", "G"))])
f.route("r-ap4", "net-vap2", T("P-VAP2", "P"), [("to", T("M10", "G"))])
f.route("r-an4", "net-van2", T("P-VAN2", "P"), [("to", T("M13", "G"))])

f.route("r-t1", "net-tail", T("M1", "S"), [("bend", X(90), 220), ("to", J("JT"))])
f.route("r-t2", "net-tail", T("M2", "S"), [("bend", X(210), 220), ("to", J("JT"))])
f.route("r-t3", "net-tail", J("JT"), [("to", T("M5", "D"))])

f.route("r-p6", "net-p6", T("M6", "D"), [("to", T("M8", "S"))])
f.route("r-p7", "net-p7", T("M7", "D"), [("to", T("M9", "S"))])

# Vsp: M8.D / M11.D share a column; row 370 -> M10.D; trunk x 380 -> M7.G, M12.G
f.route("r-sp1", "net-vsp", T("M8", "D"), [("to", J("JSP"))])
f.route("r-sp2", "net-vsp", J("JSP"), [("to", T("M11", "D"))])
f.route("r-sp3", "net-vsp", J("JSP"), [("bend", X(230), 370), ("to", T("M10", "D"))])
f.route("r-sp4", "net-vsp", J("JSP"), [("to", J("JSP2"))])
f.route("r-sp5", "net-vsp", J("JSP2"), [("to", J("JSP3"))])
f.route("r-sp6", "net-vsp", J("JSP3"), [("to", T("M7", "G"))])
f.route("r-sp7", "net-vsp", J("JSP2"), [("bend", X(380), 420), ("to", T("M12", "G"))])

# Vsn: M9.D / M12.D share a column; row 390 -> M13.D; trunk x 360 -> M6.G, M11.G
f.route("r-sn1", "net-vsn", T("M9", "D"), [("to", J("JSN"))])
f.route("r-sn2", "net-vsn", J("JSN"), [("to", T("M12", "D"))])
f.route("r-sn3", "net-vsn", J("JSN"), [("bend", X(510), 390), ("to", T("M13", "D"))])
f.route("r-sn4", "net-vsn", J("JSN"), [("to", J("JSN3"))])
f.route("r-sn5", "net-vsn", J("JSN3"), [("bend", X(360), 280), ("to", T("M6", "G"))])
f.route("r-sn6", "net-vsn", J("JSN3"), [("bend", X(360), 420), ("to", T("M11", "G"))])

# latch ground bus
f.route("r-g0", "net-gnd-2", T("M10", "S"), [("bend", X(230), 460), ("to", J("JG1"))])
f.route("r-g1", "net-gnd-2", T("M11", "S"), [("to", J("JG1"))])
f.route("r-g2", "net-gnd-2", J("JG1"), [("to", J("JG2"))])
f.route("r-g3", "net-gnd-2", J("JG2"), [("to", T("GL", "0"))])
f.route("r-g4", "net-gnd-2", J("JG2"), [("to", J("JG3"))])
f.route("r-g5", "net-gnd-2", J("JG3"), [("to", T("M12", "S"))])
f.route("r-g6", "net-gnd-2", J("JG3"), [("bend", X(510), 460), ("to", T("M13", "S"))])

# inverter ports sit pin-on-pin on the gate's own leads: no extra wire (user)

# ------------------------------------------------------------- annotations
TERMS = (("P-VIP", "V_ip", "net-vip", "input", -1),
         ("P-VIN", "V_in", "net-vin", "input", 1),
         ("P-VAP2", "V_ap", "net-vap2", "input", -1),
         ("P-VAN2", "V_an", "net-van2", "input", 1),
         ("P-VSN", "V_sn", "net-inv1-in", "input", -1),
         ("P-VOP", "V_op", "net-inv1-out", "output", 1),
         ("P-VSP", "V_sp", "net-inv2-in", "input", -1),
         ("P-VON", "V_on", "net-inv2-out", "output", 1))
for pid, nm, net, d, side in TERMS:
    tid = "t-" + pid.lower()
    f.terminal(tid, nm, net, d, [pid])
    f.port_label(pid, tid, side * LABEL_PORT, 5,
                 "start" if side > 0 else "end")
f.terminal("t-clk2", "CLK", "net-clk2", "input", ["P-CLK"])

for m in PM + NM:
    mir = f.placed[m][3] == "x"
    if m in ("M10", "M11", "M12", "M13"):   # names hug their own MOS (user)
        f.inst_label(m, -14 if mir else 14, 5, "end" if mir else "start")
    else:
        f.inst_label(m, -18 if mir else 18, 5, "end" if mir else "start")
f.power_label("label-vdd", "net-power-vdd", "jvdd-end", 12, 6, "V_DD")
f.power_label("label-vdd2", "net-power-vdd", "jvdd2-end", 12, 6, "V_DD")

TXT = [("n-clk", X(150), 92, "middle", plain("clk")),
       ("n-clk2", X(84), 265, "end", plain("clk")),
       ("n-vap", X(30), 128, "middle", "V_ap"),
       ("n-van", X(270), 128, "middle", "V_an"),
       ("n-vsn", X(356), 311, "end", "V_sn"),
       ("n-vsp", X(384), 311, "start", "V_sp")]
for tid, x, y, al, s in TXT:
    f.text(tid, x, y, al, s)

f.build(long_haul={"r-clk", "r-ap3", "r-an3", "r-sp3", "r-sp4", "r-sp5",
                   "r-sn3", "r-sn4", "r-sn5", "r-sn6", "r-sp7", "r-g0",
                   "r-g6", "r-g2", "r-g4", "r-t1", "r-t2", "r-vdd-rail-1", "r-vdd2-rail-1"},
        rail_ends={"jvdd-start", "jvdd-end", "jvdd2-start", "jvdd2-end"},
        viewbox=(X(-80), 20, 740, 480),
        expect_differ={"n-clk", "n-clk2"})

if os.path.isdir(HW2_AI):
    shutil.copyfile(OUT, os.path.join(HW2_AI, os.path.basename(OUT)))
