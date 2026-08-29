# -*- coding: utf-8 -*-
"""Razavi Fig. 9.83 (problem 68): common-gate stage with M3 current-source load.

Topology read off the user's screenshot at 5-6x zoom, transistor by transistor.
Symbol pin offsets come from the shipped razavi-v1 symbol assets.
"""
import json, os, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
SYMDIR = os.path.join(HERE, "sym")
OUT_PROJ = os.path.join(OUT, "Razavi_Fig_9_83_CG.icproj.json")
OUT_SVG = os.path.join(HERE, "preview_fig983cg.svg")

SYMS = {}
for n in ("nmos", "pmos", "current-source", "ground", "port", "port-filled",
          "vdd-port"):
    with open(os.path.join(SYMDIR, n + ".json"), encoding="utf-8") as f:
        SYMS[n] = json.load(f)


def hid(*p):
    return hashlib.sha256("|".join(map(str, p)).encode()).hexdigest()[:16]


def txt(v):
    return {"kind": "text", "value": v}


def span(style, children):
    return {"kind": "span", "style": style, "children": children}


# The editor's own label builders (packages/model), reproduced verbatim so a
# generated label is byte-identical to one the editor would have made:
#     Rs(t)  = italic(bold(t))                       -- the variable letter
#     Vs(t)  = subscript(italic(bold(t)))  if t in {dd,ss,cc,ee,bb}
#              subscript(bold(t))          otherwise
# That single exception is why V_DD is fully italic while M_REF / V_out / V_b
# keep upright subscripts. The SVG renderer hard-codes italic=false when it
# enters a subscript, so an italic span wrapped OUTSIDE the subscript is
# dropped -- it only counts when it sits INSIDE.
ITALIC_SUBSCRIPTS = {"dd", "ss", "cc", "ee", "bb"}


def Rs(t):
    return span("italic", [span("bold", [txt(t)])])


def Vs(t):
    inner = span("bold", [txt(t)])
    if t.strip().lower() in ITALIC_SUBSCRIPTS:
        inner = span("italic", [inner])
    return span("subscript", [inner])


def var(base, sub=None):
    return {"runs": [Rs(base)] + ([Vs(sub)] if sub is not None else [])}


VDD_LABEL = {"runs": [Rs("V"), Vs("DD"), span("bold", [txt(" = 1.8 V")])]}

# ---------------------------------------------------------------- placement
instances = []
PLACED = {}


def place(iid, symbol_id, x, y, mirror="none", extra=None):
    assert x % 10 == 0 and y % 10 == 0, (iid, x, y)
    inst = {"id": iid, "symbolId": symbol_id,
            "placement": {"mirror": mirror, "position": {"x": x, "y": y},
                          "rotation": 0}}
    if extra:
        inst.update(extra)
    instances.append(inst)
    PLACED[iid] = (symbol_id, x, y, mirror)
    return iid


def pin_xy(iid, pin):
    sym_id, x, y, mirror = PLACED[iid]
    for p in SYMS[sym_id]["pins"]:
        if p["name"] == pin:
            px, py = p["at"]["x"], p["at"]["y"]
            if mirror == "x":
                px = -px
            elif mirror == "y":
                py = -py
            return (x + px, y + py)
    raise KeyError((iid, sym_id, pin))


LABEL_SIZE = 0.65      # editor default 1.15 minus two A- presses (-0.1 each)
TB = "textbook-3terminal"
NMOS_BULK_NET = "net-gnd-1"


def mos(iid, kind, x, y, mirror, name_base, name_sub):
    """Bulk origin enum is exactly ["cell-default", "supply-default"]:
    NMOS bulk -> the document default bulk Net, PMOS bulk -> the supply."""
    if kind == "nmos":
        binding = {"netId": NMOS_BULK_NET, "origin": "cell-default"}
    else:
        binding = {"netId": "net-power-vdd", "origin": "supply-default"}
    return place(iid, kind, x, y, mirror, extra={
        "symbolVariantId": TB,
        "schematicReference": iid,
        "schematicName": var(name_base, name_sub),
        "mosBulkBinding": binding,
    })


