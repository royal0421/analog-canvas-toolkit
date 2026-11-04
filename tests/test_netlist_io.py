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


class CoefficientNameTests(unittest.TestCase):
    def test_coefficient_keeps_its_letter(self):
        runs = icproj.flat(autoplace.name("2L_1"))
        self.assertEqual([("2L", False), ("1", True)],
                         [(t, sub) for t, sub, _i, _b in runs])

    def test_plain_names_follow_the_editor(self):
        self.assertEqual(icproj.name("R_M"), autoplace.name("R_M"))
        self.assertFalse(autoplace.coef_name("R_M"))
        self.assertTrue(autoplace.coef_name("2L_1"))


if __name__ == "__main__":
    unittest.main()
