import contextlib
import glob
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolkit"))

import autoplace  # noqa: E402
import icproj  # noqa: E402
import netlist_io  # noqa: E402

DECK = ROOT / "toolkit" / "decks" / "razavi" / "cs-resistive-load.cir"
HAVE_SYMBOLS = bool(glob.glob(os.path.join(icproj.SYMDIR, "*.json")))


@unittest.skipUnless(HAVE_SYMBOLS, "run `python -m toolkit setup` first")
class PlaceDeckTests(unittest.TestCase):
    def draw(self, folder, serial):
        proj = os.path.join(folder, "cs.icproj.json")
        svg = os.path.join(folder, "preview_cs.svg")
        env = {"AC_SERIAL": "1" if serial else "0"}
        with mock.patch.dict(os.environ, env), \
                contextlib.redirect_stdout(io.StringIO()):
            autoplace.place_deck(str(DECK), out_proj=proj, out_svg=svg,
                                 verbose=False)
        with open(proj, "rb") as a, open(svg, "rb") as b:
            return a.read(), b.read()

    def test_parallel_descents_draw_what_serial_descents_draw(self):
        # place_deck forks independent descents; the memo tables are merged
        # back in job order, so the drawing must be byte-for-byte the same
        with tempfile.TemporaryDirectory() as a, \
                tempfile.TemporaryDirectory() as b:
            self.assertEqual(self.draw(a, serial=True),
                             self.draw(b, serial=False))

    def test_search_writes_only_the_winner(self):
        # candidates are built `dry`: in a serial search every draw happens
        # in this process, and exactly one of them -- the winner -- writes
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(icproj.json, "dump",
                                  wraps=icproj.json.dump) as dump:
            self.draw(d, serial=True)
        self.assertEqual(1, dump.call_count)

    def test_forked_descents_leave_nothing_behind(self):
        # each forked descent works in a private directory and removes it
        before = set(glob.glob(os.path.join(tempfile.gettempdir(),
                                            "ac-descent-*")))
        with tempfile.TemporaryDirectory() as d:
            self.draw(d, serial=False)
            left = set(os.listdir(d))
            self.assertTrue({"cs.icproj.json", "preview_cs.svg"} <= left)
            # the PNG appears only when Chrome is there to render it
            self.assertTrue(left <= {"cs.icproj.json", "preview_cs.svg",
                                     "preview_cs.png"}, left)
        after = set(glob.glob(os.path.join(tempfile.gettempdir(),
                                           "ac-descent-*")))
        self.assertEqual(before, after)
        self.assertFalse(autoplace._DRY[0])



NAND2 = """.title t
.global VDD
.subckt NAND2 a b out
.iodir a=input b=input out=output
MP1 out a VDD VDD pmos
MP2 out b VDD VDD pmos
MN1 out a mid 0 nmos
MN2 mid b 0 0 nmos
.ends
"""


class SplitGateInputTests(unittest.TestCase):
    def split(self, text):
        return autoplace._split_gate_inputs(netlist_io.parse(text))

    def test_nand_inputs_get_one_port_per_gate(self):
        c = self.split(NAND2)
        self.assertEqual({"a__2": "a", "b__2": "b"}, c.alias)
        self.assertEqual("a__2", c.by_ref["MN1"].pins["G"])
        self.assertEqual("a", c.by_ref["MP1"].pins["G"])
        names = [nm for nd, nm, di in c.ports if di == "input"]
        self.assertEqual(4, len(names))

    def test_only_complementary_gates_are_split(self):
        inverter = NAND2.replace("a b out", "a out").replace(
            "a=input b=input", "a=input").replace(
            "MP2 out b VDD VDD pmos\n", "").replace(
            "MN1 out a mid 0 nmos\nMN2 mid b 0 0 nmos", "MN1 out a 0 0 nmos")
        self.assertEqual({}, self.split(inverter).alias)
        with_r = NAND2.replace(".ends", "R1 out 0\n.ends")
        self.assertEqual({}, self.split(with_r).alias)
        tied = NAND2.replace("MN2 mid b 0 0 nmos", "MN2 mid b a 0 nmos")
        self.assertEqual({}, self.split(tied).alias)
        with mock.patch.dict(os.environ, {"AC_PORTCOPY": "0"}):
            self.assertEqual({}, self.split(NAND2).alias)



class HintTests(unittest.TestCase):
    def read(self, text, deck=NAND2):
        c = netlist_io.parse(deck)
        with tempfile.NamedTemporaryFile("w", suffix=".hints",
                                         delete=False) as f:
            f.write(text)
        self.addCleanup(os.remove, f.name)
        return autoplace._read_hints(c, f.name)

    def test_groups_and_portside_are_read(self):
        c = self.read("* comment\n.group up MP1 MP2\n.group dn MN1 MN2\n"
                      ".portside a top\n")
        self.assertEqual([("up", ["MP1", "MP2"]), ("dn", ["MN1", "MN2"])],
                         c.groups)
        self.assertEqual({"a": "top"}, c.portside)

    def test_row_below_names_a_group(self):
        c = self.read(".group dn MN1 MN2\n.row dn below\n")
        self.assertEqual(["dn"], c.below)
        with self.assertRaises(ValueError):
            self.read(".group dn MN1 MN2\n.row up below\n")

    def test_unknown_names_are_errors(self):
        with self.assertRaises(ValueError):
            self.read(".group up MP1 MX9\n")
        with self.assertRaises(ValueError):
            self.read(".portside nope top\n")
        with self.assertRaises(ValueError):
            self.read(".stage 1\n")

    def test_bench_reads_no_hints(self):
        c = autoplace._read_hints(netlist_io.parse(NAND2), None)
        self.assertEqual(([], {}, []), (c.groups, c.portside, c.below))



