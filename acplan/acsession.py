# 上游 Analog Canvas 本機 MCP 的常駐連線（stdio JSON-RPC）。一個工作區一個行程，
# 暫存的匯入候選（candidate）只活在行程內，所以「匯入 netlist」一定要用這個、不能用一次一個行程的 acmcp.call。
# 用法：
#   with Session("ws/miller", new=True) as s:
#       s.import_spice("src_miller", "miller.sp")
#       svg = s.svg()
import json, os, subprocess, threading
HERE = os.path.dirname(os.path.abspath(__file__))
HEADLESS = os.path.join(HERE, "analog-canvas-headless-0.17.107.mjs")
BIN = os.path.join(HERE, "pkg", "package", "bin", "analog-canvas-mcp.mjs")


class Session(object):
    def __init__(self, ws, new=False, process="abstract"):
        self.ws = ws if os.path.isabs(ws) else os.path.join(HERE, ws)
        cmd = ["node", BIN, "--local", self.ws]
        if new and not os.path.exists(os.path.join(self.ws, "project.icproj.json")):
            cmd += ["--new", "--process", process]
        env = dict(os.environ, ANALOG_CANVAS_HEADLESS=HEADLESS)
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=env)
        self.err = []
        threading.Thread(target=lambda: [self.err.append(l) for l in self.p.stderr], daemon=True).start()
        self.n = 0
        self._rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                 "clientInfo": {"name": "acsession", "version": "0"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _send(self, o):
        self.p.stdin.write((json.dumps(o) + "\n").encode("utf-8")); self.p.stdin.flush()

    def _rpc(self, method, params):
        self.n += 1
        self._send({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params})
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("MCP process ended: " + b"".join(self.err[-5:]).decode("utf-8", "replace"))
            try:
                o = json.loads(line.decode("utf-8"))
            except Exception:
                continue
            if o.get("id") == self.n:
                if "error" in o:
                    raise RuntimeError(json.dumps(o["error"], ensure_ascii=False)[:1500])
                return o["result"]

    def call(self, tool, args=None):
        r = self._rpc("tools/call", {"name": tool, "arguments": args or {}})
        texts = [b.get("text", "") for b in r.get("content", []) if b.get("type") == "text"]
        self.last_blocks = r.get("content", [])
        try:
            return json.loads(texts[0]) if texts else r
        except Exception:
            return {"_text": "\n".join(texts)}

    def import_spice(self, root, entry, target="main"):
        root = root if os.path.isabs(root) else os.path.join(HERE, root)
        r = self.call("import_file", {"action": "stage-spice", "rootPath": root, "entryPath": entry})
        if not r.get("ok"):
            return r
        c = r["candidate"]
        return self.call("import_file", {"action": "import-cell", "candidateId": c["candidateId"],
                                         "sourceDocumentId": c["documents"][0]["id"],
                                         "targetDocumentId": target, "mode": "replace-body"})

    def close(self):
        try:
            self.p.stdin.close(); self.p.wait(timeout=20)
        except Exception:
            self.p.kill()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def save_render(s, svg_path, png_path=None, mode="formal", scale=2):
    """render → 存 SVG；給 png_path 就用 Playwright 轉成 PNG（白底）。回傳 render 的回覆。"""
    import base64
    r = s.call("render", {"mode": mode})
    img = [b for b in s.last_blocks if b.get("type") == "image"]
    data = base64.b64decode(img[0]["data"])
    open(svg_path, "wb").write(data)
    if png_path:
        svg2png(svg_path, png_path, scale)
    return r


def svg2png(svg_path, png_path, scale=2):
    """SVG 檔 → 白底 PNG（直接開 SVG 檔、整頁截圖）。"""
    import re
    from pathlib import Path
    from playwright.sync_api import sync_playwright
    head = open(svg_path, encoding="utf-8").read(600)
    m = re.search(r'viewBox="([-0-9. ]+)"', head)
    w, h = (float(x) for x in m.group(1).split()[2:]) if m else (1200, 800)
    mw = re.search(r'<svg[^>]*?\swidth="([0-9.]+)"[^>]*?\sheight="([0-9.]+)"', head)
    if mw:                                   # 檔頭有寫 width/height 就以它為準（我們自己的預覽 SVG）
        w, h = float(mw.group(1)), float(mw.group(2))
        scale = 1
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": int(w) + 2, "height": int(h) + 2}, device_scale_factor=scale)
        pg.goto(Path(svg_path).resolve().as_uri())
        pg.screenshot(path=png_path, omit_background=False)
        b.close()
