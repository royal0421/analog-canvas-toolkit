# -*- coding: utf-8 -*-
"""AIC HW2 (ADFP N16 double-tail comparator) testbenches for the report,
white background.  Topology from the Virtuoso schematics (`P4_TB.png` /
`P5_TB_offset.png`); v2 (2026-10-22) wires every source straight to the
comparator box instead of the net-name stubs of the original -- the user
rejected v1 as badly arranged.

Same topology for both; only the two PWL sources differ:
  python gen_aic_hw2_tb.py pattern   -> CMP_TB        (10-pattern PWL)
  python gen_aic_hw2_tb.py offset    -> CMP_OFFSET_TB (+-20 mV ramps)

  V3 (VIN) / V2 (VIP) lie horizontally and feed the box from the left; their
  minus ends meet on the common-mode node above V0 (350 mV).  V4 (VDD) sits
  above the box, V1 (CLK) below it; the outputs carry 20 fF to ground and
  end on ports.  The comparator is a drafting box with its pin names inside.
"""
# publish: AIC-HW2_CMP_TB preview_aic_hw2_cmp_tb.svg
import os
import shutil
import sys
from icproj import Schematic, plain, LABEL_PORT

MODE = sys.argv[1] if len(sys.argv) > 1 else "pattern"
assert MODE in ("pattern", "offset"), MODE
TAG = {"pattern": "CMP_TB", "offset": "CMP_OFFSET_TB"}[MODE]
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir, "out")   # analog-canvas root
# working copy for the course folder (only on the author's machine)
HW2_AI = os.environ.get("AIC_HW2_COPY_DIR", "")   # 設了才另外複製一份到那個資料夾
OUT = os.path.join(ROOT, "AIC-HW2_%s.icproj.json" % TAG)
f = Schematic("project-aic-hw2-" + TAG.lower(), "AIC HW2 " + TAG, TAG,
              out_proj=OUT,
              out_svg=os.path.join(HERE, "preview_aic_hw2_%s.svg" % TAG.lower()))

BL, BR, BT, BB, BCX = 480, 640, 130, 330, 560      # comparator box
Y_VIN, Y_VIP, Y_VON, Y_VOP = 170, 250, 200, 260
X_CLK, X_VSS = 520, 600


# ---------------------------------------------------------------- placement
def vsrc(iid, x, y, rotation=0):
    f.place(iid, "voltage-source", x, y, rotation=rotation,
            extra={"schematicReference": iid})


# upright sources only: a rotated source turns its own '-' glyph into a bar
vsrc("V3", 240, 210)             # '+' (240,190)  '-' (240,230)
vsrc("V2", 320, 290)             # '+' (320,270)  '-' (320,310)
vsrc("V0", 280, 370)             # '+' (280,350)  '-' (280,390)
vsrc("V4", 500, 70)              # '+' (500,50)   '-' (500,90)
vsrc("V1", X_CLK, 390)           # '+' (520,370)  '-' (520,410)
f.gnd("G0", 280, 400)
f.gnd("G4", 500, 100)
f.gnd("G1", X_CLK, 420)
f.gnd("GS", X_VSS, 350)
f.passive("C1", "capacitor", 700, 170, "C_1")   # pin2 (620,190), ground above
f.passive("C0", "capacitor", 700, 290, "C_0")   # pin1 (620,270), ground below
f.place("GC1", "ground", 700, 140, rotation=180,
        extra={"schematicReference": "GC1"})    # pin (620,150) = C1 '1'
f.gnd("GC0", 700, 320)                          # pin (620,310) = C0 '2'
f.port("PVON", 750, Y_VON, mirror="x")          # pin (740,200)
f.port("PVOP", 750, Y_VOP, mirror="x")          # pin (740,260)
for iid, pin, xy in (("V3", "+", (240, 190)), ("V2", "+", (320, 270)),
                     ("V0", "+", (280, 350)), ("V4", "+", (500, 50)),
                     ("V1", "+", (X_CLK, 370)), ("PVON", "P", (740, Y_VON))):
    assert f.pin(iid, pin) == xy, (iid, pin, f.pin(iid, pin))

