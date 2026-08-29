# -*- coding: utf-8 -*-
"""Razavi Fig. 9.34: generation of current for pnp devices (Sec. 9.2).

npn reference mirror (I_REF -> Q_REF1 -> Q_M) drives a diode-connected pnp
Q_REF2 that mirrors into Q_2, the active load of the Q_1 output stage.
Built with the spacing rules in SOP.md.
"""
import json, os, hashlib, re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "out")   # .icproj.json lands here
SYMDIR = os.path.join(HERE, "sym")
OUT_PROJ = os.path.join(OUT, "Razavi_Fig_9_34_pnp-current-mirror.icproj.json")
OUT_SVG = os.path.join(HERE, "preview_fig934.svg")

SYMS = {}
for n in ("npn", "pnp", "current-source", "ground", "port",
          "port-filled"):
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


_SUB_RE = re.compile(r"^(.+?)_(?:\{(.+)\}|(.+))$", re.U)


def name(label):
    """Port of the editor's Ws(): 'Q_REF1' -> Rs('Q') + Vs('REF1').

    The underscore form preserves case (Hs() only upper-cases the first letter
    when there is NO underscore), which is what keeps v_out / v_in lowercase.
    """
    m = _SUB_RE.match(label)
    if m:
        return {"runs": [Rs(m.group(1)), Vs(m.group(2) or m.group(3))]}
    return {"runs": [Rs(label)]}




LABEL_SIZE = 0.65      # editor default 1.15, minus three A- presses (-0.1 each)

# ---------------------------------------------------------------- placement
# Columns: QREF1 170 | JB1 230 | QM 300 | QREF2 370 | JB2 430 | Q2/Q1 500
# Rows:    rail 100 | pnp row 150 | node 200 | npn+Q1 row 250 | gnd 300
# Everything is at the hard floor: the BJT base pin already sits 40 units
# from its own centre, so a bus junction cannot be closer than pin+20.
# Column gaps are at the SOP floor: 70-80 units between drawn device edges,
# with the bus junction sitting >=20 clear of both.
# BJT pins: C(0,-30) B(-40,0) E(0,+30) for npn; pnp swaps C/E.
# mirror "x" only flips the base to +40 (the C/E column stays at centre x).
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


def bjt(iid, kind, x, y, mirror, label):
    return place(iid, kind, x, y, mirror, extra={
        "schematicReference": iid, "schematicName": name(label)})


# --- reference leg -----------------------------------------------------------
place("IREF", "current-source", 170, 140, extra={
    "schematicReference": "IREF", "schematicName": name("I_REF"),
    "netlist": {"binding": {"kind": "primitive",
                            "deviceClass": "current-source"},
                "parameters": {}, "reference": "IREF"}})
bjt("QREF1", "npn", 170, 250, "x", "Q_REF1")
place("GND1", "ground", 170, 300, extra={"schematicReference": "GND1"})

# --- mirror device feeding the pnp pair --------------------------------------
bjt("QM", "npn", 300, 250, "none", "Q_M")
place("GND2", "ground", 300, 300, extra={"schematicReference": "GND2"})

# --- pnp mirror --------------------------------------------------------------
bjt("QREF2", "pnp", 370, 150, "x", "Q_REF2")
bjt("Q2", "pnp", 500, 150, "none", "Q_2")

# --- output stage ------------------------------------------------------------
bjt("Q1", "npn", 500, 250, "none", "Q_1")
place("GND3", "ground", 500, 300, extra={"schematicReference": "GND3"})

place("VOUT", "port", 540, 200, mirror="x")
place("VIN", "port", 440, 250)   # STUB_PORT floor: the BJT base lead
                                 # is already 23 units, so use 10 here

# ---------------------------------------------------------------- junctions
junctions = [
    ("jvcc-start", "net-power-vcc", 150, 100),
    ("JV_A", "net-power-vcc", 170, 100),
    ("JV_B", "net-power-vcc", 370, 100),
    ("JV_C", "net-power-vcc", 500, 100),
    ("jvcc-end", "net-power-vcc", 520, 100),
    ("JREF", "net-ref1", 170, 200),
    ("JB1", "net-ref1", 230, 250),
    ("JC2", "net-cm", 370, 200),
    ("JB2", "net-cm", 430, 150),
    ("JOUT", "net-out", 500, 200),
]
junctions = [{"id": i, "netId": n, "position": {"x": x, "y": y},
              "role": "branch"} for i, n, x, y in junctions]


# ---------------------------------------------------------------- nets
def T(iid, pin):
    return {"instanceId": iid, "pinName": pin}


