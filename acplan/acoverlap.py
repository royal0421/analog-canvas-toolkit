# 看圖檢查的自動版：讀出圖的 SVG，找「字壓到字」「字壓到線」。
# 用法：python acoverlap.py out/<名稱>.svg [...]　　（不給參數＝掃 out/ 全部）
# 做法：用瀏覽器量每段文字的外框（內縮 SHRINK，免得剛好貼著就算）；線取樣成點，看有沒有點落在文字外框裡。
import glob, os, sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SHRINK = 1.5          # 文字外框內縮（SVG 單位）
STEP = 2.0            # 線的取樣間距

JS = """
([shrink, step]) => {
  const svg = document.querySelector('svg');
  const toBox = (el) => { const r = el.getBoundingClientRect(); return {x0: r.left + shrink, y0: r.top + shrink, x1: r.right - shrink, y1: r.bottom - shrink}; };
  const texts = [...svg.querySelectorAll('text')].filter(t => t.textContent.trim().length).map(t => ({
      id: t.getAttribute('data-object-id') || '', s: t.textContent.trim(), b: toBox(t)})).filter(t => t.b.x1 > t.b.x0 && t.b.y1 > t.b.y0);
  const out = [];
  for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++) {
    const a = texts[i].b, b = texts[j].b;
    if (a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1) out.push(['text-text', texts[i].s, texts[j].s]);
  }
  const wires = [...svg.querySelectorAll('g[data-layer="routes"] line, g[data-layer="routes"] path, g[data-layer="routes"] polyline, g[data-kind="draft-arrow"] line, g[data-kind="draft-arrow"] path, g[data-kind="draft-arrow"] polyline')];
  const hit = new Set();
  for (const w of wires) {
    let len = 0; try { len = w.getTotalLength(); } catch (e) { continue; }
    const m = w.getScreenCTM(); if (!m) continue;
    for (let d = 0; d <= len; d += step) {
      const p = w.getPointAtLength(d); const x = p.x * m.a + p.y * m.c + m.e, y = p.x * m.b + p.y * m.d + m.f;
      for (const t of texts) if (x > t.b.x0 && x < t.b.x1 && y > t.b.y0 && y < t.b.y1) hit.add(t.s);
    }
  }
  for (const s of hit) out.push(['text-wire', s, '']);
  return out;
}
"""


def overlaps(svg_paths):
    """回傳 {svg 路徑: [說明字串, ...]}；沒有重疊的圖不列。"""
    from playwright.sync_api import sync_playwright
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 2000, "height": 1500})
        for sp in svg_paths:
            pg.goto(Path(sp).resolve().as_uri())
            found = pg.evaluate(JS, [SHRINK, STEP])
            msgs = []
            for kind, a, c in found:
                msgs.append("字「%s」跟字「%s」重疊" % (a, c) if kind == "text-text" else "字「%s」壓到線" % a)
            if msgs:
                res[sp] = sorted(set(msgs))
        b.close()
    return res


if __name__ == "__main__":
    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(HERE, "out", "*.svg")))
    r = overlaps(paths)
    for sp in paths:
        print("%-34s %s" % (os.path.basename(sp), "；".join(r[sp]) if sp in r else "ok"))
    print("重疊的圖：%d／%d" % (len(r), len(paths)))
