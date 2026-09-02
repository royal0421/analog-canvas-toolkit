# -*- coding: utf-8 -*-
"""Small-signal model of a two-stage BJT amplifier, from a hand drawing.

Lane 3b (hand-drawn input).  `scan_figure.py` is NO USE here: on a pen-on-grid
photo it reads the handwriting as junction dots (44 of them) and the strokes as
wire runs.  The topology below was read by eye from 3x crops.  Do NOT stop to
confirm the reading with the user first (his ruling, 2026-08-30): draw it,
he corrects the picture.

Drawn exactly as the page has it, including the second controlled source
sitting between the ground bus and a second ground symbol (user asked for a
faithful copy, 2026-08-30).
"""
import os
from icproj import Schematic, name, plain

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-handdrawn-2stage-ss",
    "Two-stage BJT amplifier -- small-signal model",
    "TwoStageSS",
    out_proj=os.path.join(OUT, "Handdrawn_two-stage-BJT_small-signal.icproj.json"),
    out_svg=os.path.join(HERE, "preview_2stagess.svg"))

# ---------------------------------------------------------------- placement
#   cols 100 V_in | 140 r_pi1 | 200 R_E | 260 source 1 | 330 R_C
#        400 r_pi2 | 480 V_out | 520 source 2 | 590 its ground
#   rows 100 top rail and the V_in stub | 140 r_pi1 | 150 the sideways
#        ground stub | 190 emitter bus | 210 ground bus | 230 R_E
#        260 grounds
# R_E hangs from the MIDDLE of the emitter bus, as the page draws it --
# when the hand drawing is clear about a shape, follow it (user, 2026-08-30)
f.port("VIN", 100, 100)
f.port("VOUT", 480, 100, mirror="x")
f.passive("RP1", "resistor", 140, 140, "r_\u03c01")
f.passive("RE", "resistor", 200, 230, "R_E")
f.passive("RC", "resistor", 330, 150, "R_C")
f.passive("RP2", "resistor", 400, 160, "r_\u03c02")
# the page labels neither source; they still need a netlist name, so give
# them one and simply draw no label
f.isrc("IS1", 260, 140, "I_1")
f.isrc("IS2", 520, 180, "I_2")
f.gnd("GE", 200, 260)
f.gnd("GC", 330, 180)
f.gnd("GP2", 460, 260)
# rotation 270 puts the pin on the LEFT and the body to the right, which is
# how the page draws this one -- lying on its side (SOP 3G, trap 3).
# Its stub rides the row half way between the top rail (100) and the ground
# bus (210): a sideways ground goes in the MIDDLE of the band it sits in,
# not hugging the top (user, 2026-08-30).
f.place("GS", "ground", 590, 150, rotation=270,
        extra={"schematicReference": "GS"})

# ---------------------------------------------------------------- junctions
for jid, net, x, y in (("JC1", "net-c", 260, 100),
                       ("JC2", "net-c", 330, 100),
                       ("JC3", "net-c", 400, 100),
                       ("JE1", "net-e", 200, 190),
                       ("JE2", "net-e", 260, 190),
                       ("JG1", "net-gnd", 400, 210),
                       ("JG2", "net-gnd", 460, 210),
                       ("JG3", "net-gnd", 520, 210)):
    f.junction(jid, net, x, y)

# -------------------------------------------------------------------- nets
f.net("net-in", [("VIN", "P"), ("RP1", "1")])
f.net("net-e", [("RP1", "2"), ("RE", "1"), ("IS1", "-")])
f.net("net-c", [("IS1", "+"), ("RC", "1"), ("RP2", "1"), ("VOUT", "P")])
# both ends of the second source are on the ground net: that is what the page
# shows, and the user asked for it drawn as-is
f.net("net-gnd", [("RE", "2"), ("GE", "0"), ("RC", "2"), ("GC", "0"),
                  ("RP2", "2"), ("GP2", "0"), ("IS2", "-"), ("IS2", "+"),
                  ("GS", "0")])

# ------------------------------------------------------------------ routes
T, Jn = f.term, f.jn
f.route("r-in", "net-in", T("VIN", "P"),
        [("bend", 140, 100), ("to", T("RP1", "1"))])

f.route("r-e-rp1", "net-e", T("RP1", "2"),
        [("bend", 140, 190), ("to", Jn("JE1"))])
f.route("r-e-re", "net-e", Jn("JE1"), [("to", T("RE", "1"))])
f.route("r-e-bus", "net-e", Jn("JE1"), [("to", Jn("JE2"))])
f.route("r-e-is1", "net-e", Jn("JE2"), [("to", T("IS1", "-"))])

f.route("r-c-is1", "net-c", T("IS1", "+"), [("to", Jn("JC1"))])
f.route("r-c-1", "net-c", Jn("JC1"), [("to", Jn("JC2"))])
f.route("r-c-rc", "net-c", Jn("JC2"), [("to", T("RC", "1"))])
f.route("r-c-2", "net-c", Jn("JC2"), [("to", Jn("JC3"))])
f.route("r-c-rp2", "net-c", Jn("JC3"), [("to", T("RP2", "1"))])
f.route("r-c-out", "net-c", Jn("JC3"), [("to", T("VOUT", "P"))])

f.route("r-g-rp2", "net-gnd", T("RP2", "2"), [("to", Jn("JG1"))])
f.route("r-g-1", "net-gnd", Jn("JG1"), [("to", Jn("JG2"))])
f.route("r-g-gp2", "net-gnd", Jn("JG2"), [("to", T("GP2", "0"))])
f.route("r-g-2", "net-gnd", Jn("JG2"), [("to", Jn("JG3"))])
f.route("r-g-is2", "net-gnd", Jn("JG3"), [("to", T("IS2", "-"))])
f.route("r-g-top", "net-gnd", T("IS2", "+"),
        [("bend", 520, 150), ("to", T("GS", "0"))])
# R_E and R_C sit pin-on-pin on their ground symbols, so neither needs a wire

f.terminal("t-in", "V_in", "net-in", "input", ["VIN"])
f.terminal("t-out", "V_out", "net-c", "output", ["VOUT"])

# ------------------------------------------------------------- annotations
f.port_label("VIN", "t-in", -14, 5, "end")
f.port_label("VOUT", "t-out", 14, 5, "start")
f.inst_label("RP1", 13, 5, "start")
f.inst_label("RE", 13, 5, "start")
f.inst_label("RC", 13, 5, "start")
f.inst_label("RP2", 13, 5, "start")
# V_pi1 with its polarity marks, to the LEFT of r_pi1, as the page has it
f.text("n-vpi1", 104, 145, "end", name("V_\u03c01"), owner="RP1")
f.text("n-plus", 124, 128, "middle", plain("+"), owner="RP1")
f.text("n-minus", 124, 166, "middle", plain("\u2212"), owner="RP1")

f.build(long_haul={"r-e-rp1",      # 60: r_pi1 across to the R_E node
                   "r-e-bus",      # 60: the emitter bus on to source 1
                   "r-c-1",        # 70: rail from source 1 to R_C
                   "r-c-2",        # 70: rail from R_C to r_pi2
                   "r-c-out",      # 70: rail out to the V_out port
                   "r-g-1",        # 60: ground bus under r_pi2
                   "r-g-2",        # 60: ground bus out to source 2
                   "r-g-top"},     # 60: source 2 across to its ground
        extra_evidence=[],
        rail_ends={"JG3"},
        viewbox=(60, 60, 600, 240),
        # plain on purpose: the polarity marks are symbols, not device names
        expect_differ=set())