nets = [
    {"id": "net-power-vcc", "terminals": [
        T("IREF", "+"), T("QREF2", "E"), T("Q2", "E")]},
    {"id": "net-ref1", "terminals": [
        T("IREF", "-"), T("QREF1", "C"), T("QREF1", "B"), T("QM", "B")]},
    {"id": "net-cm", "terminals": [
        T("QM", "C"), T("QREF2", "C"), T("QREF2", "B"), T("Q2", "B")]},
    {"id": "net-out", "terminals": [
        T("Q2", "C"), T("Q1", "C"), T("VOUT", "P")]},
    {"id": "net-in", "terminals": [T("Q1", "B"), T("VIN", "P")]},
    {"id": "net-gnd-1", "terminals": [T("GND1", "0"), T("QREF1", "E")]},
    {"id": "net-gnd-2", "terminals": [T("GND2", "0"), T("QM", "E")]},
    {"id": "net-gnd-3", "terminals": [T("GND3", "0"), T("Q1", "E")]},
]

# ---------------------------------------------------------------- routes
routes = []


def term(iid, pin):
    return {"kind": "terminal", "instanceId": iid, "pinName": pin}


def jn(jid):
    return {"kind": "junction", "junctionId": jid}


def route(rid, net_id, start, steps, presentation=None):
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


# V_CC rail: four collinear power-rail segments, overhanging both ends
route("r-vcc-rail-0", "net-power-vcc", jn("jvcc-start"), [("to", jn("JV_A"))],
      presentation="power-rail")
route("r-vcc-rail-1", "net-power-vcc", jn("JV_A"), [("to", jn("JV_B"))],
      presentation="power-rail")
route("r-vcc-rail-2", "net-power-vcc", jn("JV_B"), [("to", jn("JV_C"))],
      presentation="power-rail")
route("r-vcc-rail-3", "net-power-vcc", jn("JV_C"), [("to", jn("jvcc-end"))],
      presentation="power-rail")
route("r-vcc-drop-iref", "net-power-vcc", jn("JV_A"), [("to", term("IREF", "+"))])
route("r-vcc-drop-qref2", "net-power-vcc", jn("JV_B"), [("to", term("QREF2", "E"))])
route("r-vcc-drop-q2", "net-power-vcc", jn("JV_C"), [("to", term("Q2", "E"))])

# npn reference: I_REF -> Q_REF1 (diode-connected) -> Q_M base
route("r-ref-1", "net-ref1", term("IREF", "-"), [("to", jn("JREF"))])
route("r-ref-2", "net-ref1", jn("JREF"), [("to", term("QREF1", "C"))])
route("r-ref-3", "net-ref1", jn("JREF"), [("bend", 230, 200), ("to", jn("JB1"))])
route("r-ref-4", "net-ref1", jn("JB1"), [("to", term("QREF1", "B"))])
route("r-ref-5", "net-ref1", jn("JB1"), [("to", term("QM", "B"))])

# I_C,M : Q_M collector up into the diode-connected pnp Q_REF2
route("r-cm-1", "net-cm", term("QM", "C"), [("bend", 300, 200), ("to", jn("JC2"))])
route("r-cm-2", "net-cm", jn("JC2"), [("to", term("QREF2", "C"))])
route("r-cm-3", "net-cm", jn("JC2"), [("bend", 430, 200), ("to", jn("JB2"))])
route("r-cm-4", "net-cm", jn("JB2"), [("to", term("QREF2", "B"))])
route("r-cm-5", "net-cm", jn("JB2"), [("to", term("Q2", "B"))])

# output node and input
route("r-out-1", "net-out", term("Q2", "C"), [("to", jn("JOUT"))])
route("r-out-2", "net-out", jn("JOUT"), [("to", term("Q1", "C"))])
route("r-out-3", "net-out", jn("JOUT"), [("to", term("VOUT", "P"))])
route("r-in-1", "net-in", term("Q1", "B"), [("to", term("VIN", "P"))])

route("r-g1", "net-gnd-1", term("QREF1", "E"), [("to", term("GND1", "0"))])
route("r-g2", "net-gnd-2", term("QM", "E"), [("to", term("GND2", "0"))])
route("r-g3", "net-gnd-3", term("Q1", "E"), [("to", term("GND3", "0"))])

