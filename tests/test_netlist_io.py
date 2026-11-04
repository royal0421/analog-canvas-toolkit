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
