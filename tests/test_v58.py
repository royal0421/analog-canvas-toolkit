import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolkit"))

import fetch_symbols as F  # noqa: E402
import icproj  # noqa: E402


class LiteralTokenizerTests(unittest.TestCase):
    SRC = '''// Generated. Do not edit.
import type { X } from "./x.js";
export const things: readonly X[] = [
  {
    id: "a-b",  // trailing comment
    "quoted": 'it\\'s',
    n: -4.25, k: 10, e: 1e-3,
    flags: [true, false, null,],
    /* block */ nested: { x: { y: [] } },
  },
] as const;
export const other = [{ id: "z" }];
'''

    def test_reads_bare_keys_trailing_commas_and_comments(self):
        got = F.exported_array(self.SRC, "things")
        self.assertEqual([{"id": "a-b", "quoted": "it's", "n": -4.25,
                           "k": 10, "e": 0.001,
                           "flags": [True, False, None],
                           "nested": {"x": {"y": []}}}], got)
        self.assertIsInstance(got[0]["k"], int)
        self.assertEqual([{"id": "z"}], F.exported_array(self.SRC, "other"))

    def test_refuses_anything_that_is_not_a_literal(self):
        for body in ("[{ a: foo }];", "[...more];", "[{ a: `t` }];",
                     "[{ a }];", "[f()];"):
            with self.assertRaises(F.LiteralError, msg=body):
                F.exported_array("export const t = " + body, "t")

    def test_library_filter_ports_builtins(self):
        syms = [{"id": i, "pins": [], "primitives": []}
                for i in ("ok", "house", "bad-house", "prov", "other")]
        entries = [
            {"symbolId": "ok", "reviewStatus": "reviewed",
             "visualAuthority": {"kind": "razavi-reference-v1"}},
            {"symbolId": "house", "reviewStatus": "reviewed",
             "provenance": "house"},
            {"symbolId": "bad-house", "reviewStatus": "reviewed",
             "provenance": "house",
             "visualAuthority": {"kind": "razavi-reference-v1"}},
            {"symbolId": "prov", "reviewStatus": "provisional",
             "visualAuthority": {"kind": "razavi-reference-v1"}},
            {"symbolId": "other", "reviewStatus": "reviewed"},
        ]
        razavi = ("export const razaviSymbolCatalogEntries = %s;\n"
                  "export const razaviCatalogSymbols = %s;\n"
                  % (json.dumps(entries), json.dumps(syms)))
        expanded = ("export const expandedComponentSymbols = "
                    '[{"id": "ndmos", "pins": [], "primitives": []}];')
        ids = [s["id"] for s in F.builtin_symbols(razavi, expanded)]
        self.assertEqual(["ok", "house", "ndmos"], ids)

    def test_dump_matches_cache_format(self):
        self.assertEqual('{\n "id": "Ω"\n}\n', F.dump({"id": "Ω"}))


class MirrorTests(unittest.TestCase):
    def test_out_and_in_round_trip(self):
        for rot in (0, 90, 180, 270):
            for m in ("none", "x", "y"):
                out = icproj.mirror_out(m, rot)
                self.assertIn(out, ("none", "horizontal", "vertical"))
                self.assertEqual((m, rot), icproj.mirror_in(out, rot))
        self.assertEqual("horizontal", icproj.mirror_out("x", 0))
        self.assertEqual("vertical", icproj.mirror_out("x", 90))
        self.assertEqual(("none", 270), icproj.mirror_in("both", 90))

    def test_v58_mirror_applies_after_rotation(self):
        for rot in (0, 90, 180, 270):
            for m in ("x", "y"):
                for p in ((10, -20), (-20, 0), (3, 7)):
                    want = icproj.xf(p[0], p[1], m, rot)
                    got = icproj.xf(p[0], p[1], "none", rot)
                    out = icproj.mirror_out(m, rot)
                    got = (-got[0] if out == "horizontal" else got[0],
                           -got[1] if out == "vertical" else got[1])
                    self.assertAlmostEqual(want[0], got[0])
                    self.assertAlmostEqual(want[1], got[1])

    def test_build_serializes_v58_enum_on_a_copy(self):
        inst = {"id": "M1", "symbolId": "nmos",
                "placement": {"mirror": "x", "rotation": 90,
                              "position": {"x": 0, "y": 0}}}
        out = icproj.Schematic._instance_out(inst)
        self.assertEqual("vertical", out["placement"]["mirror"])
        self.assertEqual("x", inst["placement"]["mirror"])


if __name__ == "__main__":
    unittest.main()