# --- column A: I_REF / M_REF -------------------------------------------------
place("IREF", "current-source", 170, 230, extra={
    "schematicReference": "IREF",
    "schematicName": var("I", "REF"),
    "netlist": {"binding": {"kind": "primitive",
                            "deviceClass": "current-source"},
                "parameters": {}, "reference": "IREF"}})
mos("MREF", "nmos", 180, 310, "x", "M", "REF")
place("GND1", "ground", 170, 350, extra={"schematicReference": "GND1"})

# --- column B: M4 over M5 ----------------------------------------------------
mos("M4", "pmos", 330, 140, "x", "M", "4")
mos("M5", "nmos", 310, 310, "none", "M", "5")
place("GND2", "ground", 320, 350, extra={"schematicReference": "GND2"})

# --- column C: M3 / M1 / M2 --------------------------------------------------
mos("M3", "pmos", 440, 140, "none", "M", "3")
mos("M1", "nmos", 460, 230, "x", "M", "1")
mos("M2", "nmos", 440, 310, "none", "M", "2")
place("GND3", "ground", 450, 350, extra={"schematicReference": "GND3"})

# --- supply and ports --------------------------------------------------------
place("VOUT", "port", 480, 190, mirror="x")
place("VB", "port-filled", 510, 230, mirror="x")
place("VIN", "port", 420, 270)

# ---------------------------------------------------------------- junctions
junctions = [
    ("jvdd-start", "net-power-vdd", 150, 100),
    ("JV_A", "net-power-vdd", 170, 100),
    ("JV_B", "net-power-vdd", 320, 100),
    ("JV_C", "net-power-vdd", 450, 100),
    ("jvdd-end", "net-power-vdd", 470, 100),
    ("JREF", "net-nbias", 170, 270),
    ("JG", "net-nbias", 210, 310),
    ("JG2", "net-nbias", 270, 310),
    ("JD4", "net-pbias", 320, 180),
    ("J4G", "net-pbias", 370, 140),
    ("JOUT", "net-vout", 450, 190),
    ("JIN", "net-vin", 450, 270),
]
junctions = [{"id": i, "netId": n, "position": {"x": x, "y": y},
              "role": "branch"} for i, n, x, y in junctions]

# ---------------------------------------------------------------- nets
def T(iid, pin):
    return {"instanceId": iid, "pinName": pin}


nets = [
    {"id": "net-power-vdd", "terminals": [
        T("M3", "S"), T("M4", "S"), T("IREF", "+"),
        T("M3", "B"), T("M4", "B")]},
    {"id": "net-nbias", "terminals": [
        T("IREF", "-"), T("MREF", "D"), T("MREF", "G"), T("M5", "G"),
        T("M2", "G")]},
    {"id": "net-pbias", "terminals": [
        T("M4", "D"), T("M4", "G"), T("M3", "G"), T("M5", "D")]},
    {"id": "net-vout", "terminals": [
        T("M3", "D"), T("M1", "D"), T("VOUT", "P")]},
    {"id": "net-vb", "terminals": [T("M1", "G"), T("VB", "P")]},
    {"id": "net-vin", "terminals": [
        T("M1", "S"), T("M2", "D"), T("VIN", "P")]},
    {"id": "net-gnd-1", "terminals": [
        T("GND1", "0"), T("MREF", "S"),
        T("MREF", "B"), T("M5", "B"), T("M2", "B"), T("M1", "B")]},
    {"id": "net-gnd-2", "terminals": [T("GND2", "0"), T("M5", "S")]},
    {"id": "net-gnd-3", "terminals": [T("GND3", "0"), T("M2", "S")]},
]

# ---------------------------------------------------------------- routes
routes = []


def term(iid, pin):
    return {"kind": "terminal", "instanceId": iid, "pinName": pin}


def jn(jid):
    return {"kind": "junction", "junctionId": jid}


