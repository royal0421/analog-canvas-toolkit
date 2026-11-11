# 一次跑多份 plans_py，印每份的檢查結果，並把圖拼成一張 out/_batch.png 供一次看完。
# 用法：python runbatch.py <名稱> <名稱> ...   （名稱＝plans_py 裡的檔名，不含 .py）
import io, os, subprocess, sys
from pathlib import Path
HERE = os.path.dirname(os.path.abspath(__file__))
names = sys.argv[1:]
for n in names:
    r = subprocess.run([sys.executable, os.path.join(HERE, "plans_py", n + ".py")], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    if "走線失敗" in r.stdout or "WORKSPACE_SAVE_FAILED" in (r.stdout + r.stderr):          # 整批連跑時偶發（2026-11-11 見過 2/46，單獨重跑都過）：原樣重跑一次，兩次都失敗才算
        print("（%s 走線失敗，原樣重跑一次）" % n)
        r = subprocess.run([sys.executable, os.path.join(HERE, "plans_py", n + ".py")], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    keep = [l for l in (r.stdout + r.stderr).splitlines()
            if ("FAIL" in l or "CHECK" in l or l.startswith("    ") or "Error" in l or "Traceback" in l or "own check" in l)]
    print("== %s\n%s" % (n, "\n".join(k[:330] for k in keep)))
h = ['<!doctype html><meta charset="utf-8"><style>body{font-family:sans-serif;margin:8px;display:flex;flex-wrap:wrap;gap:10px}'
     'div{border:1px solid #bbb;padding:4px}img{zoom:.5;display:block}b{font-size:13px}</style>']
h += ['<div><b>%s</b><img src="%s.png"></div>' % (n, n) for n in names]
io.open(os.path.join(HERE, "out", "_batch.html"), "w", encoding="utf-8").write("\n".join(h))
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1500, "height": 700})
    pg.goto(Path(os.path.join(HERE, "out", "_batch.html")).as_uri()); pg.wait_for_load_state("networkidle")
    pg.screenshot(path=os.path.join(HERE, "out", "_batch.png"), full_page=True); b.close()
