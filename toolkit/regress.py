# -*- coding: utf-8 -*-
"""路線一的回歸測試：改了 SOP 或 icproj.py 之後，12 張既有的圖有沒有被改壞。

    python AI/toolkit/regress.py            # 跑全部，跟基準比
    python AI/toolkit/regress.py --accept   # 把現況存成新基準（**確認變更是刻意的才用**）

為什麼需要這支：SOP 的排版常數與稽核規則都寫在 icproj.py 裡，三條生產路線共用。
為路線二／三加規則時，很容易順手動到共用的部分而不自知——版控能讓你事後回頭，
但這支能在當下就指出「你改壞了哪一張」。

判定方式是**產物本身的 SHA**，不是「跑完沒報錯」（environment.md 硬規則 1）。
"""
import hashlib, io, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir, "out")
BASE = os.path.join(HERE, "_regress_baseline.json")
ACCEPT = "--accept" in sys.argv

def out_name(stdout):
    """產生器自己印的 `wrote N bytes -> <檔名>` 就是權威來源。

    舊版是掃原始碼找 `.icproj.json`，會被跨行的路徑字面值與 docstring 裡
    提到的檔名騙倒（2026-08-30：6 支被誤判成「沒寫出檔案」）。
    """
    for line in stdout.splitlines():
        if line.startswith("wrote ") and " -> " in line:
            return line.split(" -> ", 1)[1].strip()
    return None


LEGACY = {"gen_fig934.py": "Razavi_Fig_9_34_pnp-current-mirror.icproj.json",
          "gen_fig983_cg.py": "Razavi_Fig_9_83_CG.icproj.json"}


gens = sorted(f for f in os.listdir(HERE)
              if f.startswith("gen_") and f.endswith(".py"))
try:
    base = json.load(io.open(BASE, encoding="utf-8"))
except Exception:
    base = {}

now, broken = {}, []
for fn in gens:
    r = subprocess.run([sys.executable, fn], cwd=HERE, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       # the per-figure node checks and PNG render are for
                       # interactive use; 23 of each would take minutes
                       env=dict(os.environ, AC_FAST="1"))
    if "self-check errors: 0" not in r.stdout:
        broken.append((fn, "audit failed"))
        continue
    name = out_name(r.stdout) or LEGACY.get(fn)   # 兩支舊骨架不印路徑
    if not name:
        broken.append((fn, "cannot read its output filename"))
        continue
    p = os.path.join(ROOT, name)
    if not os.path.isfile(p):
        broken.append((fn, "did not write " + name))
        continue
    now[name] = hashlib.sha256(io.open(p, "rb").read()).hexdigest()

if ACCEPT:
    io.open(BASE, "w", encoding="utf-8", newline=chr(10)).write(
        json.dumps(now, indent=1, sort_keys=True, ensure_ascii=False) + chr(10))
    print("new baseline stored: %d figures" % len(now))
    sys.exit(0)

changed = [n for n in now if n in base and base[n] != now[n]]
added = [n for n in now if n not in base]
missing = [n for n in base if n not in now]

print("regression: %d figures" % len(now))
for fn, why in broken:
    print("  X %-24s %s" % (fn, why))
for n in changed:
    print("  ! CHANGED  %s" % n)
for n in missing:
    print("  ! MISSING  %s" % n)
for n in added:
    print("  + new      %s" % n)
if not (broken or changed or missing):
    print("  lane 1 untouched: all %d byte-identical" % len(now))
sys.exit(1 if (broken or changed or missing) else 0)