def route(rid, net_id, start, steps, presentation=None):
    """steps: list of ('bend', x, y) or ('to', anchor)."""
    legs = []
    for i, s in enumerate(steps):
        lid = hid(rid, i)
        if s[0] == "bend":
            legs.append({"id": "route-leg-" + lid, "mode": "manual",
                         "to": {"kind": "bend", "bendId": "route-bend-" + lid,
                                "position": {"x": s[1], "y": s[2]}}})
        else:
            legs.append({"id": "route-leg-" + lid, "mode": "manual",
                         "to": {"kind": "endpoint", "endpoint": s[1]}})
    r = {"id": rid, "netId": net_id, "start": start, "legs": legs}
    if presentation:
        r["presentation"] = presentation
    routes.append(r)


# supply rail
# The supply is a Razavi-style power rail: three collinear route segments
# tagged presentation="power-rail" (the app draws those as one heavy bar),
# plus ordinary drops to each device.
route("r-vdd-rail-0", "net-power-vdd", jn("jvdd-start"), [("to", jn("JV_A"))],
      presentation="power-rail")            # left overhang
route("r-vdd-rail-1", "net-power-vdd", jn("JV_A"), [("to", jn("JV_B"))],
      presentation="power-rail")
route("r-vdd-rail-2", "net-power-vdd", jn("JV_B"), [("to", jn("JV_C"))],
      presentation="power-rail")
route("r-vdd-rail-3", "net-power-vdd", jn("JV_C"), [("to", jn("jvdd-end"))],
      presentation="power-rail")            # right overhang
route("r-vdd-drop-m4", "net-power-vdd", jn("JV_B"), [("to", term("M4", "S"))])
route("r-vdd-drop-m3", "net-power-vdd", jn("JV_C"), [("to", term("M3", "S"))])
route("r-vdd-drop-iref", "net-power-vdd", jn("JV_A"),
      [("to", term("IREF", "+"))])
# NMOS mirror bias
route("r-nb-1", "net-nbias", term("IREF", "-"), [("to", jn("JREF"))])
route("r-nb-2", "net-nbias", jn("JREF"), [("to", term("MREF", "D"))])
route("r-nb-3", "net-nbias", jn("JREF"), [("bend", 210, 270), ("to", jn("JG"))])
route("r-nb-4", "net-nbias", jn("JG"), [("to", term("MREF", "G"))])
route("r-nb-5", "net-nbias", jn("JG"), [("to", jn("JG2"))])
route("r-nb-6", "net-nbias", jn("JG2"), [("to", term("M5", "G"))])
route("r-nb-7", "net-nbias", jn("JG2"), [
    ("bend", 270, 380), ("bend", 380, 380), ("bend", 380, 310),
    ("to", term("M2", "G"))])
# PMOS mirror bias
route("r-pb-1", "net-pbias", term("M4", "D"), [("to", jn("JD4"))])
route("r-pb-2", "net-pbias", jn("JD4"), [("to", term("M5", "D"))])
route("r-pb-3", "net-pbias", term("M4", "G"), [("to", jn("J4G"))])
route("r-pb-4", "net-pbias", jn("J4G"), [("to", term("M3", "G"))])
route("r-pb-5", "net-pbias", jn("J4G"), [("bend", 370, 180), ("to", jn("JD4"))])
# output / input / bias port
route("r-out-1", "net-vout", term("M3", "D"), [("to", jn("JOUT"))])
route("r-out-2", "net-vout", jn("JOUT"), [("to", term("M1", "D"))])
route("r-out-3", "net-vout", jn("JOUT"), [("to", term("VOUT", "P"))])
route("r-vb-1", "net-vb", term("M1", "G"), [("to", term("VB", "P"))])
route("r-in-1", "net-vin", term("M1", "S"), [("to", jn("JIN"))])
route("r-in-2", "net-vin", jn("JIN"), [("to", term("M2", "D"))])
route("r-in-3", "net-vin", jn("JIN"), [("to", term("VIN", "P"))])
# grounds
route("r-g1", "net-gnd-1", term("MREF", "S"), [("to", term("GND1", "0"))])
route("r-g2", "net-gnd-2", term("M5", "S"), [("to", term("GND2", "0"))])
route("r-g3", "net-gnd-3", term("M2", "S"), [("to", term("GND3", "0"))])

