# -*- coding: utf-8 -*-
"""Two-stage latched comparator, 19 MOS (SOP lane 3a: a non-Razavi source).

Topology and every `mirror` came from `python scan_figure.py <shot>`: the source
figure is not razavi-v1, so the scanner's generic path found the devices as
paired vertical strokes (19/19, verified device by device against the image).
PMOS/NMOS is the one reading the scanner does NOT give -- it comes from the
bubble on the gate, which in this figure matches "source touches VDD".

Circuit: M1/M2 diode stack biases M4, which loads the diode-connected M3; M3
mirrors into M_B, the tail source of the PMOS input pair M7/M11.  M8/M12 are
diode loads, M9/M10 the cross-coupled positive feedback.  The left node drives
M6 (diode load M5) into M13's gate and the right node drives M14 directly, so
the differential pair converts to single-ended at M13/M14; two inverters
(M15/M16, M17/M18) buffer it out to V_OUT with a 0.1 pF load.

Layout is the user's, corrected in the editor on 2026-08-29 and read back here.
Three things changed from the first attempt, all now enforced by the toolkit:

  * the M5 -> M13 bias line ran at y=210, straight through M7's and M11's
    source pins and along M5's own bottom edge, and the V_IN- port's pin landed
    exactly on M5's gate wire -- four components reading as connected to a net
    they are not on.  It now runs at y=190, above the input pair.  `icproj`
    grew a component-to-wire clearance check for this whole class of fault.
  * every ground now sits on one row (y=350), the load cap's included.
  * the cross-coupled drains are drawn with two construction lines, so the
    figure gets the textbook X instead of the orthogonal staircase.
"""
import os
from icproj import Schematic, name, plain, LABEL_PORT

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
f = Schematic(
    "project-comparator-19",
    "Latched comparator with cross-coupled load and inverter output",
    "Comparator19",
    out_proj=os.path.join(OUT, "Comparator_latched_19T.icproj.json"),
    out_svg=os.path.join(HERE, "preview_comparator19.svg"))

# ---------------------------------------------------------------- placement
# rows 100 VDD | 140 M3/M_B | 190 M1,M5,M13,M15,M17 + the bias line
#      230 M7,M11 (inputs) | 270 M6,M14,M16,M18 + both comparator buses
#      320 the NMOS row | 350 every ground, one row
for iid, kind, cx, cy, mir, lab in (
        ("M1", "pmos", 120, 190, "x", "M_1"),
        ("M2", "nmos", 120, 320, "x", "M_2"),
        ("M3", "pmos", 210, 140, "x", "M_3"),
        ("M4", "nmos", 190, 320, "none", "M_4"),
        ("M5", "pmos", 270, 190, "x", "M_5"),
        ("M6", "nmos", 270, 270, "x", "M_6"),
        ("M7", "pmos", 360, 230, "none", "M_7"),
        ("M8", "nmos", 380, 320, "x", "M_8"),
        ("M9", "nmos", 440, 320, "none", "M_9"),
        ("MB", "pmos", 480, 140, "none", "M_B"),
        ("M10", "nmos", 550, 320, "x", "M_10"),
        ("M11", "pmos", 630, 230, "x", "M_11"),
        ("M12", "nmos", 610, 320, "none", "M_12"),
        ("M13", "pmos", 710, 190, "none", "M_13"),
        ("M14", "nmos", 710, 270, "none", "M_14"),
        ("M15", "pmos", 790, 190, "none", "M_15"),
        ("M16", "nmos", 790, 270, "none", "M_16"),
        ("M17", "pmos", 870, 190, "none", "M_17"),
        ("M18", "nmos", 870, 270, "none", "M_18")):
    f.mos(iid, kind, cx, cy, mir, lab)

f.passive("CL", "capacitor", 930, 300, "C_L")
for iid, x in (("G2", 110), ("G4", 200), ("G6", 260), ("G8", 370),
               ("G9", 450), ("G10", 540), ("G12", 620), ("G14", 720),
               ("G16", 800), ("G18", 880), ("GC", 930)):
    f.gnd(iid, x, 350)
f.port("VINN", 340, 230)
f.port("VINP", 650, 230, mirror="x")
f.port("VOUT", 960, 230, mirror="x")

