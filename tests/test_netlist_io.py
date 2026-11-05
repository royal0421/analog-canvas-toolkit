import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolkit"))

import autoplace  # noqa: E402
import icproj  # noqa: E402
import netlist_io  # noqa: E402

LC = ROOT / "out" / "Diff-amp_LC-load.icproj.json"


class ExportTests(unittest.TestCase):
    def test_lc_load_exports_clean(self):
        # both L_2 run drain -> V_out: two nets, not a shorted inductor
        _c, problems = netlist_io.export_project(str(LC))
        self.assertEqual([], problems)

    def test_names_drawn_as_text_are_exported(self):
        # the second R / L_2 / C_1 / C_2 print their name as drafting text
        # (`unbound`); the deck must still carry it
        c, _p = netlist_io.export_project(str(LC))
        names = sorted(d.label for d in c.devices if d.label)
        for nm in ("R", "L_2", "C_1", "C_2"):
            self.assertEqual(2, names.count(nm), nm)


class RectangleTests(unittest.TestCase):
    def export_with(self, rect):
        import json
        import tempfile
        proj = json.loads(LC.read_text(encoding="utf-8"))
        proj["documents"][0]["drafting"]["objects"].append(rect)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.icproj.json"
            path.write_text(json.dumps(proj), encoding="utf-8")
            return netlist_io.export_project(str(path))[1]

    def box(self, cx, cy, w, h):
        return {"id": "box-x", "kind": "rectangle", "locked": False,
                "zIndex": 0, "center": {"x": cx, "y": cy}, "width": w,
                "height": h, "rotation": 0, "lineStyle": "dashed",
                "anchor": {"kind": "free", "position": {"x": cx, "y": cy}}}

    def test_a_box_no_wire_touches_is_art(self):
        self.assertEqual([], self.export_with(self.box(1000, 1000, 40, 40)))

    def test_a_box_a_wire_runs_into_is_a_block(self):
        # JD1 sits at (300, 210): put the box's left edge on it
        problems = self.export_with(self.box(320, 210, 40, 40))
        self.assertTrue(any("rectangle" in p for p in problems), problems)


class DeckTests(unittest.TestCase):
    def test_deck_round_trips(self):
        c, _p = netlist_io.export_project(str(LC))
        text = netlist_io.deck_text(c)
        again = netlist_io.parse(text)
        self.assertEqual(text, netlist_io.deck_text(again))
        self.assertEqual(sorted(d.ref for d in c.devices),
                         sorted(d.ref for d in again.devices))

    def test_mirror_map_pairs_the_two_halves(self):
        deck = (ROOT / "toolkit" / "decks" / "razavi"
                / "fig10-6b_mos-diffpair.cir").read_text(encoding="utf-8")
        nmap, dmap = autoplace._mirror_map(netlist_io.parse(deck))
        self.assertEqual("M2", dmap["M1"])
        self.assertEqual("RDR", dmap["RDL"])
        self.assertEqual("ISS", dmap["ISS"])           # the middle one
        self.assertEqual("y", nmap["x"])

    def test_an_active_load_is_not_mirror_symmetric(self):
        # 5T OTA: M_3 is diode-connected, M_4 is not
        deck = (ROOT / "toolkit" / "decks" / "new"
                / "5T-OTA.cir").read_text(encoding="utf-8")
        self.assertIsNone(autoplace._mirror_map(netlist_io.parse(deck)))

    def test_no_pair_of_ports_means_no_symmetry(self):
        deck = (ROOT / "toolkit" / "decks" / "new"
                / "darlington-follower.cir").read_text(encoding="utf-8")
        self.assertIsNone(autoplace._mirror_map(netlist_io.parse(deck)))


class CoefficientNameTests(unittest.TestCase):
    def test_coefficient_keeps_its_letter(self):
        runs = icproj.flat(autoplace.name("2L_1"))
        self.assertEqual([("2L", False), ("1", True)],
                         [(t, sub) for t, sub, _i, _b in runs])

    def test_plain_names_follow_the_editor(self):
        self.assertEqual(icproj.name("R_M"), autoplace.name("R_M"))
        self.assertFalse(autoplace.coef_name("R_M"))
        self.assertTrue(autoplace.coef_name("2L_1"))


class DeckLibraryTests(unittest.TestCase):
    """Every generalisation deck is a well-formed netlist (11-05)."""

    def _decks(self):
        root = Path(netlist_io.__file__).resolve().parent / "decks"
        out = sorted(root.glob("new/*.cir")) + sorted(root.glob("razavi/*.cir"))
        self.assertGreater(len(out), 50)
        return out

    def test_every_deck_parses_round_trips_and_has_no_short(self):
        for path in self._decks():
            with self.subTest(deck=path.name):
                c = netlist_io.parse(path.read_text(encoding="utf-8"))
                self.assertTrue(c.devices)
                self.assertEqual([], netlist_io.topology_defects(c))
                text = netlist_io.deck_text(c)
                self.assertEqual(text, netlist_io.deck_text(
                    netlist_io.parse(text)))

    def test_every_port_node_is_used_by_a_device(self):
        for path in self._decks():
            with self.subTest(deck=path.name):
                c = netlist_io.parse(path.read_text(encoding="utf-8"))
                used = {n for d in c.devices for n in d.pins.values()}
                for nd, _nm, _di in c.ports:
                    self.assertIn(nd, used)


class DanglingNodeTests(unittest.TestCase):
    def test_a_node_only_one_pin_touches_is_reported(self):
        c = netlist_io.parse(".subckt D a b\n.iodir a=input b=output\n"
                             "R1 a b\nR2 b x\n.ends\n")
        self.assertEqual(["x"], netlist_io.dangling_nodes(c))

    def test_ports_rails_and_bulk_do_not_count_as_dangling(self):
        c = netlist_io.parse(".global VDD VEE\n.subckt D a\n"
                             ".iodir a=input\nR1 a 0\nR2 VDD 0\n"
                             "R3 VEE 0\nM1 a a 0 nb nmos\n.ends\n")
        self.assertEqual([], netlist_io.dangling_nodes(c))


if __name__ == "__main__":
    unittest.main()