# ------------------------------------------------- cell terminals for ports
terminals = [
    {"id": "terminal-vout", "name": "Vout", "netId": "net-vout",
     "direction": "output", "interfaceInstanceIds": ["VOUT"]},
    {"id": "terminal-vin", "name": "Vin", "netId": "net-vin",
     "direction": "input", "interfaceInstanceIds": ["VIN"]},
    {"id": "terminal-vb", "name": "Vb", "netId": "net-vb",
     "direction": "input", "interfaceInstanceIds": ["VB"]},
]

# ---------------------------------------------------------------- annotations
annotations = []


def inst_label(iid, dx, dy, alignment):
    _, ix, iy, _ = PLACED[iid]
    annotations.append({
        "id": "instance-label-" + iid, "kind": "instance-label",
        "alignment": alignment, "locked": False, "rotation": 0,
        "sizeScale": LABEL_SIZE,
        "anchor": {"kind": "object", "objectId": iid,
                   "localOffset": {"x": dx, "y": dy},
                   "fallbackPosition": {"x": ix + dx, "y": iy + dy}},
        "binding": {"kind": "instance-schematic-name", "instanceId": iid}})


def port_label(iid, tid, rt, dx, dy, alignment):
    _, ix, iy, _ = PLACED[iid]
    annotations.append({
        "id": "instance-label-" + iid, "kind": "instance-label",
        "alignment": alignment, "locked": False, "rotation": 0, "sizeScale": LABEL_SIZE,
        "anchor": {"kind": "object", "objectId": iid,
                   "localOffset": {"x": dx, "y": dy},
                   "fallbackPosition": {"x": ix + dx, "y": iy + dy}},
        "binding": {"kind": "cell-terminal-name", "terminalId": tid},
        "formatOverride": rt})


inst_label("IREF", -18, 5, "end")
inst_label("MREF", -18, 5, "end")
inst_label("M5", 18, 5, "start")
inst_label("M2", 18, 5, "start")
inst_label("M4", -18, 5, "end")
inst_label("M3", 18, 5, "start")
inst_label("M1", -18, 5, "end")
port_label("VOUT", "terminal-vout", var("V", "out"), 11, 5, "start")
port_label("VB", "terminal-vb", var("V", "b"), 11, 5, "start")
port_label("VIN", "terminal-vin", var("V", "in"), -16, 5, "end")

# ---------------------------------------------------------------- drafting
annotations.append({
    "id": "label-vdd", "kind": "power-label", "netId": "net-power-vdd",
    "alignment": "start", "locked": False, "rotation": 0, "sizeScale": LABEL_SIZE,
    "anchor": {"kind": "object", "objectId": "jvdd-end",
               "localOffset": {"x": 12, "y": 6},
               "fallbackPosition": {"x": 482, "y": 105}},
    "content": VDD_LABEL})

drafting = []

# ---------------------------------------------------------------- project
project = {
    "documents": [{
        "annotations": annotations,
        "connectivityEvidence": [
            {"id": "cev-vdd-property", "kind": "name-claim",
             "netId": "net-power-vdd", "name": "VDD",
             "owner": {"kind": "explicit-net-property"},
             "scope": "global", "powerDomain": "vdd"},
            {"id": "cev-vdd-marker", "kind": "name-claim",
             "netId": "net-power-vdd", "name": "VDD",
             "owner": {"kind": "power-marker", "objectId": "jvdd-end"},
             "scope": "global", "powerDomain": "vdd"}],
        "constraints": [],
        "drafting": {"objects": drafting},
        "id": "document-main",
        "instances": instances,
        "junctions": junctions,
        "layoutGroups": [],
        "mosBulkDefaults": {"nmosNetId": "net-gnd-1"},
        "name": "Main",
        "netlist": {"formalParameters": [], "name": "Fig_9_83_CG",
                    "terminals": terminals},
        "nets": nets,
        "noConnects": [],
        "presentation": {"compactness": "compact", "grid": 10,
                         "styleProfileId": "razavi-textbook-v1",
                         "styleOverrides": {"symbolStrokeScale": 1.5,
                                            "wireStrokeScale": 1.5,
                                            "annotationStrokeScale": 1.5,
                                            "junctionRadiusScale": 1.3,
                                            "fontScale": 2.0}},
        "revision": 0,
        "routes": routes,
        "sourceStatus": "in-sync",
    }],
    "externalSubcircuitDefinitions": [],
    "id": "project-razavi-fig-9-83-cg",
    "name": "Razavi Fig. 9.83 — common-gate stage",
    "schemaVersion": 30,
    "source": {"dialect": "none", "entry": None, "files": [],
               "sourcePolicy": "copy"},
    "structureRevision": 0,
    "symbolLibrary": {"hash": "razavi-reference-v1", "id": "razavi-symbols",
                      "version": "1"},
    "topDocumentId": "document-main",
}