# ---------------------------------------------------------------- junctions
RAIL = [90, 110, 200, 260, 490, 720, 800, 880, 900]
J = [("jvdd-%d" % i, "net-power-vdd", x, 100) for i, x in enumerate(RAIL)]
J[0] = ("jvdd-start", "net-power-vdd", RAIL[0], 100)
J[-1] = ("jvdd-end", "net-power-vdd", RAIL[-1], 100)
for jid, net, x, y in J + [
        ("JB1A", "net-b1", 110, 230),    # M1 gate tie lands here
        ("JB1B", "net-b1", 110, 280),    # M2 gate tie leaves here
        ("JB1C", "net-b1", 150, 320),    # M2 gate / M4 gate
        ("JB2A", "net-b2", 200, 170),    # M3 drain / its own gate tie
        ("JB2B", "net-b2", 240, 140),    # the M3 - M_B mirror line
        ("JTAIL", "net-tail", 490, 210),  # M_B drain tees into the tail
        ("JLG", "net-left", 410, 320),    # the fan-out to M8/M9 gates
        ("JRG", "net-right", 580, 320),   # the fan-out to M10/M12
        ("JB3", "net-b3", 260, 230),     # M5 drain / M6 drain
        ("JB3G", "net-b3", 300, 190),    # M5 gate; the bias line to M13
        ("JL1", "net-left", 370, 270),   # left bus: M7/M8 drains
        ("JL2", "net-left", 410, 270),   # left bus: M8/M9 gates
        ("JX1", "net-left", 450, 270),   # the four ends the construction
        ("JX3", "net-x9", 450, 290),     # lines pick up -- see the note in
        ("JX2", "net-right", 540, 270),  # the nets section
        ("JX4", "net-x10", 540, 290),
        ("JR1", "net-right", 580, 270),  # right bus: M10/M12 gates
        ("JR2", "net-right", 620, 270),  # right bus: M11/M12 drains
        ("JO1", "net-out1", 720, 230),
        ("JG1", "net-out1", 770, 230),   # inverter 1 gate tee
        ("JO2", "net-out2", 800, 230),
        ("JG2", "net-out2", 850, 230),   # inverter 2 gate tee
        ("JO3", "net-vout", 880, 230),
        ("JO4", "net-vout", 930, 230)]:
    f.junction(jid, net, x, y)

# ---------------------------------------------------------------- nets
PB = [(m, "B") for m in ("M1", "M3", "M5", "M7", "M11", "MB", "M13", "M15",
                         "M17")]
f.net("net-power-vdd", [("M1", "S"), ("M3", "S"), ("M5", "S"), ("MB", "S"),
                        ("M13", "S"), ("M15", "S"), ("M17", "S")] + PB)
f.net("net-b1", [("M1", "D"), ("M1", "G"), ("M2", "D"), ("M2", "G"),
                 ("M4", "G")])
f.net("net-b2", [("M3", "D"), ("M3", "G"), ("M4", "D"), ("MB", "G")])
f.net("net-tail", [("MB", "D"), ("M7", "S"), ("M11", "S")])
f.net("net-b3", [("M5", "D"), ("M5", "G"), ("M6", "D"), ("M13", "G")])
# The cross-coupling is DRAWN with two construction lines (SOP §3E): routes
# cannot go diagonally.  Those do not conduct, so M9's and M10's drains stay
# on nets of their own -- fine for a figure, which is all this is for.
f.net("net-left", [("M6", "G"), ("M7", "D"), ("M8", "D"), ("M8", "G"),
                   ("M9", "G")])
f.net("net-right", [("M10", "G"), ("M11", "D"), ("M12", "D"), ("M12", "G"),
                    ("M14", "G")])
f.net("net-x9", [("M9", "D")])
f.net("net-x10", [("M10", "D")])
f.net("net-out1", [("M13", "D"), ("M14", "D"), ("M15", "G"), ("M16", "G")])
f.net("net-out2", [("M15", "D"), ("M16", "D"), ("M17", "G"), ("M18", "G")])
f.net("net-vout", [("M17", "D"), ("M18", "D"), ("CL", "1"), ("VOUT", "P")])
f.net("net-inn", [("VINN", "P"), ("M7", "G")])
f.net("net-inp", [("VINP", "P"), ("M11", "G")])
NB = [(m, "B") for m in ("M2", "M4", "M6", "M8", "M9", "M10", "M12", "M14",
                         "M16", "M18")]
f.net("net-gnd-1", [("M2", "S"), ("G2", "0"), ("M4", "S"), ("G4", "0"),
                    ("M6", "S"), ("G6", "0"), ("M8", "S"), ("G8", "0"),
                    ("M9", "S"), ("G9", "0"), ("M10", "S"), ("G10", "0"),
                    ("M12", "S"), ("G12", "0"), ("M14", "S"), ("G14", "0"),
                    ("M16", "S"), ("G16", "0"), ("M18", "S"), ("G18", "0"),
                    ("CL", "2"), ("GC", "0")] + NB)

# ---------------------------------------------------------------- routes
T, Jn = f.term, f.jn
f.rail("net-power-vdd", 100, RAIL)
for iid, x in (("M1", 110), ("M3", 200), ("M5", 260), ("MB", 490),
               ("M13", 720), ("M15", 800), ("M17", 880)):
    f.route("r-vdd-%s" % iid, "net-power-vdd",
            Jn(f._jat(x, 100)), [("to", T(iid, "S"))])

