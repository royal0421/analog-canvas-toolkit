import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolkit"))

import icproj  # noqa: E402


def symbol(*pins):
    return {
        "pins": [
            {"name": name, "at": {"x": x, "y": y}, "direction": direction}
            for name, x, y, direction in pins
        ],
        "primitives": [
            {"kind": "line", "from": {"x": -5, "y": -5},
             "to": {"x": 5, "y": 5}}
        ],
    }


class SchematicTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.figure = icproj.Schematic(
            "project-test", "Test", "Test",
            out_proj=str(base / "project.icproj.json"),
            out_svg=str(base / "preview.svg"),
        )
        self.original_symbols = dict(icproj._SYMS)
        self.addCleanup(self.restore_symbols)

    def restore_symbols(self):
        icproj._SYMS.clear()
        icproj._SYMS.update(self.original_symbols)

    def test_drafting_text_records_owner(self):
        self.figure.text("label", 10, 20, "start", "R_1", owner="R1")
        self.assertEqual("R1", self.figure.label_records()[0][-1])

    def test_bjt_base_is_not_treated_as_hidden_bulk(self):
        icproj._SYMS["npn"] = symbol(("B", 0, 0, "west"))
        self.figure.place("Q1", "npn", 100, 100)
        self.figure.net("net-base", [("Q1", "B")])
        errors = self.figure._selfcheck(set())
        self.assertTrue(any("unrouted terminal Q1.B" in error
                            for error in errors), errors)

    def test_mos_bulk_binding_may_be_implicit(self):
        icproj._SYMS["nmos"] = symbol(("B", 0, 0, "west"))
        self.figure.mos("M1", "nmos", 100, 100, "none", "M_1")
        self.figure.net("net-gnd-1", [("M1", "B")])
        errors = self.figure._selfcheck(set())
        self.assertFalse(any("unrouted terminal M1.B" in error
                             for error in errors), errors)

    def test_route_endpoints_must_belong_to_route_net(self):
        icproj._SYMS["port"] = symbol(("P", 0, 0, "east"))
        self.figure.port("A", 100, 100)
        self.figure.port("B", 140, 100)
        self.figure.net("net-a", [("A", "P")])
        self.figure.net("net-b", [("B", "P")])
        self.figure.route("wrong", "net-a", self.figure.term("A", "P"),
                          [("to", self.figure.term("B", "P"))])
        errors = self.figure._selfcheck(set())
        self.assertTrue(any("touches terminal B.P on net-b" in error
                            for error in errors), errors)

    def test_failed_external_validation_preserves_existing_output(self):
        output = Path(self.figure.out_proj)
        output.write_text("known-good", encoding="utf-8")
        missing_tools = str(Path(self.temp.name) / "missing-toolkit")
        with mock.patch.object(icproj, "HERE_TOOLKIT", missing_tools), \
                mock.patch.dict(os.environ, {"AC_NO_RENDER": "1"}, clear=False):
            with redirect_stdout(StringIO()):
                with self.assertRaises(icproj.BuildValidationError):
                    self.figure.build(extra_evidence=[], verbose=False,
                                      viewbox=(0, 0, 100, 100))
        self.assertEqual("known-good", output.read_text(encoding="utf-8"))


class RichTextTests(unittest.TestCase):
    def test_name_preserves_subscript_case(self):
        self.assertEqual("V_in", "_".join(
            text for text, sub, _italic, _bold in icproj.flat(icproj.name("V_in"))))

    def test_plain_text_is_upright(self):
        record = icproj.flat(icproj.plain("50 Ω"))
        self.assertEqual([("50 Ω", False, False, True)], record)


if __name__ == "__main__":
    unittest.main()