f.rect("box-cmp", BCX, (BT + BB) // 2, BR - BL, BB - BT)

# --------------------------------------------------------------- junctions
for jid, net, x, y in (
        ("JCM", "net-cm", 280, 330),
        ("JE-VIN", "net-vin", BL, Y_VIN), ("JE-VIP", "net-vip", BL, Y_VIP),
        ("JE-VDD", "net-vdd", BCX, BT), ("JE-CLK", "net-clk", X_CLK, BB),
        ("JE-VSS", "net-vss", X_VSS, BB),
        ("JE-VON", "net-von", BR, Y_VON), ("JON", "net-von", 700, Y_VON),
        ("JE-VOP", "net-vop", BR, Y_VOP), ("JOP", "net-vop", 700, Y_VOP)):
    f.junction(jid, net, x, y)

# -------------------------------------------------------------------- nets
f.net("net-vin", [("V3", "+")])
f.net("net-vip", [("V2", "+")])
f.net("net-cm", [("V3", "-"), ("V2", "-"), ("V0", "+")])
f.net("net-vdd", [("V4", "+")])
f.net("net-clk", [("V1", "+")])
f.net("net-gnd-1", [("V0", "-"), ("G0", "0")])
f.net("net-gnd-2", [("V4", "-"), ("G4", "0")])
f.net("net-gnd-3", [("V1", "-"), ("G1", "0")])
f.net("net-vss", [("GS", "0")])
f.net("net-von", [("C1", "2"), ("PVON", "P")])
f.net("net-vop", [("C0", "1"), ("PVOP", "P")])
f.net("net-gc1", [("C1", "1"), ("GC1", "0")])
f.net("net-gc0", [("C0", "2"), ("GC0", "0")])

# ------------------------------------------------------------------ routes
T, Jn = f.term, f.jn
f.route("r-vin", "net-vin", T("V3", "+"), [("bend", 240, Y_VIN), ("to", Jn("JE-VIN"))])
f.route("r-vip", "net-vip", T("V2", "+"), [("bend", 320, Y_VIP), ("to", Jn("JE-VIP"))])
f.route("r-cm3", "net-cm", T("V3", "-"), [("bend", 240, 330), ("to", Jn("JCM"))])
f.route("r-cm2", "net-cm", T("V2", "-"), [("bend", 320, 330), ("to", Jn("JCM"))])
f.route("r-cm0", "net-cm", Jn("JCM"), [("to", T("V0", "+"))])
f.route("r-vdd", "net-vdd", Jn("JE-VDD"), [("bend", BCX, 50), ("to", T("V4", "+"))])
f.route("r-clk", "net-clk", T("V1", "+"), [("to", Jn("JE-CLK"))])
f.route("r-vss", "net-vss", Jn("JE-VSS"), [("to", T("GS", "0"))])
f.route("r-on1", "net-von", Jn("JE-VON"), [("to", Jn("JON"))])
f.route("r-on2", "net-von", Jn("JON"), [("to", T("C1", "2"))])
f.route("r-on3", "net-von", Jn("JON"), [("to", T("PVON", "P"))])
f.route("r-op1", "net-vop", Jn("JE-VOP"), [("to", Jn("JOP"))])
f.route("r-op2", "net-vop", Jn("JOP"), [("to", T("C0", "1"))])
f.route("r-op3", "net-vop", Jn("JOP"), [("to", T("PVOP", "P"))])

# ------------------------------------------------------------- annotations
f.terminal("t-von", "V_on", "net-von", "output", ["PVON"])
f.terminal("t-vop", "V_op", "net-vop", "output", ["PVOP"])
f.port_label("PVON", "t-von", LABEL_PORT, 5, "start")
f.port_label("PVOP", "t-vop", LABEL_PORT, 5, "start")

if MODE == "pattern":
    w3 = w2 = "10 patterns"
else:
    w2 = "+20 " + chr(0x2192) + " " + chr(0x2212) + "20 mV"
    w3 = chr(0x2212) + "20 " + chr(0x2192) + " +20 mV"
txt = [
    # pin names inside the box, and its title
    ("p-vin", BL + 8, Y_VIN + 5, "start", "VIN", None),
    ("p-vip", BL + 8, Y_VIP + 5, "start", "VIP", None),
    ("p-vdd", BCX, BT + 20, "middle", "VDD", None),
    ("p-clk", X_CLK, BB - 8, "middle", "CLK", None),
    ("p-vss", X_VSS, BB - 8, "middle", "VSS", None),
    ("p-von", BR - 8, Y_VON + 5, "end", "VON", None),
    ("p-vop", BR - 8, Y_VOP + 5, "end", "VOP", None),
    ("t-cmp", BR, BT - 8, "end", "CMP", None),      # above the top edge, right (user)
    # source values
    ("v-v3a", 264, 205, "start", "PWL", "V3"),
    ("v-v3b", 264, 225, "start", w3, "V3"),
    ("v-v2a", 344, 285, "start", "PWL", "V2"),
    ("v-v2b", 344, 305, "start", w2, "V2"),
    ("v-v0", 304, 375, "start", "350 mV", "V0"),
    ("v-v4", 476, 75, "end", "800 mV", "V4"),
    ("v-v1a", 496, 375, "end", "pulse", "V1"),
    ("v-v1b", 496, 395, "end", "0 " + chr(0x2192) + " 800 mV", "V1"),
    ("v-v1c", 496, 415, "end", "tr = 10 ps", "V1"),
    ("v-c1", 713, 175, "start", "20 fF", "C1"),
    ("v-c0", 713, 295, "start", "20 fF", "C0")]
for tid, x, y, al, s, owner in txt:
    f.text(tid, x, y, al, plain(s), owner)
    if tid == "t-cmp":                       # title one size up (user)
        f.drafting[-1]["styleOverride"]["sizeScale"] *= 1.4

f.build(long_haul={"r-vin", "r-vip", "r-cm3", "r-cm2", "r-vdd", "r-on1",
                   "r-op1"},
        extra_evidence=[],
        rail_ends={"JE-VIN", "JE-VIP", "JE-VDD", "JE-CLK", "JE-VSS",
                   "JE-VON", "JE-VOP"},
        viewbox=(180, 20, 640, 440),
        expect_differ={t[0] for t in txt})   # plain text on purpose (SOP 4)

if HW2_AI and os.path.isdir(HW2_AI):
    shutil.copyfile(OUT, os.path.join(HW2_AI, os.path.basename(OUT)))