FOLDED = """.title t
.global VDD
.subckt FC b4 b3 b2 b1 b5 in1 in2 ol or
.iodir b4=input b3=input b2=input b1=input b5=input in1=input in2=input ol=output or=output
M7 fl b4 VDD VDD pmos
M8 fr b4 VDD VDD pmos
M5 ol b3 fl VDD pmos
M6 or b3 fr VDD pmos
M3 ol b2 xl 0 nmos
M4 or b2 xr 0 nmos
M9 xl b1 0 0 nmos
M10 xr b1 0 0 nmos
M1 fl in1 tail 0 nmos
M2 fr in2 tail 0 nmos
M11 tail b5 0 0 nmos
.ends
"""


class AnalyzeTests(unittest.TestCase):
    def test_folded_cascode_is_recognised(self):
        groups, portside, own = autoplace._folded_cascode(
            netlist_io.parse(FOLDED))
        self.assertEqual(("input", ["M1", "M11", "M2"]), groups[0])
        self.assertEqual({"M7", "M5", "M3", "M9"}, set(groups[1][1]))
        self.assertEqual({"b1", "b2", "b3", "b4"}, set(portside))
        self.assertEqual({"M11"}, own)

    def test_symmetric_biases_come_in_from_the_top(self):
        deck = (ROOT / "toolkit" / "decks" / "new"
                / "telescopic-cascode.cir").read_text(encoding="utf-8")
        c = netlist_io.parse(deck)
        c.mirror = autoplace._mirror_map(c)
        autoplace._read_hints(c, None)
        autoplace._analyze(c)
        self.assertEqual({"vb2", "vb3", "vb4"}, set(c.portside))
        self.assertIsNone(autoplace._folded_cascode(c))

    def test_other_circuits_are_left_alone(self):
        self.assertIsNone(autoplace._folded_cascode(netlist_io.parse(NAND2)))
        same_stack = FOLDED.replace("M2 fr in2", "M2 fl in2")
        self.assertIsNone(autoplace._folded_cascode(
            netlist_io.parse(same_stack)))


T_FEEDBACK = """.title non-inverting amplifier with T feedback (Razavi 8.48)
.subckt T out
.iodir out=output
XOA in a out opamp-inputs-swapped
.alias XOA OA
VIN in 0
R1 out b
R2 a 0
R3 b a
R4 b 0
.ends
"""


@unittest.skipUnless(HAVE_SYMBOLS, "run `python -m toolkit setup` first")
class InpFirstTests(unittest.TestCase):
    def column_x(self, inpfirst):
        c = netlist_io.parse(T_FEEDBACK)
        c.mirror = autoplace._mirror_map(c)
        autoplace._read_hints(c, None)
        autoplace._analyze(c)
        style = dict(autoplace.STYLE0, inpfirst=inpfirst)
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {"AC_FAST": "1"}), \
                contextlib.redirect_stdout(io.StringIO()):
            p = autoplace.Placer(c, os.path.join(tmp, "t.icproj.json"),
                                 os.path.join(tmp, "t.svg"), style=style)
            p.run(verbose=False)
        return dict((k, v[1]) for k, v in p.f.placed.items())

    def test_inverting_input_shunt_moves_in_front_of_the_op_amp(self):
        x = self.column_x(1)
        self.assertLess(x["R2"], x["OA"])

    def test_off_by_default(self):
        x = self.column_x(0)
        self.assertGreater(x["R2"], x["OA"])


TWO_STAGES = """.title two inverting stages
.subckt S out
.iodir out=output
XOA1 0 a x opamp
.alias XOA1 OA1
XOA2 0 b out opamp
.alias XOA2 OA2
VIN in 0
R1 in a
RF1 a x
R2 x b
RF2 b out
.ends
"""


@unittest.skipUnless(HAVE_SYMBOLS, "run `python -m toolkit setup` first")
class AmpDropTests(unittest.TestCase):
    def y_of(self, **style):
        c = netlist_io.parse(TWO_STAGES)
        c.mirror = autoplace._mirror_map(c)
        autoplace._read_hints(c, None)
        autoplace._analyze(c)
        st = dict(autoplace.STYLE0, **style)
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {"AC_FAST": "1"}), \
                contextlib.redirect_stdout(io.StringIO()):
            p = autoplace.Placer(c, os.path.join(tmp, "t.icproj.json"),
                                 os.path.join(tmp, "t.svg"), style=st)
            p.run(verbose=False)
        return p.f.placed["OA2"][2]

    def test_an_amplifier_can_hang_one_step_lower(self):
        self.assertEqual(self.y_of() + 10,
                         self.y_of(vdrop=(("OA2", 10),)))


if __name__ == "__main__":
    unittest.main()
