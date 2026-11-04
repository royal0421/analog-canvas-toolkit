# -*- coding: utf-8 -*-
"""Kept for old habits: runs `python -m toolkit regress`.

This used to rebuild the hand-drawn figures under AC_FAST and compare their
SHAs against `_regress_baseline.json` -- a file that no longer exists, so it
listed every figure as "new" and still printed "all byte-identical", and it
never ran `gen_aic_hw2_tb`'s second (offset) project.  The CLI regression
rebuilds every generator in a temporary copy, validates it and compares it
byte for byte with the tracked out/ files -- git is the baseline, so there
is nothing to `--accept`: commit the new outputs instead.
"""
import os
import subprocess
import sys

if __name__ == "__main__":
    if "--accept" in sys.argv[1:]:
        print("nothing to accept: the tracked out/*.icproj.json ARE the "
              "baseline -- regenerate (python -m toolkit generate all) and "
              "commit them")
        sys.exit(0)
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
    sys.exit(subprocess.call([sys.executable, "-m", "toolkit", "regress"]
                             + sys.argv[1:], cwd=os.path.abspath(root)))