# ------------------------------------------------- cell terminals for ports
# Name the ports with the underscore form: the schema checks a formatOverride
# against Ws(terminalName), and Ws() only upper-cases the first letter when
# there is NO underscore ("vout" -> "Vout"). "v_out" keeps the lowercase v,
# which is Razavi's small-signal notation -- and then the editor's own default
# rendering is already correct, so no formatOverride is needed at all.
terminals = [
    {"id": "terminal-vout", "name": "v_out", "netId": "net-out",
     "direction": "output", "interfaceInstanceIds": ["VOUT"]},
    {"id": "terminal-vin", "name": "v_in", "netId": "net-in",
     "direction": "input", "interfaceInstanceIds": ["VIN"]},
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


def port_label(iid, tid, dx, dy, alignment):
    _, ix, iy, _ = PLACED[iid]
    annotations.append({
        "id": "instance-label-" + iid, "kind": "instance-label",
        "alignment": alignment, "locked": False, "rotation": 0,
        "sizeScale": LABEL_SIZE,
        "anchor": {"kind": "object", "objectId": iid,
                   "localOffset": {"x": dx, "y": dy},
                   "fallbackPosition": {"x": ix + dx, "y": iy + dy}},
        "binding": {"kind": "cell-terminal-name", "terminalId": tid}})


# Label gap is measured from the DRAWN INK, not the instance centre and not
# the viewBox. Fig 9.83 put MOS labels at centre +/-18 while the MOS ink stops
# at centre +/-10.6 -> an 8-unit gap. The BJT's ink reaches the C/E column,
# which IS the instance centre, so the same 8-unit gap means centre +/-8.
inst_label("IREF", -18, 5, "end")
inst_label("QREF1", -8, 5, "end")
inst_label("QM", 8, 5, "start")
inst_label("QREF2", -8, 5, "end")
inst_label("Q2", 8, 5, "start")
inst_label("Q1", 8, 5, "start")
port_label("VOUT", "terminal-vout", 11, 5, "start")
port_label("VIN", "terminal-vin", -11, 5, "end")

# V_CC power label on the rail end cap
annotations.append({
    "id": "label-vcc", "kind": "power-label", "netId": "net-power-vcc",
    "alignment": "start", "locked": False, "rotation": 0,
    "sizeScale": LABEL_SIZE,
    "anchor": {"kind": "object", "objectId": "jvcc-end",
               "localOffset": {"x": 12, "y": 6},
               "fallbackPosition": {"x": 532, "y": 106}},
    "content": name("V_CC")})

# ---------------------------------------------------------------- drafting
# X_1 / X_2 are the device-count annotations Razavi puts beside each mirror leg
drafting = []

# I_C,M : the textbook placement (confirmed against the user's own manual
# edit) -- the current arrow sits on the VERTICAL collector lead pointing in
# the direction of current flow (down, into Q_M's collector), and the label
# sits to its LEFT at the same height. Done as drafting objects, not a
# route-marker:
# the route-marker's normalOffset left the text sitting on top of the wire and
# orientation "follow" flipped it upside down, and neither is verifiable
# offline -- drafting geometry is exact and renders in the local preview.
drafting.append({
    "id": "arrow-icm", "kind": "arrow", "locked": False, "zIndex": 0,
    "anchor": {"kind": "free", "position": {"x": 300, "y": 200}},
    "from": {"kind": "free", "position": {"x": 300, "y": 200}},
    "to": {"kind": "free", "position": {"x": 300, "y": 220}},
    # NO strokeScale here: annotationStrokeScale (1.5) already lifts the
    # annotation stroke to 1.6*1.5 = 2.4, exactly the wire weight. Adding
    # another 1.5 made the shaft 3.6 -- visibly fatter than the wire.
    "styleOverride": {"arrowHead": "filled", "arrowHeadScale": 1.0}})

for nid, x, y, txt_name in (("note-icm", 287, 224, "I_C,M"),
                            ("note-x1", 224, 284, "X_1"),
                            ("note-x2", 436, 190, "X_2")):
    drafting.append({
        "id": nid, "kind": "text",
        "alignment": "end" if nid == "note-icm" else "start",
        "locked": False,
        "rotation": 0, "zIndex": 0, "typographyToken": "label",
        "styleOverride": {"sizeScale": LABEL_SIZE},
        "anchor": {"kind": "free", "position": {"x": x, "y": y}},
        "content": name(txt_name)})

# ---------------------------------------------------------------- project
project = {
    "documents": [{
        "annotations": annotations,
        "connectivityEvidence": [
            {"id": "cev-vcc-property", "kind": "name-claim",
             "netId": "net-power-vcc", "name": "VCC",
             "owner": {"kind": "explicit-net-property"},
             "scope": "global", "powerDomain": "vdd"},
            {"id": "cev-vcc-marker", "kind": "name-claim",
             "netId": "net-power-vcc", "name": "VCC",
             "owner": {"kind": "power-marker", "objectId": "jvcc-end"},
             "scope": "global", "powerDomain": "vdd"}],
        "constraints": [],
        "drafting": {"objects": drafting},
        "id": "document-main",
        "instances": instances,
        "junctions": junctions,
        "layoutGroups": [],
        "name": "Main",
        "netlist": {"formalParameters": [], "name": "Fig_9_34",
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
    "id": "project-razavi-fig-9-34",
    "name": "Razavi Fig. 9.34 — current generation for pnp devices",
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
RAIL_ENDS = {"jvcc-end", "jvcc-start"}      # rail end-cap carries the power marker only
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
# Source-free check: every straight leg must be <= LEG_BUDGET unless it is a
# declared long haul (rail spans, the I_REF drop, the mirror bus risers).
LEG_BUDGET = 40
LONG_HAUL = {
    "r-vcc-rail-1", "r-vcc-rail-2",   # the V_CC rail itself
    "r-vcc-drop-iref",                # rail -> I_REF, Razavi draws this long
    "r-ref-1",                        # I_REF -> Q_REF1 diode node
    "r-ref-5",                        # Q_REF1 base bus -> Q_M base
    "r-cm-1",                         # Q_M collector riser (carries I_C,M)
    "r-cm-5",                         # pnp base bus -> Q_2
    "r-ref-3", "r-cm-3",              # diode-tie jogs: must clear the device
}
print()
print("%-18s %5s %5s  %s" % ("route", "dy", "dx", "legs"))
over = 0
for r in routes:
    pt = axy(r["start"]); dx = dy = 0; legs = []
    for lg in r["legs"]:
        to = lg["to"]
        nxt = ((to["position"]["x"], to["position"]["y"])
               if to["kind"] == "bend" else axy(to["endpoint"]))
        L = abs(nxt[0] - pt[0]) + abs(nxt[1] - pt[1])
        legs.append(L); dx += abs(nxt[0] - pt[0]); dy += abs(nxt[1] - pt[1])
        pt = nxt
    worst = max(legs)
    bad = worst > LEG_BUDGET and r["id"] not in LONG_HAUL
    over += bad
    print("%-18s %5d %5d  %s%s" % (r["id"], dy, dx, legs,
                                   "  <-- LONG" if bad else ""))
print("legs over the %d-unit budget (excluding declared long hauls): %d"
      % (LEG_BUDGET, over))

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
P = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="80 60 700 330" '
     'width="2100" height="990"><rect x="70" y="60" width="560" '
     'height="330" fill="#fff"/><g stroke="#111" fill="none" '
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

import math as _m
for o in drafting:
    if o["kind"] != "arrow":
        continue
    fx, fy = o["from"]["position"]["x"], o["from"]["position"]["y"]
    tx, ty = o["to"]["position"]["x"], o["to"]["position"]["y"]
    P.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke-width="%g"/>'
             % (fx, fy, tx, ty, 1.6 * WIRE_S))
    ang = _m.atan2(ty - fy, tx - fx)
    h, w = 14, 6
    tri = [(tx, ty),
           (tx - h * _m.cos(ang) + w * _m.sin(ang),
            ty - h * _m.sin(ang) - w * _m.cos(ang)),
           (tx - h * _m.cos(ang) - w * _m.sin(ang),
            ty - h * _m.sin(ang) + w * _m.cos(ang))]
    P.append('<polygon points="%s" fill="#111" stroke="none"/>'
             % " ".join("%.2f,%.2f" % q for q in tri))

for j in junctions:
    P.append('<circle cx="%g" cy="%g" r="%g" fill="#111" stroke="none"/>'
             % (j["position"]["x"], j["position"]["y"], 2.8 * JUNC_S))
P.append('</g><g font-family="' + FONT_STACK + '" fill="#111">')

LBL = [(o["anchor"]["position"]["x"], o["anchor"]["position"]["y"],
        o["content"], o["alignment"]) for o in drafting if o["kind"] == "text"]
for a in annotations:
    fb = a["anchor"]["fallbackPosition"]
    if "formatOverride" in a:
        rt = a["formatOverride"]
    elif "content" in a:
        rt = a["content"]
    elif a["binding"]["kind"] == "cell-terminal-name":
        rt = name(next(t for t in terminals
                       if t["id"] == a["binding"]["terminalId"])["name"])
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
