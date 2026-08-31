import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "toolkit"))

import cli  # noqa: E402
import refresh_model  # noqa: E402
import scan_figure  # noqa: E402


class WorkflowTests(unittest.TestCase):
    def test_every_generator_declares_one_unique_output(self):
        projects = cli.discover_projects()
        self.assertEqual(29, len(projects))
        self.assertEqual(29, len({project.output.name for project in projects}))

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


if __name__ == "__main__":
    unittest.main()