# ---------------------------------------------------------------- self-check
errs = []
JPOS = {j["id"]: (j["position"]["x"], j["position"]["y"]) for j in junctions}
net_ids = {n["id"] for n in nets}


def axy(a):
    if a["kind"] == "terminal":
        return pin_xy(a["instanceId"], a["pinName"])
    return JPOS[a["junctionId"]]


for n in nets:
    for t_ in n["terminals"]:
        pin_xy(t_["instanceId"], t_["pinName"])

routed = set()
for r in routes:
    if r["netId"] not in net_ids:
        errs.append("route %s unknown net" % r["id"])
    pt = axy(r["start"])
    if r["start"]["kind"] == "terminal":
        routed.add((r["start"]["instanceId"], r["start"]["pinName"]))
    for lg in r["legs"]:
        to = lg["to"]
        if to["kind"] == "bend":
            nxt = (to["position"]["x"], to["position"]["y"])
        else:
            nxt = axy(to["endpoint"])
            if to["endpoint"]["kind"] == "terminal":
                routed.add((to["endpoint"]["instanceId"],
                            to["endpoint"]["pinName"]))
        if pt[0] != nxt[0] and pt[1] != nxt[1]:
            errs.append("route %s not orthogonal %s->%s" % (r["id"], pt, nxt))
        if pt == nxt:
            errs.append("route %s zero-length at %s" % (r["id"], pt))
        pt = nxt

for n in nets:
    for t_ in n["terminals"]:
        key = (t_["instanceId"], t_["pinName"])
        if t_["pinName"] == "B":
            continue                      # hidden bulk: bound, not routed
        if key not in routed:
            errs.append("unrouted terminal %s.%s in %s"
                        % (key[0], key[1], n["id"]))

# every junction must be touched by >=2 route ends
touch = {}
for r in routes:
    for a in [r["start"]] + [lg["to"].get("endpoint") for lg in r["legs"]
                             if lg["to"]["kind"] == "endpoint"]:
        if a and a["kind"] == "junction":
            touch[a["junctionId"]] = touch.get(a["junctionId"], 0) + 1
RAIL_ENDS = {"jvdd-end", "jvdd-start"}      # rail end-cap carries the power marker only
for j in junctions:
    if j["id"] in RAIL_ENDS:
        continue
    if touch.get(j["id"], 0) < 2:
        errs.append("junction %s touched %d times" % (j["id"],
                                                      touch.get(j["id"], 0)))

print("self-check errors:", len(errs))
for e in errs:
    print("  !", e)

with open(OUT_PROJ, "w", encoding="utf-8") as f:
    json.dump(project, f, ensure_ascii=False, indent=2)
print("wrote", os.path.getsize(OUT_PROJ), "bytes")


