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


class LabelBuilderTests(unittest.TestCase):
    """icproj.name() must be the editor's buildName (model.mjs Kd)."""

    NAMES = ("M_1", "V_DD", "V_in1", "FF_1", "CK", "IN", "Out", "L1",
             "I_{SS}", "x", "v_out", "Alexander PD", "+", "\u2212",
             "r_\u03c01", "g_m1", "\U0001d6fdx")

    @staticmethod
    def kd_reference(text):
        """Kd() written out by hand from the v58 bundle."""
        def g(t):
            return {"kind": "span", "style": "italic", "children": [
                {"kind": "span", "style": "bold",
                 "children": [{"kind": "text", "value": t}]}]}

        def fd(t):
            return {"kind": "span", "style": "subscript", "children": [
                {"kind": "span", "style": "bold",
                 "children": [{"kind": "text", "value": t}]}]}
        if not text:
            return {"runs": [{"kind": "line-break"}]}
        return {"runs": [g(text[0])] + ([fd(text[1:])] if text[1:] else [])}

    def test_name_is_kd_of_the_semantic_text(self):
        for label in self.NAMES:
            sem = icproj.semantic(label)
            self.assertNotIn("_", sem)
            self.assertEqual(self.kd_reference(sem), icproj.name(label),
                             msg=label)
            self.assertEqual(sem, icproj.flat_text(icproj.name(label)))

    def test_v58_has_no_italic_subscripts(self):
        self.assertEqual(set(), icproj.ITALIC_SUBSCRIPTS)
        self.assertEqual(icproj.Vs("DD"), icproj.name("V_DD")["runs"][1])

    def test_port_words_keep_the_whole_word(self):
        self.assertEqual(icproj.word("IN"),
                         icproj.Schematic._port_text("IN"))
        self.assertEqual(icproj.name("V_out"),
                         icproj.Schematic._port_text("V_out"))

    def test_python_port_matches_the_downloaded_builder(self):
        import shutil
        import subprocess
        toolkit = ROOT / "toolkit"
        if not (toolkit / "model-adapter.mjs").is_file() \
                or not shutil.which("node"):
            self.skipTest("run `python -m toolkit setup` first")
        script = ('import {buildName} from "./model-adapter.mjs";'
                  'const n = JSON.parse(process.argv[1]);'
                  'console.log(JSON.stringify(n.map(s => buildName(s))));')
        sems = [icproj.semantic(n) for n in self.NAMES]
        out = subprocess.run(
            ["node", "--input-type=module", "-e", script, json.dumps(sems)],
            cwd=str(toolkit), capture_output=True, text=True,
            encoding="utf-8", timeout=120)
        self.assertEqual(0, out.returncode, out.stderr)
        self.assertEqual(json.loads(out.stdout),
                         [icproj.name(n) for n in self.NAMES])


if __name__ == "__main__":
    unittest.main()