# bias branch 1: M1 and M2 both diode-connected onto one node
f.route("r-b1-a", "net-b1", T("M1", "D"), [("to", Jn("JB1A"))])
f.route("r-b1-g1", "net-b1", T("M1", "G"), [("bend", 160, 190),
                                            ("bend", 160, 230),
                                            ("to", Jn("JB1A"))])
f.route("r-b1-b", "net-b1", Jn("JB1A"), [("to", Jn("JB1B"))])
f.route("r-b1-c", "net-b1", Jn("JB1B"), [("to", T("M2", "D"))])
f.route("r-b1-g2", "net-b1", Jn("JB1B"), [("bend", 150, 280),
                                          ("to", Jn("JB1C"))])
f.route("r-b1-g2b", "net-b1", Jn("JB1C"), [("to", T("M2", "G"))])
f.route("r-b1-g4", "net-b1", Jn("JB1C"), [("to", T("M4", "G"))])

# bias branch 2: diode-connected M3 mirrors into M_B
f.route("r-b2-a", "net-b2", T("M3", "D"), [("to", Jn("JB2A"))])
f.route("r-b2-b", "net-b2", Jn("JB2A"), [("to", T("M4", "D"))])
f.route("r-b2-c", "net-b2", Jn("JB2A"), [("bend", 240, 170),
                                         ("to", Jn("JB2B"))])
f.route("r-b2-g3", "net-b2", Jn("JB2B"), [("to", T("M3", "G"))])
f.route("r-b2-gb", "net-b2", Jn("JB2B"), [("to", T("MB", "G"))])

f.route("r-tail-b", "net-tail", T("MB", "D"), [("to", Jn("JTAIL"))])
f.route("r-tail-7", "net-tail", Jn("JTAIL"), [("to", T("M7", "S"))])
f.route("r-tail-11", "net-tail", Jn("JTAIL"), [("to", T("M11", "S"))])

# Second-stage load: diode-connected M5 over M6, driving M13's gate.  The long
# bias line runs at y=190, ABOVE the input pair -- at 210 it lay on M7's and
# M11's source pins and read as if it connected to them.
f.route("r-b3-a", "net-b3", T("M5", "D"), [("to", Jn("JB3"))])
f.route("r-b3-b", "net-b3", Jn("JB3"), [("to", T("M6", "D"))])
f.route("r-b3-g5", "net-b3", T("M5", "G"), [("to", Jn("JB3G"))])
f.route("r-b3-d", "net-b3", Jn("JB3G"), [("bend", 300, 210),
                                         ("to", T("M5", "D"))])
f.route("r-b3-13", "net-b3", Jn("JB3G"), [("to", T("M13", "G"))])

# left bus
f.route("r-l-7", "net-left", T("M7", "D"), [("to", Jn("JL1"))])
f.route("r-l-8", "net-left", Jn("JL1"), [("to", T("M8", "D"))])
f.route("r-l-6", "net-left", Jn("JL1"), [("to", T("M6", "G"))])
f.route("r-l-bus", "net-left", Jn("JL1"), [("to", Jn("JL2"))])
f.route("r-l-gr", "net-left", Jn("JL2"), [("to", Jn("JLG"))])
f.route("r-l-g8", "net-left", Jn("JLG"), [("to", T("M8", "G"))])
f.route("r-l-g9", "net-left", Jn("JLG"), [("to", T("M9", "G"))])
f.route("r-l-x", "net-left", Jn("JL2"), [("to", Jn("JX1"))])

# right bus
f.route("r-r-11", "net-right", T("M11", "D"), [("to", Jn("JR2"))])
f.route("r-r-12", "net-right", Jn("JR2"), [("to", T("M12", "D"))])
f.route("r-r-14", "net-right", Jn("JR2"), [("to", T("M14", "G"))])
f.route("r-r-bus", "net-right", Jn("JR2"), [("to", Jn("JR1"))])
f.route("r-r-gr", "net-right", Jn("JR1"), [("to", Jn("JRG"))])
f.route("r-r-g10", "net-right", Jn("JRG"), [("to", T("M10", "G"))])
f.route("r-r-g12", "net-right", Jn("JRG"), [("to", T("M12", "G"))])
f.route("r-r-x", "net-right", Jn("JR1"), [("to", Jn("JX2"))])

# the two drain stubs, and the X itself
f.route("r-x9", "net-x9", T("M9", "D"), [("to", Jn("JX3"))])
f.route("r-x10", "net-x10", T("M10", "D"), [("to", Jn("JX4"))])
f.construction("xc-1", 450, 270, 540, 290)
f.construction("xc-2", 540, 270, 450, 290)