# ---------------------------------------------------------------- run audit
# Every run measured off the book screenshot as (vertical_px, horizontal_px).
# The two axes need different scales because the canvas symbol is ~2x wider
# relative to its channel bar than Razavi's drawing is:
#   K_V = 250 / 582  (rail -> ground bar)      K_H = 320 / 598  (rail span)
K_V, K_H = 250 / 582, 320 / 598
BOOK = {                     # (v_px, h_px)
    "r-vdd-rail-0": (0, 30), "r-vdd-rail-1": (0, 298),
    "r-vdd-rail-2": (0, 240), "r-vdd-rail-3": (0, 30),
    "r-vdd-drop-iref": (324, 0), "r-vdd-drop-m4": (75, 0),
    "r-vdd-drop-m3": (76, 0),
    "r-nb-1": (68, 0), "r-nb-2": (44, 0), "r-nb-3": (69, 100),
    "r-nb-4": (0, 35), "r-nb-5": (0, 90), "r-nb-6": (0, 70),
    "r-nb-7": (253, 243),
    "r-pb-1": (41, 0), "r-pb-2": (385, 0), "r-pb-3": (0, 35),
    "r-pb-4": (0, 137), "r-pb-5": (71, 102),
    "r-out-1": (70, 0), "r-out-2": (74, 0), "r-out-3": (0, 94),
    "r-vb-1": (0, 77),
    "r-in-1": (102, 0), "r-in-2": (104, 0), "r-in-3": (0, 63),
    "r-g1": (56, 0), "r-g2": (56, 0), "r-g3": (56, 0),
}
print()
print("%-18s %5s %5s %8s %6s" % ("route", "dy", "dx", "book~", "ratio"))
rows = []
for r in routes:
    pt = axy(r["start"]); dx = dy = 0
    for lg in r["legs"]:
        to = lg["to"]
        nxt = ((to["position"]["x"], to["position"]["y"])
               if to["kind"] == "bend" else axy(to["endpoint"]))
        dx += abs(nxt[0] - pt[0]); dy += abs(nxt[1] - pt[1]); pt = nxt
    b = BOOK.get(r["id"])
    tgt = (b[0] * K_V + b[1] * K_H) if b else None
    rows.append((dx + dy, r["id"], dx, dy, tgt))
flagged = 0
for tot, rid, dx, dy, tgt in sorted(rows, reverse=True):
    if tgt:
        bad = tot / tgt > 1.25
        flagged += bad
        print("%-18s %5d %5d %8.0f %6.2f%s" % (rid, dy, dx, tgt, tot / tgt,
                                               "  <-- LONG" if bad else ""))
    else:
        print("%-18s %5d %5d %8s" % (rid, dy, dx, "-"))
print("runs longer than the book: %d of %d" % (flagged, len(rows)))

# ---------------------------------------------------------------- preview
# razavi-textbook-v1 typography, read out of the shipped style profile:
#   fontFamily 'DejaVu Sans',Arial,... (SANS, not a serif face)
#   mathWeight 700 / mathStyle italic ; plainWeight 400
#   annotationFontSize 15.116 ; subscriptScale .76 ; subscriptBaselineShiftEm .28
FONT_STACK = "'DejaVu Sans',Arial,'Helvetica Neue',Helvetica,sans-serif"
BASE_FONT, SUB_SCALE, SUB_SHIFT = 15.116, 0.76, 0.28


def flat(rt):
    """-> [(text, subscript, italic, bold)].

    Matches what the editor actually draws (verified against a real export):
    `italic` and `bold` are independent, and a `subscript` span renders
    UPRIGHT even when nested inside an italic span.
    """
    out = []

    def walk(n, sub, ital, bold):
        if n["kind"] == "text":
            out.append((n["value"], sub, ital, bold))
        elif n["kind"] == "span":
            st = n["style"]
            if st == "subscript":
                c_sub, c_ital = True, False      # renderer resets italic here
            else:
                c_sub, c_ital = sub, ital or st == "italic"
            c_bold = bold or st == "bold"
            for c in n["children"]:
                walk(c, c_sub, c_ital, c_bold)
    for r in rt["runs"]:
        walk(r, False, False, False)
    return out


def prims(sym_id, variant):
    s = SYMS[sym_id]
    base = list(s["primitives"])
    if variant:
        v = next((v for v in s.get("variants", []) if v["id"] == variant),
                 None)
        if v:
            hide = set(v.get("hiddenPrimitiveParts", []))
            base = [p for p in base if p.get("part") not in hide]
            base += v.get("additionalPrimitives", [])
    return base


SYM_S, WIRE_S, JUNC_S, FONT_S = 1.5, 1.5, 1.3, 2.0
P = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="70 60 560 350" '
     'width="1960" height="1225"><rect x="70" y="60" width="560" '
     'height="350" fill="#fff"/><g stroke="#111" fill="none" '
     'stroke-width="1.6">']
