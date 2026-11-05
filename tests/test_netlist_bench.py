import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolkit"))

import netlist_bench as NB  # noqa: E402


class PlacementScoreTests(unittest.TestCase):
    """The official scorer had no test of its own (11-05)."""

    REF = {"A": (100, 100, "none"), "B": (200, 100, "x"),
           "C": (100, 200, "none")}

    def test_a_copy_at_another_pitch_scores_perfectly(self):
        # every coordinate doubled: same ranks, same relations
        got = {k: (2 * x, 2 * y, m) for k, (x, y, m) in self.REF.items()}
        self.assertEqual(NB.score(self.REF, got), (1.0, 1.0))
        self.assertEqual(NB.order_score(self.REF, got), 1.0)
        self.assertEqual(NB.axis_score(self.REF, got, 0), 1.0)
        self.assertEqual(NB.axis_score(self.REF, got, 1), 1.0)

    def test_swapping_two_columns_is_seen(self):
        got = dict(self.REF, A=(200, 100, "none"), B=(100, 100, "x"))
        place, mirror = NB.score(self.REF, got)
        self.assertLess(place, 1.0)
        self.assertEqual(mirror, 1.0)
        self.assertLess(NB.order_score(self.REF, got), 1.0)
        self.assertEqual(NB.axis_score(self.REF, got, 1), 1.0)

    def test_a_flipped_transistor_costs_mirror_only(self):
        got = dict(self.REF, B=(200, 100, "none"))
        place, mirror = NB.score(self.REF, got)
        self.assertEqual(place, 1.0)
        self.assertAlmostEqual(mirror, 2 / 3.0)

    def test_nothing_in_common_scores_zero(self):
        self.assertEqual(NB.score(self.REF, {"Z": (0, 0, "none")}),
                         (0.0, 0.0))
        self.assertEqual(NB.order_score(self.REF, {}), 0.0)


class ReferenceFigureTests(unittest.TestCase):
    def test_hand_drawn_reference_matches_itself(self):
        stem = "Razavi_Fig_7_94_source-follower"
        ref = NB.ref_placement(stem)
        self.assertTrue(ref)
        self.assertEqual(NB.score(ref, ref), (1.0, 1.0))
        doc = json.loads((ROOT / "out" / (stem + ".icproj.json"))
                         .read_text(encoding="utf-8"))["documents"][0]
        self.assertGreater(NB.wire_len(doc), 0)
        self.assertEqual(NB.bend_count(doc), 3.0)
        self.assertEqual(NB.ref_crossings(stem), 0)


class CornerKindsTests(unittest.TestCase):
    def test_bench_bends_are_corner_kinds_plus_whole_gate_penalties(self):
        import os
        cwd = os.getcwd()
        os.chdir(str(ROOT / "toolkit"))
        try:
            import corner_kinds as K
            for path in sorted((ROOT / "out").glob("*.icproj.json")):
                with self.subTest(figure=path.name):
                    doc = json.loads(path.read_text(encoding="utf-8")
                                     )["documents"][0]
                    extra = NB.bend_count(doc) - len(K.corners(str(path)))
                    self.assertGreaterEqual(extra, 0)
                    self.assertEqual(extra % 2.5, 0)
        finally:
            os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
