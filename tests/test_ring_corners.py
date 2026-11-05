import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolkit"))

import render_project as RP  # noqa: E402
import ring_corners as RC  # noqa: E402


class HandDrawnCountTests(unittest.TestCase):
    """The bench's reference numbers, read straight off the hand-drawn
    figures in out/: if `corners` or `crossings` drift, every bend and
    crossing ratio the bench prints drifts with them (11-05)."""

    CASES = {
        # stem: (bends = corners + 2.5 x gate crossings, crossings)
        "Razavi_Fig_7_94_source-follower": (3.0, 0),
        "AIC-intro_Midterm-2026_Fig1_folded-cascode": (17.5, 2),
        "AIC-HW2_Fig1_double-tail-comparator": (29.0, 2),
        "Razavi_Fig_10_35a_diffpair-diode-load": (15.0, 1),
    }

    def test_reference_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            for stem, (bends, cross) in self.CASES.items():
                with self.subTest(stem=stem):
                    f = RP.load(str(ROOT / "out" / (stem + ".icproj.json")),
                                out_svg=os.path.join(tmp, "x.svg"))
                    pts, gates, _x = RC.corners(f)
                    self.assertEqual(len(pts) + 2.5 * len(gates), bends)
                    # the bench's count: every unconnected X
                    import contextlib
                    import io
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(f._cross_count(), cross)
                    # ring_corners splits the same X's: one over a gate net
                    # is scored as 2.5 corners, the rest as crossings
                    self.assertEqual(len(RC.crossings(f))
                                     + len(RC._cross_points(f, True)), cross)


if __name__ == "__main__":
    unittest.main()