VARIANT = {i["id"]: i.get("symbolVariantId") for i in instances}
for iid, (sym_id, x, y, mirror) in PLACED.items():
    sx = -1 if mirror == "x" else 1
    P.append('<g transform="translate(%g,%g) scale(%g,1)">' % (x, y, sx))
    for pr in prims(sym_id, VARIANT.get(iid)):
        w = (2.4 if pr.get("style", {}).get("strokeRole") == "emphasis"
             else 1.6) * SYM_S
        k = pr["kind"]
        if k == "line":
            P.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke-width="%g"/>'
                     % (pr["from"]["x"], pr["from"]["y"], pr["to"]["x"],
                        pr["to"]["y"], w))
        elif k == "path":
            P.append('<path d="%s" stroke-width="%g"/>' % (pr["data"], w))
        elif k in ("polygon", "polyline"):
            pts = " ".join("%g,%g" % (p["x"], p["y"]) for p in pr["points"])
            if k == "polygon":
                P.append('<polygon points="%s" fill="#111" stroke="none"/>'
                         % pts)
            else:
                P.append('<polyline points="%s" stroke-width="%g"/>' % (pts, w))
        elif k == "circle":
            fill = "#111" if pr.get("fill") == "foreground" else "none"
            P.append('<circle cx="%g" cy="%g" r="%g" stroke-width="%g" '
                     'fill="%s"/>'
                     % (pr["center"]["x"], pr["center"]["y"], pr["radius"], w,
                        fill))
    P.append('</g>')

for r in routes:
    pt = axy(r["start"])
    for lg in r["legs"]:
        to = lg["to"]
        nxt = ((to["position"]["x"], to["position"]["y"])
               if to["kind"] == "bend" else axy(to["endpoint"]))
        lw = (3.24 * WIRE_S if r.get("presentation") == "power-rail"
              else 1.6 * WIRE_S)
        P.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke-width="%g"/>'
                 % (pt + nxt + (lw,)))
        pt = nxt

for j in junctions:
    P.append('<circle cx="%g" cy="%g" r="%g" fill="#111" stroke="none"/>'
             % (j["position"]["x"], j["position"]["y"], 2.8 * JUNC_S))
P.append('</g><g font-family="' + FONT_STACK + '" fill="#111">')

LBL = [(o["anchor"]["position"]["x"], o["anchor"]["position"]["y"],
        o["content"], o["alignment"]) for o in drafting]
for a in annotations:
    fb = a["anchor"]["fallbackPosition"]
    if "formatOverride" in a:
        rt = a["formatOverride"]
    elif "content" in a:
        rt = a["content"]
    else:
        rt = next(i for i in instances
                  if i["id"] == a["binding"]["instanceId"])["schematicName"]
    LBL.append((fb["x"], fb["y"], rt, a["alignment"]))

BASE = BASE_FONT * FONT_S * LABEL_SIZE
for x, y, rt, align in LBL:
    parts, prev_sub = [], False
    for t, sub, ital, bold in flat(rt):
        dy = (BASE * SUB_SHIFT if sub and not prev_sub
              else (-BASE * SUB_SHIFT if prev_sub and not sub else 0))
        parts.append('<tspan font-size="%.2f" dy="%.2f" font-style="%s" '
                     'font-weight="%d">%s</tspan>'
                     % (BASE * (SUB_SCALE if sub else 1.0), dy,
                        "italic" if ital else "normal", 700 if bold else 400,
                        t.replace("&", "&amp;").replace("<", "&lt;")))
        prev_sub = sub
    P.append('<text x="%g" y="%g" text-anchor="%s">%s</text>'
             % (x, y, {"start": "start", "middle": "middle",
                       "end": "end"}[align], "".join(parts)))
P.append('</g></svg>')

with open(OUT_SVG, "w", encoding="utf-8") as f:
    f.write("".join(P))
import xml.etree.ElementTree as ET
ET.parse(OUT_SVG)
print("preview written+parsed")
