# -*- coding: utf-8 -*-
"""Render an existing `.icproj.json` (ours, or one exported from the site)
straight to SVG + PNG with the same preview renderer `icproj.build()` uses.

    python render_project.py "<path>.json" [-o out.svg]

No audits, no schema check -- this only draws what the file already says.
"""
import json
import os
import sys

from icproj import Schematic, label_box

HERE = os.path.dirname(os.path.abspath(__file__))


def load(path, out_svg=None):
    proj = json.load(open(path, encoding="utf-8"))
    doc = proj["documents"][0]
    stem = os.path.splitext(os.path.basename(path))[0].replace(" ", "_")
    out_svg = out_svg or os.path.join(HERE, "auto", "render_" + stem + ".svg")
    if not os.path.isdir(os.path.dirname(out_svg)):
        os.makedirs(os.path.dirname(out_svg))
    f = Schematic(proj.get("id", "x"), proj.get("name", stem),
                  doc.get("netlist", {}).get("name", stem),
                  out_proj=os.path.join(HERE, "auto", "_render_tmp.json"),
                  out_svg=out_svg)
    f.instances = doc["instances"]
    for i in f.instances:
        pl = i["placement"]
        f.placed[i["id"]] = (i["symbolId"], pl["position"]["x"],
                             pl["position"]["y"], pl.get("mirror", "none"),
                             pl.get("rotation", 0))
    f.junctions = doc.get("junctions", [])
    f.routes = doc.get("routes", [])
    f.nets = doc.get("nets", [])
    f.annotations = doc.get("annotations", [])
    f.drafting = doc.get("drafting", {}).get("objects", [])
    f.terminals = doc.get("netlist", {}).get("terminals", [])
    return f


def viewbox(f, pad=20):
    xs, ys = [], []
    for iid in f.placed:
        b = f.ink(iid)
        xs += [b[0], b[2]]
        ys += [b[1], b[3]]
    for j in f.junctions:
        xs.append(j["position"]["x"])
        ys.append(j["position"]["y"])
    for _rid, x0, y0, x1, y1 in f.segments():
        xs += [x0, x1]
        ys += [y0, y1]
    for o in f.drafting:
        if o["kind"] == "rectangle":
            xs += [o["center"]["x"] - o["width"] / 2.0,
                   o["center"]["x"] + o["width"] / 2.0]
            ys += [o["center"]["y"] - o["height"] / 2.0,
                   o["center"]["y"] + o["height"] / 2.0]
        elif o["kind"] in ("arrow", "construction-line"):
            for p in ([o["from"]["position"], o["to"]["position"]]
                      if o["kind"] == "arrow"
                      else o.get("points", [])):
                xs.append(p["x"])
                ys.append(p["y"])
    for lid, rt, lx, ly, al, _own in f.label_records():
        b = label_box(rt, lx, ly, al)
        xs += [b[0], b[2]]
        ys += [b[1], b[3]]
    return (int(min(xs) - pad), int(min(ys) - pad),
            int(max(xs) - min(xs) + 2 * pad),
            int(max(ys) - min(ys) + 2 * pad))


def _png(f):
    """Same headless-Chrome shot `build()` takes, without the audits."""
    import subprocess
    chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    png = os.path.splitext(f.out_svg)[0] + ".png"
    if not os.path.isfile(chrome):
        print("  png: no Chrome at", chrome)
        return
    w, h = f.preview_px[0] + 20, f.preview_px[1] + 20
    subprocess.run([chrome, "--headless=new", "--screenshot=" + png,
                    "--window-size=%d,%d" % (w, h),
                    "--default-background-color=FFFFFFFF",
                    "file:///" + f.out_svg.replace("\\", "/")],
                   capture_output=True, timeout=120)
    print("  png: %s (%dx%d)" % (png, w, h))


def main(argv):
    path = argv[1]
    out = None
    if "-o" in argv:
        out = argv[argv.index("-o") + 1]
    f = load(path, out)
    vb = viewbox(f)
    print("%d instances, %d routes, %d junctions, %d drafting objects"
          % (len(f.instances), len(f.routes), len(f.junctions),
             len(f.drafting)))
    print("viewBox", vb)
    f._preview(vb)
    _png(f)


if __name__ == "__main__":
    main(sys.argv)