# output chain
for n, jid, jg, mp, mn, gp, gn in (
        ("net-out1", "JO1", "JG1", "M13", "M14", "M15", "M16"),
        ("net-out2", "JO2", "JG2", "M15", "M16", "M17", "M18")):
    f.route("r-%s-p" % jid, n, T(mp, "D"), [("to", Jn(jid))])
    f.route("r-%s-n" % jid, n, Jn(jid), [("to", T(mn, "D"))])
    f.route("r-%s-t" % jid, n, Jn(jid), [("to", Jn(jg))])
    f.route("r-%s-gp" % jid, n, Jn(jg), [("to", T(gp, "G"))])
    f.route("r-%s-gn" % jid, n, Jn(jg), [("to", T(gn, "G"))])
f.route("r-o3-p", "net-vout", T("M17", "D"), [("to", Jn("JO3"))])
f.route("r-o3-n", "net-vout", Jn("JO3"), [("to", T("M18", "D"))])
f.route("r-o3-j", "net-vout", Jn("JO3"), [("to", Jn("JO4"))])
f.route("r-o3-c", "net-vout", Jn("JO4"), [("to", T("CL", "1"))])
f.route("r-o3-p2", "net-vout", Jn("JO4"), [("to", T("VOUT", "P"))])
f.route("r-cl-gnd", "net-gnd-1", T("CL", "2"), [("to", T("GC", "0"))])

f.route("r-inn", "net-inn", T("VINN", "P"), [("to", T("M7", "G"))])
f.route("r-inp", "net-inp", T("VINP", "P"), [("to", T("M11", "G"))])
# Every source but M6/M14/M16/M18 sits pin-on-pin on its ground symbol.
for iid, g in (("M6", "G6"), ("M14", "G14"), ("M16", "G16"), ("M18", "G18")):
    f.route("r-gnd-%s" % iid, "net-gnd-1", T(iid, "S"), [("to", T(g, "0"))])

f.terminal("terminal-inn", "V_IN-", "net-inn", "input", ["VINN"])
f.terminal("terminal-inp", "V_IN+", "net-inp", "input", ["VINP"])
f.terminal("terminal-vout", "V_OUT", "net-vout", "output", ["VOUT"])

# ---------------------------------------------------------------- annotations
for iid in ("M1", "M2", "M3", "M5", "M6", "M8", "M10", "M11"):
    f.inst_label(iid, -18, 5, "end")      # mirrored: ink on the left
for iid in ("M4", "M7", "M9", "MB", "M12"):
    f.inst_label(iid, 18, 5, "start")
# The inverter chain sits column-on-column, so its labels take the wide offset
# that drops them into the gap before the next stage.
for iid in ("M13", "M14", "M15", "M16", "M17", "M18"):
    f.inst_label(iid, 43, 5, "end")
f.port_label("VINN", "terminal-inn", -15, 5, "end")
f.port_label("VINP", "terminal-inp", LABEL_PORT, 5, "start")
f.port_label("VOUT", "terminal-vout", LABEL_PORT, 5, "start")
f.power_label("label-vdd", "net-power-vdd", "jvdd-end", 12, 6, "V_DD")
# The source figure prints only the value on the load cap, no device name.
f.text("v-cl", 943, 305, "start", plain("0.1 pF"), owner="CL")

f.build(long_haul={
            "r-vdd-rail-1", "r-vdd-rail-2", "r-vdd-rail-3", "r-vdd-rail-4",
            "r-vdd-rail-5", "r-vdd-rail-6",          # the V_DD rail itself
            "r-vdd-M1", "r-vdd-M5", "r-vdd-M13", "r-vdd-M15", "r-vdd-M17",
            "r-b1-b", "r-b1-g1", "r-b1-g2",          # the two diode ties
            "r-b2-b", "r-b2-c", "r-b2-gb",           # M3 -> M_B mirror line
            "r-tail-7", "r-tail-11", "r-tail-b",     # the tail bus
            "r-b3-13",                               # second stage to M13
            "r-l-bus", "r-r-bus", "r-l-x", "r-r-x",  # the comparator buses
            "r-r-gr", "r-l-gr",                      # and their gate risers
            "r-r-14",
            "r-gnd-M6", "r-gnd-M14", "r-gnd-M16", "r-gnd-M18",
            "r-JO1-t", "r-JO2-t",
            "r-l-6",            # 80: the left bus back to M6's gate
            "r-o3-j", "r-o3-c"},  # 50: V_OUT out to the load cap
        # JX1..JX4 are the ends the construction lines pick up: one route each,
        # the same exemption the rail end caps get.
        rail_ends={"jvdd-start", "jvdd-end", "JX1", "JX2", "JX3", "JX4"},
        viewbox=(60, 85, 970, 300),
        # plain text on purpose (values / block titles): the
        # editor's generator italicises everything, we follow the
        # textbook page instead -- SOP 4
        expect_differ=set())
