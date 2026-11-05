import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolkit"))

import cli  # noqa: E402
import refresh_model  # noqa: E402
import scan_figure  # noqa: E402


class WorkflowTests(unittest.TestCase):
    def test_every_generator_declares_one_unique_output(self):
        projects = cli.discover_projects()
        generators = sorted((ROOT / "toolkit").glob("gen_*.py"))
        self.assertEqual(35, len(generators))
        self.assertEqual(set(generators),
                         {project.generator for project in projects})
        self.assertEqual(36, len(projects))
        self.assertEqual(36, len({project.output.name for project in projects}))
        modes = [p.args for p in projects if p.generator.stem == "gen_aic_hw2_tb"]
        self.assertEqual([("pattern",), ("offset",)], modes)

    def test_schema_version_update_preserves_file_shape(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "schema_version.py"
            path.write_text("header = True\nSCHEMA_VERSION = 31\n", encoding="utf-8")
            changed = refresh_model.update_schema_version(32, str(path))
            self.assertTrue(changed)
            self.assertEqual("header = True\nSCHEMA_VERSION = 32\n",
                             path.read_text(encoding="utf-8"))
            self.assertFalse(refresh_model.update_schema_version(32, str(path)))

    def test_runs_keeps_segment_at_end_of_vector(self):
        self.assertEqual([(1, 3)], scan_figure.runs([False, True, True, True], 3))


class GenerateCliTests(unittest.TestCase):
    def test_generator_name_selects_every_mode(self):
        projects = cli.discover_projects()
        got = cli.resolve_projects(["gen_aic_hw2_tb"], projects)
        self.assertEqual(["gen_aic_hw2_tb:pattern", "gen_aic_hw2_tb:offset"],
                         [p.name for p in got])
        one = cli.resolve_projects(["AIC-HW2_CMP_OFFSET_TB"], projects)
        self.assertEqual([("offset",)], [p.args for p in one])

    def test_only_a_build_that_validated_skips_the_second_check(self):
        ok = "self-check errors: 0\n  schema: VALID (v58)\n  labels: OK\n"
        self.assertTrue(cli.SCHEMA_OK.search(ok))
        for log in ("  external checks: SKIPPED (AC_FAST=1)\n",
                    "  schema: FAILED\n",
                    "  ! label x says schema: VALID (v58) in passing\n"):
            self.assertIsNone(cli.SCHEMA_OK.search(log), log)

    def test_unknown_selector_is_refused(self):
        with self.assertRaises(SystemExit):
            cli.resolve_projects(["gen_nope"], cli.discover_projects())

    def test_example_is_refreshed_only_when_its_svg_changed(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            ex, tk = tmp / "examples", tmp / "toolkit"
            ex.mkdir()
            tk.mkdir()
            (ex / "Fig.png").write_bytes(b"old")
            (tk / "preview_fig.svg").write_text("<svg/>", encoding="utf-8")
            (tk / "preview_fig.png").write_bytes(b"new")
            project = cli.Project(tk / "gen_fig.py", tmp / "Fig.icproj.json")
            out = "  png: preview_fig.png (10x10)\n"
            with unittest.mock.patch.object(cli, "EXAMPLES", ex), \
                    unittest.mock.patch.object(cli, "TOOLKIT", tk):
                manifest = {}
                self.assertTrue(cli.publish_example(project, out, manifest))
                self.assertEqual(b"new", (ex / "Fig.png").read_bytes())
                self.assertEqual(hashlib.sha256(b"<svg/>").hexdigest(),
                                 manifest["Fig.png"])
                (tk / "preview_fig.png").write_bytes(b"newer")
                self.assertFalse(cli.publish_example(project, out, manifest))
                self.assertEqual(b"new", (ex / "Fig.png").read_bytes())
                # no gallery image yet: nothing is added
                other = cli.Project(tk / "gen_x.py", tmp / "X.icproj.json")
                self.assertIsNone(cli.publish_example(other, out, manifest))


class GenBaselineTests(unittest.TestCase):
    def test_compare_flags_any_column_that_got_worse(self):
        import bench_par
        base = {"a": {"errors": 0, "crossings": 1, "bends": 4.0},
                "b": {"errors": 0, "crossings": 0, "bends": 3.0}}
        now = {"a": {"errors": 0, "crossings": 2, "bends": 3.5},
               "b": {"errors": 0, "crossings": 0, "bends": 3.0},
               "c": {"errors": 0, "crossings": 0, "bends": 1.0}}
        worse, better, new = bench_par.compare_gen(now, base)
        self.assertEqual(["a crossings 1 -> 2"], worse)
        self.assertEqual(["a bends 4.0 -> 3.5"], better)
        self.assertEqual(["c"], new)

    def test_stored_baseline_is_all_clean(self):
        import json
        base = json.loads((ROOT / "toolkit" / "gen_baseline.json")
                          .read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(base), 57)
        self.assertEqual([], [k for k, v in base.items() if v["errors"]])


class RenderProjectTests(unittest.TestCase):
    def test_an_existing_project_redraws(self):
        import contextlib
        import io
        import icproj
        import render_project
        if not list(Path(icproj.SYMDIR).glob("*.json")):
            self.skipTest("run `python -m toolkit setup` first")
        src = ROOT / "out" / "Razavi_Fig_9_34_pnp-current-mirror.icproj.json"
        with tempfile.TemporaryDirectory() as tmp:
            svg = str(Path(tmp) / "x.svg")
            with contextlib.redirect_stdout(io.StringIO()):
                f = render_project.load(str(src), svg)
                f._preview(render_project.viewbox(f))
            self.assertIn("<svg", Path(svg).read_text(encoding="utf-8"))
            self.assertEqual(6, len(f.instances) - sum(
                1 for i in f.instances
                if i["symbolId"] in ("ground", "port", "vdd-port")))

    def test_chrome_is_looked_up_on_every_platform(self):
        import icproj
        with unittest.mock.patch.dict("os.environ",
                                      {"CHROME_PATH": __file__}):
            self.assertEqual(__file__, icproj.find_chrome())


class ListValidateCliTests(unittest.TestCase):
    """`list` and `validate` had no test (11-05)."""

    def _run(self, *argv):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = {"list": cli.command_list,
                    "validate": cli.command_validate}[argv[0]](
                cli.build_parser().parse_args(list(argv)))
        return code, buf.getvalue()

    def test_list_names_every_generator_once(self):
        code, text = self._run("list")
        self.assertEqual(code, 0)
        names = [p.name for p in cli.discover_projects()]
        self.assertEqual(len(names), len(set(names)))
        for n in names:
            self.assertIn(n, text)

    def test_validate_passes_a_tracked_output_and_fails_a_broken_copy(self):
        import json
        import tempfile
        src = sorted(p.output for p in cli.discover_projects())[0]
        code, text = self._run("validate", str(src))
        self.assertEqual(code, 0, text)
        data = json.loads(src.read_text(encoding="utf-8"))
        data["schemaVersion"] = -1
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / src.name
            bad.write_text(json.dumps(data), encoding="utf-8")
            code, text = self._run("validate", str(bad))
        self.assertEqual(code, 1, text)
        self.assertIn("FAIL", text)

    def test_default_validate_skips_hand_drawn_references(self):
        code, text = self._run("validate")
        self.assertEqual(code, 0, text[-2000:])
        self.assertIn("SKIP AIC-HW1_Q1d_PNP_hybrid-pi.icproj.json", text)


if __name__ == "__main__":
    unittest.main()
