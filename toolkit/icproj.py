# -*- coding: utf-8 -*-
"""icproj.py — the reusable 80% of an Analog Canvas figure generator.

A new figure script only declares placement / junctions / nets / routes /
annotations and calls `fig.build()`.  Everything else (schema assembly, the
self-check, the leg audit, the LABEL audit, the SVG preview) lives here.

    from icproj import Schematic
    f = Schematic("project-razavi-fig-x", "Razavi Fig. X", "Fig_X",
                  out_proj=r"...\\Name.icproj.json", out_svg="preview_x.svg")
    f.mos("M1", "nmos", 200, 230, "none", "M_1")
    ...
    f.build(long_haul={...}, viewbox=(100, 75, 400, 310))

Constants and rules come from SOP.md; the ones this file
enforces automatically are:
  §3A  leg budget 40 units unless declared in `long_haul`
  §3A  labels sit at the drawn-ink edge + 8
  §4   label box geometry, used by the two automatic label checks:
         - LABEL OVERLAPS WIRE   : text must never sit on a line
         - LABEL AMBIGUOUS       : the neighbour on the label's side must be
                                   >= 20 from the text, or the reader cannot
                                   tell which device the label names
  §3E  a component may not sit on a wire belonging to another net
  §6   junctions may not share a coordinate with a terminal (zero-length route)
"""
import json, os, hashlib, re, math

HERE = os.path.dirname(os.path.abspath(__file__))
SYMDIR = os.path.join(HERE, "sym")

# --- typography (razavi-textbook-v1, bundle dist-DMiczVQI.js) ---------------
BASE_FONT, SUB_SCALE, SUB_SHIFT = 15.116, 0.76, 0.28
FONT_STACK = "'DejaVu Sans',Arial,'Helvetica Neue',Helvetica,sans-serif"
LABEL_SIZE = 0.58          # BASE = 17.53 units = Razavi's own label
                           # size (measured: cap 12.28 units on the
                           # Fig 10.35 page).  Because the type now
                           # matches the book, every clearance measured
                           # off a textbook page can be used directly --
                           # no more 1.2x correction factor.
FONT_SCALE = 2.0
HERE_TOOLKIT = os.path.dirname(os.path.abspath(__file__))
SCHEMA_VERSION = 31        # keep in step with refresh_model.py
LEG_BUDGET = 40
LABEL_INK_GAP = 8
LABEL_PORT = 14            # port label offset from the port CENTRE.  The
                           # circle edge sits at 9.57, so this leaves a 4.4-unit
                           # gap; the printed figure gets away with 1.1 only
                           # because its circle is twice the diameter of ours.
                           # (Approved 2026-08-29.  A dragged adjustment in the
                           # editor snaps by a whole grid step to 21, which is
                           # too far -- change this constant instead.)
CROWD_MIN = 6              # tightest acceptable ink-to-ink clearance.  The
                           # user accepted 7.0-7.1 (Fig 14.36 caps, Fig 5.170
                           # R_E1/C_2) but not 0.6.
NEIGHBOUR_GAP = 17         # measured off Razavi's page (M_3: 16.8, M_4: 17.2)
VERT_GAP = 1.5             # clearance for a label placed above/below a
                           # component (user-tuned; the sideways one is
                           # LABEL_INK_GAP = 8)

_SYMS = {}


def sym(sid):
    if sid not in _SYMS:
        with open(os.path.join(SYMDIR, sid + ".json"), encoding="utf-8") as f:
            _SYMS[sid] = json.load(f)
    return _SYMS[sid]


def hid(*p):
    return hashlib.sha256("|".join(map(str, p)).encode()).hexdigest()[:16]


# --- the editor's own RichText builders (packages/model), verbatim ----------
ITALIC_SUBSCRIPTS = {"dd", "ss", "cc", "ee", "bb"}
_SUB_RE = re.compile(r"^(.+?)_(?:\{(.+)\}|(.+))$", re.U)


def _txt(v):
    return {"kind": "text", "value": v}


def _span(style, children):
    return {"kind": "span", "style": style, "children": children}


def Rs(t):
    return _span("italic", [_span("bold", [_txt(t)])])


def Vs(t):
    inner = _span("bold", [_txt(t)])
    if t.strip().lower() in ITALIC_SUBSCRIPTS:
        inner = _span("italic", [inner])
    return _span("subscript", [inner])


def name(label):
    """Port of the editor's Ws(): 'V_in1' -> Rs('V') + Vs('in1').

    The underscore form preserves case (Hs() only upper-cases the first letter
    when there is NO underscore), which is what keeps v_out lowercase when the
    textbook writes it that way.
    """
    m = _SUB_RE.match(label)
    if m:
        return {"runs": [Rs(m.group(1)), Vs(m.group(2) or m.group(3))]}
    return {"runs": [Rs(label)]}


def name_suffix(label, suffix):
    """'V_DD' + ' = 1.8 V' -> the composite Razavi prints on a supply rail.

    NOTE: check_labels.mjs reports DIFFER for these -- it rebuilds the name as
    'V = 1.8 V_DD'.  Known false positive, not a defect; Fig 9.83 shipped so.
    """
    return {"runs": name(label)["runs"] + [_span("bold", [_txt(suffix)])]}


def plain(text):
    """Upright bold, for a VALUE such as "50 Ω" -- Razavi does
    not italicise numeric values, only symbol names."""
    return {"runs": [_span("bold", [_txt(text)])]}


def flat(rt):
    """RichText -> [(text, subscript, italic, bold)] as the SVG renderer sees
    it: a `subscript` span renders UPRIGHT even inside an italic span."""
    out = []

    def walk(n, sub, ital, bold):
        if n["kind"] == "text":
            out.append((n["value"], sub, ital, bold))
        elif n["kind"] == "span":
            st = n["style"]
            if st == "subscript":
                c_sub, c_ital = True, False
            else:
                c_sub, c_ital = sub, ital or st == "italic"
            for c in n["children"]:
                walk(c, c_sub, c_ital, bold or st == "bold")
    for r in rt["runs"]:
        walk(r, False, False, False)
    return out


def prims(sym_id, variant):
    s = sym(sym_id)
    base = list(s["primitives"])
    if variant:
        v = next((v for v in s.get("variants", []) if v["id"] == variant), None)
        if v:
            hide = set(v.get("hiddenPrimitiveParts", []))
            base = [p for p in base if p.get("part") not in hide]
            base += v.get("additionalPrimitives", [])
    return base


_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def xf(px, py, mirror, rotation):
    """Local symbol point -> placed point: mirror first, then rotation.

    Rotation follows the repo's own rotatePointByDegrees (canvas-geometry.ts):
    x' = x*cos - y*sin, y' = x*sin + y*cos.  At 90 degrees that sends pin "1"
    of a passive (0,-20) to the RIGHT and pin "2" to the LEFT, which is how a
    horizontal capacitor comes out.
    """
    if mirror == "x":
        px = -px
    elif mirror == "y":
        py = -py
    if rotation:
        r = math.radians(rotation)
        c, sn = math.cos(r), math.sin(r)
        px, py = px * c - py * sn, px * sn + py * c
    return px, py


def ink_box(sym_id, variant, x, y, mirror, rotation=0):
    """Bounding box of the DRAWN primitives (SOP: never use the viewBox)."""
    xs, ys = [], []

    def add(px, py):
        a, b = xf(px, py, mirror, rotation)
        xs.append(a)
        ys.append(b)
    for pr in prims(sym_id, variant):
        k = pr["kind"]
        if k == "line":
            add(pr["from"]["x"], pr["from"]["y"])
            add(pr["to"]["x"], pr["to"]["y"])
        elif k in ("polygon", "polyline"):
            for p in pr["points"]:
                add(p["x"], p["y"])
        elif k == "circle":
            c, r = pr["center"], pr["radius"]
            add(c["x"] - r, c["y"] - r)
            add(c["x"] + r, c["y"] + r)
        elif k == "path":
            n = [float(v) for v in _NUM_RE.findall(pr["data"])]
            for i in range(0, len(n) - 1, 2):
                add(n[i], n[i + 1])
    return (x + min(xs), y + min(ys), x + max(xs), y + max(ys))


# DejaVu Sans Bold advance widths, em units -- the face razavi-textbook-v1
# actually renders with.  Measured against the textbook page: with sizeScale
# 0.65 our labels come out 1.21x the size of Razavi's print, so every
# label-driven clearance has to scale up by the same factor (SOP §4).
_ADV = {" ": .348, ",": .380, ".": .380, "-": .415, "+": .838, "=": .838,
        "A": .774, "B": .762, "C": .796, "D": .830, "E": .683, "F": .683,
        "G": .821, "H": .837, "I": .372, "J": .372, "K": .775, "L": .637,
        "M": 1.005, "N": .837, "O": .850, "P": .733, "Q": .850, "R": .770,
        "S": .720, "T": .682, "U": .812, "V": .774, "W": 1.104, "X": .774,
        "Y": .724, "Z": .682,
        "a": .675, "b": .716, "c": .593, "d": .716, "e": .678, "f": .435,
        "g": .716, "h": .712, "i": .343, "j": .343, "k": .665, "l": .343,
        "m": 1.042, "n": .712, "o": .687, "p": .716, "q": .716, "r": .493,
        "s": .595, "t": .478, "u": .712, "v": .652, "w": .924, "x": .652,
        "y": .652, "z": .582}


def text_width(rt, size=LABEL_SIZE):
    base = BASE_FONT * FONT_SCALE * size
    w = 0.0
    for t, sub, _i, _b in flat(rt):
        adv = sum(_ADV.get(c, .696 if c.isdigit() else .700) for c in t)
        w += adv * base * (SUB_SCALE if sub else 1.0)
    return w


def label_box(rt, x, y, align, size=LABEL_SIZE):
    """Text box from the real advance widths (SOP §4)."""
    base = BASE_FONT * FONT_SCALE * size
    w = text_width(rt, size)
    has_sub = any(sub for _t, sub, _i, _b in flat(rt))
    x0 = {"start": x, "middle": x - w / 2.0, "end": x - w}[align]
    top = y - base * 0.70
    bot = y + (base * SUB_SHIFT if has_sub else base * 0.02)
    return (x0, top, x0 + w, bot)


def cap_height(size=LABEL_SIZE):
    return 0.70 * BASE_FONT * FONT_SCALE * size


def descent(size=LABEL_SIZE):
    """How far a subscript hangs below the baseline."""
    return SUB_SHIFT * BASE_FONT * FONT_SCALE * size


def dy_above(ink_half, gap=VERT_GAP, sub=True, size=LABEL_SIZE):
    """localOffset.y for a label sitting ABOVE a component.

    The box bottom has to clear the ink by `gap`, and the box bottom is the
    baseline plus whatever a subscript hangs down.
    """
    return -round(ink_half + gap + (descent(size) if sub else 0.0))


def dy_below(ink_half, gap=VERT_GAP, size=LABEL_SIZE):
    """localOffset.y for a label sitting BELOW a component: the box TOP is one
    cap height above the baseline."""
    return round(ink_half + gap + cap_height(size))


def _crosses(box, seg):
    """True when an axis-aligned wire enters one side of an ink box and leaves
    by the other -- i.e. it is drawn straight through the component body.

    Ending ON a component (a pin lead) is not crossing: the segment then stops
    inside or at the edge, so it fails the "extends beyond on BOTH sides" test.
    """
    bx0, by0, bx1, by1 = box
    x0, y0, x1, y1 = seg
    if y0 == y1:                                     # horizontal
        return (by0 < y0 < by1
                and min(x0, x1) < bx0 and max(x0, x1) > bx1)
    if x0 == x1:                                     # vertical
        return (bx0 < x0 < bx1
                and min(y0, y1) < by0 and max(y0, y1) > by1)
    return False


def _box_gap(b, seg):
    """Distance from box b to an axis-aligned segment seg=(x0,y0,x1,y1)."""
    sx0, sx1 = sorted((seg[0], seg[2]))
    sy0, sy1 = sorted((seg[1], seg[3]))
    dx = max(b[0] - sx1, sx0 - b[2], 0.0)
    dy = max(b[1] - sy1, sy0 - b[3], 0.0)
    return math.hypot(dx, dy)


def _box_gap_box(a, b):
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(dx, dy)


class Schematic(object):
    def __init__(self, project_id, project_name, netlist_name,
                 out_proj, out_svg, nmos_bulk_net="net-gnd-1",
                 supply_net="net-power-vdd", rail_end="jvdd-end",
                 supply_name="VDD"):
        self.pid, self.pname, self.nname = project_id, project_name, netlist_name
        self.out_proj, self.out_svg = out_proj, out_svg
        self.nmos_bulk_net, self.supply_net = nmos_bulk_net, supply_net
        self.rail_end, self.supply_name = rail_end, supply_name
        self.instances, self.placed = [], {}
        self.junctions, self.nets, self.routes = [], [], []
        self.terminals, self.annotations, self.drafting = [], [], []
        self._text_owner = {}          # value labels declare their component

    # ---------------------------------------------------------- placement
    # Symbols whose geometry exists somewhere in the deployment but which the
    # site's symbol CATALOG does not register.  A project that uses one parses
    # against the schema, validates, and then silently fails to import.
    # 2026-08-30: `vdd` cost a whole round trip.  Checked with
    #   grep -c 'symbolId:`vdd`,' <bundle chunk>   ->  0
    UNPLACEABLE = {"vdd": "use `vdd-port` (same pin at (0,+20))",
                   "ndmos": "no geometry anywhere; needs a PDK",
                   "pdmos": "no geometry anywhere; needs a PDK"}

    def place(self, iid, symbol_id, x, y, mirror="none", extra=None,
              rotation=0):
        assert x % 10 == 0 and y % 10 == 0, (iid, x, y)
        assert rotation in (0, 90, 180, 270), rotation
        if symbol_id in self.UNPLACEABLE:
            raise ValueError(
                "symbol %r is not placeable -- the site's catalog has no entry "
                "for it, so the project imports as a blank canvas: %s"
                % (symbol_id, self.UNPLACEABLE[symbol_id]))
        inst = {"id": iid, "symbolId": symbol_id,
                "placement": {"mirror": mirror, "position": {"x": x, "y": y},
                              "rotation": rotation}}
        if extra:
            inst.update(extra)
        self.instances.append(inst)
        self.placed[iid] = (symbol_id, x, y, mirror, rotation)
        return iid

    def passive(self, iid, kind, x, y, label, rotation=0, extra_style=None):
        """kind: 'resistor' | 'capacitor' | 'inductor'.

        `extra_style` is the instance styleOverride, e.g.
        {"foreground": "#E03127"} to draw the part in the red the page uses
        for something added by the analysis.
        """
        st = {"styleOverride": extra_style} if extra_style else {}
        return self.place(iid, kind, x, y, rotation=rotation, extra=dict(st, **{
            "schematicReference": iid, "schematicName": name(label),
            "netlist": {"binding": {"kind": "primitive", "deviceClass": kind},
                        "parameters": {}, "reference": iid}}))

    def mos(self, iid, kind, x, y, mirror, label):
        binding = ({"netId": self.nmos_bulk_net, "origin": "cell-default"}
                   if kind == "nmos"
                   else {"netId": self.supply_net, "origin": "supply-default"})
        return self.place(iid, kind, x, y, mirror, extra={
            "symbolVariantId": "textbook-3terminal",
            "schematicReference": iid, "schematicName": name(label),
            "mosBulkBinding": binding})

    def bjt(self, iid, kind, x, y, mirror, label):
        return self.place(iid, kind, x, y, mirror, extra={
            "schematicReference": iid, "schematicName": name(label)})

    def isrc(self, iid, x, y, label, mirror="none", rotation=0):
        """rotation=180 turns the arrow UP (and swaps which pin is on top),
        which is how a source that pushes INTO a node from ground is drawn."""
        return self.place(iid, "current-source", x, y, mirror, rotation=rotation,
                          extra={
                              "schematicReference": iid,
                              "schematicName": name(label),
                              "netlist": {"binding": {"kind": "primitive",
                                          "deviceClass": "current-source"},
                              "parameters": {}, "reference": iid}})

    def gnd(self, iid, x, y):
        return self.place(iid, "ground", x, y,
                          extra={"schematicReference": iid})

    def port(self, iid, x, y, mirror="none", filled=False):
        return self.place(iid, "port-filled" if filled else "port", x, y,
                          mirror)

    def pin(self, iid, pinname):
        sym_id, x, y, mirror, rot = self.placed[iid]
        for p in sym(sym_id)["pins"]:
            if p["name"] == pinname:
                px, py = xf(p["at"]["x"], p["at"]["y"], mirror, rot)
                return (x + round(px), y + round(py))
        raise KeyError((iid, sym_id, pinname))

    DIRV = {"north": (0, -1), "south": (0, 1),
            "west": (-1, 0), "east": (1, 0)}

    def pin_dir(self, iid, pinname):
        """Outward escape direction of a pin, after mirror and rotation."""
        sym_id, _x, _y, mirror, rot = self.placed[iid]
        for pdef in sym(sym_id)["pins"]:
            if pdef["name"] == pinname:
                d = pdef.get("direction")
                if not d:
                    return None
                vx, vy = xf(*self.DIRV[d], mirror=mirror, rotation=rot)
                return (round(vx), round(vy))
        raise KeyError((iid, sym_id, pinname))

    def ink(self, iid):
        sym_id, x, y, mirror, rot = self.placed[iid]
        variant = next((i.get("symbolVariantId") for i in self.instances
                        if i["id"] == iid), None)
        return ink_box(sym_id, variant, x, y, mirror, rot)

    # ---------------------------------------------------------- topology
    def junction(self, jid, net_id, x, y, role="branch"):
        self.junctions.append({"id": jid, "netId": net_id,
                               "position": {"x": x, "y": y}, "role": role})
        return jid

    def net(self, net_id, terminals):
        """terminals: [(instanceId, pinName), ...]"""
        self.nets.append({"id": net_id, "terminals": [
            {"instanceId": i, "pinName": p} for i, p in terminals]})

    def term(self, iid, pinname):
        return {"kind": "terminal", "instanceId": iid, "pinName": pinname}

    def jn(self, jid):
        return {"kind": "junction", "junctionId": jid}

    def route(self, rid, net_id, start, steps, presentation=None):
        legs = []
        for i, s in enumerate(steps):
            lid = hid(rid, i)
            if s[0] == "bend":
                legs.append({"id": "route-leg-" + lid, "mode": "manual",
                             "to": {"kind": "bend",
                                    "bendId": "route-bend-" + lid,
                                    "position": {"x": s[1], "y": s[2]}}})
            else:
                legs.append({"id": "route-leg-" + lid, "mode": "manual",
                             "to": {"kind": "endpoint", "endpoint": s[1]}})
        r = {"id": rid, "netId": net_id, "start": start, "legs": legs}
        if presentation:
            r["presentation"] = presentation
        self.routes.append(r)

    def rail(self, net_id, y, xs, prefix="r-vdd-rail"):
        """xs = [start, tap..., end]; emits collinear power-rail segments."""
        for i in range(len(xs) - 1):
            self.route("%s-%d" % (prefix, i), net_id,
                       self.jn(self._jat(xs[i], y)),
                       [("to", self.jn(self._jat(xs[i + 1], y)))],
                       presentation="power-rail")

    def _jat(self, x, y):
        for j in self.junctions:
            if j["position"]["x"] == x and j["position"]["y"] == y:
                return j["id"]
        raise KeyError("no junction at (%s,%s)" % (x, y))

    def terminal(self, tid, tname, net_id, direction, instance_ids):
        self.terminals.append({"id": tid, "name": tname, "netId": net_id,
                               "direction": direction,
                               "interfaceInstanceIds": instance_ids})

    # ---------------------------------------------------------- labels
    def _anchor(self, iid, dx, dy):
        ix, iy = self.placed[iid][1], self.placed[iid][2]
        return {"kind": "object", "objectId": iid,
                "localOffset": {"x": dx, "y": dy},
                "fallbackPosition": {"x": ix + dx, "y": iy + dy}}

    def inst_label(self, iid, dx, dy, alignment, color=None):
        self.annotations.append({
            "id": "instance-label-" + iid, "kind": "instance-label",
            "alignment": alignment, "locked": False, "rotation": 0,
            "sizeScale": LABEL_SIZE, "anchor": self._anchor(iid, dx, dy),
            "binding": {"kind": "instance-schematic-name", "instanceId": iid}})
        if color:
            raise ValueError(
                "an instance-label cannot carry a colour: the schema has no "
                "styleOverride on annotations (it rejects the whole project "
                "with `annotations.N | unrecognized_keys`).  Drop the "
                "inst_label and write the name as drafting text instead: "
                "f.text(tid, x, y, align, name(...), owner=iid, color=...)")

    def port_label(self, iid, tid, dx, dy, alignment):
        """A port label bound to a cell terminal ALWAYS needs a formatOverride.

        Left to itself the editor runs the terminal name through its own
        builder, which subscripts a trailing capital run: `IN` renders as
        I with a subscript N, `CK` as C_K, `Out` as O_ut (user, 2026-08-30).
        Our `name()` only subscripts after an underscore, which is what the
        textbook does -- so hand the editor the finished RichText.
        (Fig 9.83's hand-written generator always did this; the shared engine
        lost it, and five labels across four figures were rendering wrong.)
        """
        term = next((t for t in self.terminals if t["id"] == tid), None)
        if term is None:
            raise KeyError("declare f.terminal(%r, ...) before its label" % tid)
        self.annotations.append({
            "id": "instance-label-" + iid, "kind": "instance-label",
            "alignment": alignment, "locked": False, "rotation": 0,
            "sizeScale": LABEL_SIZE, "anchor": self._anchor(iid, dx, dy),
            "binding": {"kind": "cell-terminal-name", "terminalId": tid},
            "formatOverride": name(term["name"])})

    def power_label(self, lid, net_id, obj_id, dx, dy, label,
                    alignment="start"):
        self.annotations.append({
            "id": lid, "kind": "power-label", "netId": net_id,
            "alignment": alignment, "locked": False, "rotation": 0,
            "sizeScale": LABEL_SIZE, "anchor": self._anchor(obj_id, dx, dy)
            if obj_id in self.placed else {
                "kind": "object", "objectId": obj_id,
                "localOffset": {"x": dx, "y": dy},
                "fallbackPosition": self._jxy(obj_id, dx, dy)},
            # a rail label is often "name + value" (V_CC = 2.5 V), so accept a
            # ready-made RichText the way text() does
            "content": label if isinstance(label, dict) else name(label)})

    def _jxy(self, jid, dx, dy):
        for j in self.junctions:
            if j["id"] == jid:
                return {"x": j["position"]["x"] + dx,
                        "y": j["position"]["y"] + dy}
        raise KeyError(jid)

    def text(self, tid, x, y, alignment, label, owner=None, color=None):
        """`label` is a name string, or a RichText dict from
        name_suffix()/plain() for composite or value text."""
        self.drafting.append({
            "id": tid, "kind": "text", "alignment": alignment, "locked": False,
            "rotation": 0, "zIndex": 0, "typographyToken": "label",
            "styleOverride": {"sizeScale": LABEL_SIZE},
            "anchor": {"kind": "free", "position": {"x": x, "y": y}},
            "content": label if isinstance(label, dict) else name(label)})
        if color:
            raise ValueError(
                "drafting text ignores styleOverride.color on the site.  Its "
                "renderer only passes the colour through the formula path and "
                "the polarity path; ordinary runs go through `re()` and are "
                "emitted as <text> with NO fill, so they come out black "
                "(bundle dist-CE3Pi34B.js, function De).  Arrows and component "
                "instances DO take a colour -- text does not, so do not mix "
                "the two or the picture reads as half-finished.")
        return tid
        if owner:
            self._text_owner[tid] = owner

    def rect(self, rid, cx, cy, w, h, style="solid"):
        """A drafting rectangle -- block-diagram boxes (FF, VCO, Latch) and
        the layer stacks that ESD papers draw next to the schematic."""
        self.drafting.append({
            "id": rid, "kind": "rectangle", "locked": False, "zIndex": 0,
            "center": {"x": cx, "y": cy}, "width": int(w), "height": int(h),
            "rotation": 0, "lineStyle": style,
            "anchor": {"kind": "free", "position": {"x": cx, "y": cy}}})

    def construction(self, cid, x0, y0, x1, y1):
        """A drafting line, for the one thing routes cannot draw: a DIAGONAL.

        Analog Canvas routes are orthogonal only (the editor enforces it too),
        so a textbook X -- cross-coupled drains -- has no routable form.
        Construction lines do not conduct: the two devices stay on separate
        nets, so an exported netlist loses that connection.  Fine for figures.
        """
        self.drafting.append({
            "id": cid, "kind": "construction-line", "locked": False,
            "zIndex": 0, "lineStyle": "dashed",
            "styleOverride": {"lineStyle": "solid"},
            "anchor": {"kind": "free", "position": {"x": x0, "y": y0}},
            "points": [{"x": x0, "y": y0}, {"x": x1, "y": y1}]})

    def arrow(self, aid, x0, y0, x1, y1, head_scale=1.0, color=None):
        """Current arrow.  NEVER add strokeScale here: annotationStrokeScale
        already puts the shaft at the wire weight (SOP §6B)."""
        self.drafting.append({
            "id": aid, "kind": "arrow", "locked": False, "zIndex": 0,
            "anchor": {"kind": "free", "position": {"x": x0, "y": y0}},
            "from": {"kind": "free", "position": {"x": x0, "y": y0}},
            "to": {"kind": "free", "position": {"x": x1, "y": y1}},
            "styleOverride": {"arrowHead": "filled",
                              "arrowHeadScale": head_scale}})
        if color:
            self.drafting[-1].setdefault("styleOverride", {})["color"] = color
        return aid

    # ---------------------------------------------------------- geometry
    def _axy(self, a):
        if a["kind"] == "terminal":
            return self.pin(a["instanceId"], a["pinName"])
        for j in self.junctions:
            if j["id"] == a["junctionId"]:
                return (j["position"]["x"], j["position"]["y"])
        raise KeyError(a)

    def segments(self):
        out = []
        for r in self.routes:
            pt = self._axy(r["start"])
            for lg in r["legs"]:
                to = lg["to"]
                nxt = ((to["position"]["x"], to["position"]["y"])
                       if to["kind"] == "bend" else self._axy(to["endpoint"]))
                out.append((r["id"], pt[0], pt[1], nxt[0], nxt[1]))
                pt = nxt
        return out

    def label_records(self):
        """[(id, richtext, x, y, alignment, owner_instance_or_None)]"""
        recs = []
        self._text_colour = {}
        for o in self.drafting:
            if o["kind"] == "text":
                p = o["anchor"]["position"]
                recs.append((o["id"], o["content"], p["x"], p["y"],
                             o["alignment"], self._text_owner.get(o["id"])))
                self._text_colour[o["id"]] = (
                    o.get("styleOverride") or {}).get("color")
        for a in self.annotations:
            fb = a["anchor"]["fallbackPosition"]
            if "content" in a:
                rt = a["content"]
            elif a["binding"]["kind"] == "cell-terminal-name":
                rt = name(next(t for t in self.terminals
                               if t["id"] == a["binding"]["terminalId"])["name"])
            else:
                rt = next(i for i in self.instances
                          if i["id"] == a["binding"]["instanceId"])["schematicName"]
            owner = a.get("binding", {}).get("instanceId") \
                or a["anchor"].get("objectId")
            recs.append((a["id"], rt, fb["x"], fb["y"], a["alignment"], owner))
        return recs

    # ---------------------------------------------------------- build
    def build(self, long_haul=(), rail_ends=(), viewbox=(100, 75, 400, 310),
              extra_evidence=None, verbose=True, density_ref=None,
              expect_differ=()):
        long_haul, rail_ends = set(long_haul), set(rail_ends)
        self._long_haul = long_haul
        doc = {
            "annotations": self.annotations,
            "connectivityEvidence": extra_evidence
            if extra_evidence is not None else [
                {"id": "cev-vdd-property", "kind": "name-claim",
                 "netId": self.supply_net, "name": self.supply_name,
                 "owner": {"kind": "explicit-net-property"},
                 "scope": "global", "powerDomain": "vdd"},
                {"id": "cev-vdd-marker", "kind": "name-claim",
                 "netId": self.supply_net, "name": self.supply_name,
                 "owner": {"kind": "power-marker", "objectId": self.rail_end},
                 "scope": "global", "powerDomain": "vdd"}],
            "constraints": [],
            "drafting": {"objects": self.drafting},
            "id": "document-main",
            "instances": self.instances,
            "junctions": self.junctions,
            "layoutGroups": [],
            "mosBulkDefaults": {"nmosNetId": self.nmos_bulk_net},
            "name": "Main",
            "netlist": {"formalParameters": [], "name": self.nname,
                        "terminals": self.terminals},
            "nets": self.nets,
            "noConnects": [],
            "presentation": {"compactness": "compact", "grid": 10,
                             "styleProfileId": "razavi-textbook-v1",
                             "styleOverrides": {"symbolStrokeScale": 1.5,
                                                "wireStrokeScale": 1.5,
                                                "annotationStrokeScale": 1.5,
                                                "junctionRadiusScale": 1.3,
                                                "fontScale": FONT_SCALE}},
            "revision": 0,
            "routes": self.routes,
            "sourceStatus": "in-sync",
        }
        if not any(i.get("mosBulkBinding") for i in self.instances):
            del doc["mosBulkDefaults"]
        project = {
            "documents": [doc],
            "externalSubcircuitDefinitions": [],
            "id": self.pid,
            "name": self.pname,
            "schemaVersion": SCHEMA_VERSION,
            "source": {"dialect": "none", "entry": None, "files": [],
                       "sourcePolicy": "copy"},
            "structureRevision": 0,
            "symbolLibrary": {"hash": "razavi-reference-v1",
                              "id": "razavi-symbols", "version": "1"},
            "topDocumentId": "document-main",
        }

        errs = self._selfcheck(rail_ends)
        print("self-check errors:", len(errs))
        for e in errs:
            print("  !", e)

        with open(self.out_proj, "w", encoding="utf-8") as f:
            json.dump(project, f, ensure_ascii=False, indent=2)
        print("wrote", os.path.getsize(self.out_proj), "bytes ->",
              os.path.basename(self.out_proj))

        if verbose:
            # One summary line when everything is clean; each audit still
            # prints its own detail lines above whenever it finds something.
            legs = self._leg_audit(long_haul)
            labels = self._label_audit()
            onwire = self._wire_clearance()
            tees = self._tee_audit()
            print("audits: legs %d | labels %d | on-wire %d | tees %d"
                  "   (all must be 0)" % (legs, labels, onwire, tees))
            self._crowding()
            self._pitch()
            self._density(density_ref)
        self._preview(viewbox)
        if verbose:
            self._verify(expect_differ)
        return project

    # ---------------------------------------------------------- checks
    def _selfcheck(self, rail_ends):
        errs = []
        self.warnings = []
        net_ids = {n["id"] for n in self.nets}
        jpos = {j["id"]: (j["position"]["x"], j["position"]["y"])
                for j in self.junctions}
        for n in self.nets:
            for t in n["terminals"]:
                self.pin(t["instanceId"], t["pinName"])
        # §6: a junction may not sit on a terminal
        pinpos = {}
        for n in self.nets:
            for t in n["terminals"]:
                pinpos[self.pin(t["instanceId"], t["pinName"])] = \
                    "%s.%s" % (t["instanceId"], t["pinName"])
        for jid, p in jpos.items():
            if p in pinpos:
                errs.append("junction %s sits on terminal %s at %s"
                            % (jid, pinpos[p], p))
        routed = set()
        for r in self.routes:
            if r["netId"] not in net_ids:
                errs.append("route %s unknown net" % r["id"])
        for rid, x0, y0, x1, y1 in self.segments():
            if x0 != x1 and y0 != y1:
                errs.append("route %s not orthogonal (%s,%s)->(%s,%s)"
                            % (rid, x0, y0, x1, y1))
            if (x0, y0) == (x1, y1):
                errs.append("route %s zero-length at (%s,%s)" % (rid, x0, y0))
        for r in self.routes:
            if r["start"]["kind"] == "terminal":
                routed.add((r["start"]["instanceId"], r["start"]["pinName"]))
            for lg in r["legs"]:
                to = lg["to"]
                if to["kind"] == "endpoint" \
                        and to["endpoint"]["kind"] == "terminal":
                    routed.add((to["endpoint"]["instanceId"],
                                to["endpoint"]["pinName"]))
        for n in self.nets:
            # Two pins placed at the SAME point are connected with no wire at
            # all -- that is how the textbook gets a resistor to sit straight
            # on a ground symbol, and it saves the 10-unit stub each time
            # (user's own edit to Fig 8.69, 2026-08-29).
            pos = {}
            for t in n["terminals"]:
                if t["pinName"] != "B":
                    pos.setdefault(self.pin(t["instanceId"], t["pinName"]),
                                   []).append((t["instanceId"], t["pinName"]))
            coincident = {k for v in pos.values() if len(v) > 1 for k in v}
            for t in n["terminals"]:
                if t["pinName"] == "B":
                    continue                 # hidden bulk: bound, not routed
                key = (t["instanceId"], t["pinName"])
                if key not in routed and key not in coincident:
                    errs.append("unrouted terminal %s.%s in %s"
                                % (t["instanceId"], t["pinName"], n["id"]))
        touch = {}
        for r in self.routes:
            ends = [r["start"]] + [lg["to"].get("endpoint") for lg in r["legs"]
                                   if lg["to"]["kind"] == "endpoint"]
            for a in ends:
                if a and a["kind"] == "junction":
                    touch[a["junctionId"]] = touch.get(a["junctionId"], 0) + 1
        for j in self.junctions:
            if j["id"] in rail_ends:
                continue
            if touch.get(j["id"], 0) < 2:
                errs.append("junction %s touched %d times"
                            % (j["id"], touch.get(j["id"], 0)))
        return errs

    def _leg_audit(self, long_haul):
        """Print only the offenders.  The full table is 25+ lines of noise on
        a clean figure and I re-run generators a dozen times per drawing;
        `AC_VERBOSE=1` brings it back when a layout needs studying."""
        loud = os.environ.get("AC_VERBOSE")
        if loud:
            print()
            print("%-14s %5s %5s  %s" % ("route", "dy", "dx", "legs"))
        over = 0
        for r in self.routes:
            pt = self._axy(r["start"])
            dx = dy = 0
            legs = []
            for lg in r["legs"]:
                to = lg["to"]
                nxt = ((to["position"]["x"], to["position"]["y"])
                       if to["kind"] == "bend" else self._axy(to["endpoint"]))
                legs.append(abs(nxt[0] - pt[0]) + abs(nxt[1] - pt[1]))
                dx += abs(nxt[0] - pt[0])
                dy += abs(nxt[1] - pt[1])
                pt = nxt
            bad = max(legs) > LEG_BUDGET and r["id"] not in long_haul
            over += bad
            if loud or bad:
                print("%-14s %5d %5d  %s%s" % (r["id"], dy, dx, legs,
                                               "  <-- LONG" if bad else ""))
        return over

    def _label_audit(self):
        """SOP §4: text must never sit on a wire, and a label must be closer
        to its own device than to any neighbour."""
        segs = self.segments()
        boxes = {iid: self.ink(iid) for iid in self.placed}
        # Ambiguity only matters against the SAME KIND of component: nobody
        # reads "R_5" as naming an opamp, but "M_3" between two NMOS really is
        # ambiguous (user, 2026-08-29).
        kind = {iid: self.placed[iid][0] for iid in self.placed}
        print()
        bad = 0
        for lid, rt, x, y, align, owner in self.label_records():
            box = label_box(rt, x, y, align)
            worst = None
            for s in segs:
                g = _box_gap(box, s[1:])
                if worst is None or g < worst[1]:
                    worst = (s[0], g)
            if worst and worst[1] < 2.0:
                print("  ! LABEL OVERLAPS WIRE  %-18s on %s (gap %.1f)"
                      % (lid, worst[0], worst[1]))
                bad += 1
            elif worst and worst[1] < LABEL_INK_GAP - 2:
                print("  ~ label close to wire   %-18s on %s (gap %.1f)"
                      % (lid, worst[0], worst[1]))
            near = None
            for iid, b in boxes.items():
                if iid == owner or (owner in kind
                                    and kind.get(iid) != kind[owner]):
                    continue
                # A side label can only be confused with a device at its OWN
                # height.  Two ports stacked vertically each carry a label
                # beside them and are not competing (Fig 8.55's V_1 / V_2).
                if align in ("start", "end") and (b[1] > box[3] or b[3] < box[1]):
                    continue
                g = _box_gap_box(box, b)
                if near is None or g < near[1]:
                    near = (iid, g)
            if owner in boxes and near:
                own = _box_gap_box(box, boxes[owner])
                # Razavi's own figures: label sits ~4 units from its device and
                # ~17 from the neighbour.  Require both an absolute floor and a
                # clear ratio, so the reader cannot mis-assign the label.
                if near[1] < NEIGHBOUR_GAP or near[1] < 2.0 * own:
                    print("  ! LABEL AMBIGUOUS      %-18s own %s gap %.1f, "
                          "but %s is only %.1f away  (need >=%d and >=2x own)"
                          % (lid, owner, own, near[0], near[1],
                             NEIGHBOUR_GAP))
                    bad += 1
        return bad

    def _crowding(self):
        """Rank the tightest clearances so "crowded" names a place, not a mood.

        Compares every component ink box and every label box against each
        other, skipping a label against its own component (that gap is set by
        LABEL_INK_GAP on purpose).
        """
        items = [(iid, self.ink(iid), None) for iid in self.placed]
        for lid, rt, x, y, align, owner in self.label_records():
            items.append((lid, label_box(rt, x, y, align), owner))
        # Only components joined by ONE wire (or sitting pin-on-pin) are
        # exempt.  Sharing a net is not enough: R_E1 and C_2 hang off the same
        # emitter node yet still crowded each other to 0.6 units, and the old
        # net-wide exemption hid it (user caught it by eye, 2026-08-29).
        share = set()
        for r in self.routes:
            ends = [r["start"]]
            last = r["legs"][-1]["to"]
            if last["kind"] == "endpoint":
                ends.append(last["endpoint"])
            ids = [e["instanceId"] for e in ends if e.get("kind") == "terminal"]
            if len(ids) == 2:
                share.add((ids[0], ids[1]))
                share.add((ids[1], ids[0]))
        pinpos = {}
        for n in self.nets:
            for t in n["terminals"]:
                if t["pinName"] != "B":
                    pinpos.setdefault(self.pin(t["instanceId"], t["pinName"]),
                                      []).append(t["instanceId"])
        for ids in pinpos.values():
            for i, a in enumerate(sorted(set(ids))):
                for b2 in sorted(set(ids))[i + 1:]:
                    share.add((a, b2))
                    share.add((b2, a))
        pairs = []
        for i, (an, ab, ao) in enumerate(items):
            for bn, bb, bo in items[i + 1:]:
                if ao == bn or bo == an or (ao and ao == bo):
                    continue          # a label vs its own component, or two
                                      # labels on the same component
                if (an, bn) in share or (ao or an, bo or bn) in share:
                    continue          # electrically connected
                pairs.append((_box_gap_box(ab, bb), an, bn))
        pairs.sort()
        print()
        tight = [p for p in pairs if p[0] < CROWD_MIN]
        print("  tightest clearances: " + ", ".join(
            "%s/%s %.1f" % (a, b, g) for g, a, b in pairs[:4]))
        if tight:
            print("  ! %d pair(s) closer than %d units"
                  % (len(tight), CROWD_MIN))

    def _tee_audit(self):
        """三叉必有圓點（使用者 2026-08-30 裁示）。

        圓點是 junction 物件畫出來的。三條線在同一點相會、卻只是「一條 route
        的轉角 ＋ 另一條 route 從旁邊經過」時，編輯器看到的是兩個獨立幾何，
        不畫點——圖上就少一個節點。CDR 那張的 C_2 上緣就是這樣漏掉的。

        落在元件腳位上的三叉不算：junction 不可以壓在 terminal 上（SOP 6），
        那種點本來就由腳位自己收尾。

        **電源軌也不算**（使用者 2026-08-30 裁示）：軌上每一個分支點都是三叉，
        但課本與網站的正式渲染都不在軌上畫點（SOP 8 第 8 條）。
        """
        rail = {r["id"] for r in self.routes
                if r.get("presentation") == "power-rail"}
        net_of = {r["id"]: r["netId"] for r in self.routes}
        jpos = {(j["position"]["x"], j["position"]["y"])
                for j in self.junctions}
        pins = set()
        for n in self.nets:
            for t in n["terminals"]:
                pins.add(self.pin(t["instanceId"], t["pinName"]))
        segs, on_rail = {}, set()
        for rid, x0, y0, x1, y1 in self.segments():
            segs.setdefault(net_of.get(rid), []).append((x0, y0, x1, y1))
            if rid in rail:
                on_rail.add((x0, y0))
                on_rail.add((x1, y1))

        def unit(a, b):
            return (0 if a == b else (1 if b > a else -1))

        bad = 0
        for net in sorted(segs, key=str):
            ss = segs[net]
            pts = set()
            for x0, y0, x1, y1 in ss:
                pts.add((x0, y0))
                pts.add((x1, y1))
            for px, py in sorted(pts):
                if (px, py) in jpos or (px, py) in pins or (px, py) in on_rail:
                    continue
                dirs = set()
                for x0, y0, x1, y1 in ss:
                    if (x0, y0) == (x1, y1):
                        continue
                    d = (unit(x0, x1), unit(y0, y1))
                    if (x0, y0) == (px, py):
                        dirs.add(d)
                    elif (x1, y1) == (px, py):
                        dirs.add((-d[0], -d[1]))
                    elif (min(x0, x1) <= px <= max(x0, x1)
                          and min(y0, y1) <= py <= max(y0, y1)
                          and (x0 == x1 == px or y0 == y1 == py)):
                        dirs.add(d)
                        dirs.add((-d[0], -d[1]))
                if len(dirs) >= 3:
                    print("  ! three-way node at (%g,%g) on %s has no junction"
                          " -- the editor draws no dot there" % (px, py, net))
                    bad += 1
        return bad

    def _verify(self, expect_differ):
        """Steps 4 and 5 of the SOP, run from inside step 3.

        Every tool call re-sends the whole conversation, so four round trips
        per figure (generate / validate / check_labels / render) cost far more
        than the bytes they print.  This collapses them into one.
        `AC_FAST=1` skips it -- regress.py sets that, since it runs 23 figures.
        """
        if os.environ.get("AC_FAST"):
            return
        import subprocess
        here, proj = HERE_TOOLKIT, self.out_proj

        def node(script, *args):
            try:
                r = subprocess.run(["node", os.path.join(here, script), proj]
                                   + list(args), capture_output=True,
                                   text=True, encoding="utf-8",
                                   errors="replace", timeout=120)
                return r.stdout + r.stderr
            except Exception as e:                       # noqa: BLE001
                return "COULD NOT RUN %s: %s" % (script, e)

        out = node("validate.mjs")
        line = [l for l in out.splitlines() if "PROJECT" in l]
        if line and "VALID" in line[0]:
            print("  schema: VALID (v%d)" % SCHEMA_VERSION)
        else:
            print("  schema: FAILED")
            print(out.strip()[-1200:])

        out = node("check_labels.mjs")
        differ = [l.split()[2] for l in out.splitlines()
                  if l.startswith("DIFFER ") and len(l.split()) > 2]
        expect = set(expect_differ)
        unexpected = [d for d in differ if d not in expect]
        missing = [d for d in expect if d not in differ]
        if not unexpected and not missing:
            print("  labels: OK (%d declared plain)" % len(expect))
        else:
            for d in unexpected:
                print("  ! label %s differs from the editor's generator and is"
                      " not declared in expect_differ" % d)
            for d in missing:
                print("  ! %s is declared in expect_differ but now MATCHES --"
                      " drop it from the list" % d)

        chrome = (r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        png = os.path.splitext(self.out_svg)[0] + ".png"
        if os.path.isfile(chrome):
            w, h = self.preview_px[0] + 20, self.preview_px[1] + 20
            try:
                subprocess.run([chrome, "--headless=new",
                                "--screenshot=" + png,
                                "--window-size=%d,%d" % (w, h),
                                "--default-background-color=FFFFFFFF",
                                "file:///" + self.out_svg.replace("\\", "/")],
                               capture_output=True, timeout=120)
                print("  png: %s (%dx%d)" % (os.path.basename(png), w, h))
            except Exception as e:                       # noqa: BLE001
                print("  png: FAILED %s" % e)

    def _wire_clearance(self):
        """A component must not sit on a wire belonging to a DIFFERENT net.

        The other three checks compare component-to-component and label-to-wire,
        which left the worst kind of collision unwatched: 2026-08-29 a port's
        pin landed exactly on another net's gate wire, so the drawing showed a
        connection that does not exist.  The user found it by eye.  Nothing
        automatic would have.
        """
        bad = 0
        net_of = {r["id"]: r["netId"] for r in self.routes}
        for iid in sorted(self.placed):
            box = self.ink(iid)
            on = {n["id"] for n in self.nets
                  for t in n["terminals"] if t["instanceId"] == iid}
            for rid, x0, y0, x1, y1 in self.segments():
                if _crosses(box, (x0, y0, x1, y1)):
                    # A wire that goes IN one side and OUT the other is drawn
                    # straight through the component body.  The same-net
                    # exemption below must not cover this: 2026-08-30 the
                    # cascode gate wire ran through a CDM diode and all four
                    # audits let it pass because both were on net-vdd.
                    print("  ! wire %s (%s) runs THROUGH %s -- reroute it"
                          % (rid, net_of.get(rid), iid))
                    bad += 1
                    continue
                if net_of.get(rid) in on:
                    continue          # its own wiring: touching is the point
                g = _box_gap(box, (x0, y0, x1, y1))
                if g < CROWD_MIN:
                    print("  ! %s sits %.1f from wire %s of another net "
                          "(%s) -- reads as a connection that is not there"
                          % (iid, g, rid, net_of.get(rid)))
                    bad += 1
        return bad

    def _pitch(self):
        """Column and row pitch -- the number that actually decides "too wide".

        The old density metric (component height / figure height) is useless on
        a figure with no MOS, and "too loose" was still the standing complaint.
        Measured against the user's own correction of the hand-drawn figure
        (2026-08-30): he pulled every column gap down to 60-80.  Mine had been
        80-120.  So print the gaps and let the number do the arguing.
        """
        def gaps(vals):
            v = sorted(set(vals))
            return [b - a for a, b in zip(v, v[1:])] or [0]

        cx = gaps(self.placed[i][1] for i in self.placed)
        cy = gaps(self.placed[i][2] for i in self.placed)
        big = [g for g in cx if g > 80]
        print("  pitch: columns %s | rows %s%s"
              % ("/".join(str(g) for g in cx), "/".join(str(g) for g in cy),
                 "   <-- %d column gap(s) over 80" % len(big) if big else ""))

    def _density(self, ref=None):
        """ref = (instance_id, original_percent).  The density rule is a
        COMPARISON with the textbook page (user, 2026-08-29): measure the
        original's <component height / figure height> and match it."""
        xs, ys = [], []
        for iid in self.placed:
            b = self.ink(iid)
            xs += [b[0], b[2]]
            ys += [b[1], b[3]]
        for _rid, x0, y0, x1, y1 in self.segments():
            xs += [x0, x1]
            ys += [y0, y1]
        for lid, rt, x, y, align, _o in self.label_records():
            b = label_box(rt, x, y, align)
            xs += [b[0], b[2]]
            ys += [b[1], b[3]]
        h, w = max(ys) - min(ys), max(xs) - min(xs)
        line = "extent %.0f x %.0f  aspect %.2f" % (w, h, w / h)
        if ref:
            iid, target = ref
            b = self.ink(iid)
            got = 100.0 * (b[3] - b[1]) / h
            line += ("  |  %s height / figure height = %.1f%%  (original %.1f%%"
                     "%s)" % (iid, got, target,
                              "" if got >= 0.85 * target else "  <-- TOO LOOSE"))
        else:
            line += "  |  MOS bar 25 / height = %.1f%% (target >= 9)" % (
                100.0 * 25.0 / h)
        print(line)

    # ---------------------------------------------------------- preview
    def _preview(self, vb):
        S, J = 1.5, 1.3
        # Keep the rendered page under 2000 px wide: a bigger SVG than the
        # headless window just gets scrollbars and a cropped screenshot.
        z = min(5.0, 2000.0 / vb[2])
        self.preview_px = (int(vb[2] * z), int(vb[3] * z))
        P = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="%d %d %d %d" '
             'width="%d" height="%d"><rect x="%d" y="%d" width="%d" '
             'height="%d" fill="#fff"/><g stroke="#111" fill="none" '
             'stroke-width="1.6">'
             % (tuple(vb) + self.preview_px + tuple(vb))]
        variant = {i["id"]: i.get("symbolVariantId") for i in self.instances}
        fg = {i["id"]: (i.get("styleOverride") or {}).get("foreground")
              for i in self.instances}
        for iid, (sid, x, y, mirror, rot) in self.placed.items():
            # honour the instance colour, or the preview lies about what the
            # site will draw (SOP 8 rule 3)
            P.append('<g transform="translate(%g,%g) rotate(%g) scale(%g,1)"%s>'
                     % (x, y, rot, -1 if mirror == "x" else 1,
                        ' stroke="%s"' % fg[iid] if fg.get(iid) else ""))
            for pr in prims(sid, variant.get(iid)):
                w = (2.4 if pr.get("style", {}).get("strokeRole") == "emphasis"
                     else 1.6) * S
                k = pr["kind"]
                if k == "line":
                    P.append('<line x1="%g" y1="%g" x2="%g" y2="%g" '
                             'stroke-width="%g"/>'
                             % (pr["from"]["x"], pr["from"]["y"],
                                pr["to"]["x"], pr["to"]["y"], w))
                elif k == "path":
                    P.append('<path d="%s" stroke-width="%g"/>'
                             % (pr["data"], w))
                elif k in ("polygon", "polyline"):
                    pts = " ".join("%g,%g" % (p["x"], p["y"])
                                   for p in pr["points"])
                    P.append('<polygon points="%s" fill="#111" stroke="none"/>'
                             % pts if k == "polygon" else
                             '<polyline points="%s" stroke-width="%g"/>'
                             % (pts, w))
                elif k == "circle":
                    P.append('<circle cx="%g" cy="%g" r="%g" stroke-width="%g"'
                             ' fill="%s"/>'
                             % (pr["center"]["x"], pr["center"]["y"],
                                pr["radius"], w,
                                "#111" if pr.get("fill") == "foreground"
                                else "none"))
            P.append('</g>')
        pres = {r["id"]: r.get("presentation") for r in self.routes}
        for rid, x0, y0, x1, y1 in self.segments():
            lw = 3.24 * S if pres.get(rid) == "power-rail" else 1.6 * S
            P.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke-width="%g"/>'
                     % (x0, y0, x1, y1, lw))
        for o in self.drafting:
            if o["kind"] == "rectangle":
                # A dashed box (the block-diagram "this part is one macro"
                # boundary) has to look dashed here too, or the eyeball check
                # is looking at a different picture than the editor will.
                dash = {"dashed": ' stroke-dasharray="%g %g"' % (6 * S, 4 * S),
                        "dotted": ' stroke-dasharray="%g %g"' % (1.6 * S,
                                                                 3 * S)
                        }.get(o.get("lineStyle", "solid"), "")
                P.append('<rect x="%g" y="%g" width="%g" height="%g" '
                         'stroke-width="%g"%s fill="none"/>'
                         % (o["center"]["x"] - o["width"] / 2.0,
                            o["center"]["y"] - o["height"] / 2.0,
                            o["width"], o["height"], 1.6 * S, dash))
                continue
            if o["kind"] == "construction-line":
                # Draw these at wire weight: they stand in for wire the router
                # cannot make (a diagonal), so the preview has to show them or
                # the eyeball check is looking at a different picture than the
                # editor will (SOP section 8, rule 5).
                p = o["points"]
                P.append('<polyline points="%s" stroke-width="%g" '
                         'fill="none"/>'
                         % (" ".join("%g,%g" % (q["x"], q["y"]) for q in p),
                            1.6 * S))
                continue
            if o["kind"] != "arrow":
                continue
            fx, fy = o["from"]["position"]["x"], o["from"]["position"]["y"]
            tx, ty = o["to"]["position"]["x"], o["to"]["position"]["y"]
            ac = (o.get("styleOverride") or {}).get("color")
            colour = (' stroke="%s"' % ac) if ac else ""
            ang = math.atan2(ty - fy, tx - fx)
            # the site's own numbers (bundle dist-BrjFK9L9.js:
            # arrowHeadLength 16.569767, arrowHeadWidth 7.906977).  The preview
            # used to draw 14 x 12 -- almost equilateral, so the head came out
            # blunt and the user could see it was not the real shape.
            hs = (o.get("styleOverride") or {}).get("arrowHeadScale", 1.0)
            h, hw = 16.569767 * hs, 7.906977 * hs / 2.0
            # the shaft STOPS at the head's base, exactly as the site does
            # (`b = o - l/d*g` in its renderer).  Drawing it all the way to the
            # tip put a blunt stroke end on top of the point (user, 2026-08-30).
            P.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke-width="%g"%s/>'
                     % (fx, fy, tx - h * math.cos(ang), ty - h * math.sin(ang),
                        1.6 * S, colour))
            tri = [(tx, ty),
                   (tx - h * math.cos(ang) + hw * math.sin(ang),
                    ty - h * math.sin(ang) - hw * math.cos(ang)),
                   (tx - h * math.cos(ang) - hw * math.sin(ang),
                    ty - h * math.sin(ang) + hw * math.cos(ang))]
            P.append('<polygon points="%s" fill="%s" stroke="none"/>'
                     % (" ".join("%.2f,%.2f" % q for q in tri), ac or "#111"))
        # A junction is only PAINTED when three different directions meet at
        # it -- that is the editor's rule (SOP 3A rule 0b).  The preview used
        # to dot every junction, which put a round blob on each end of the
        # power rail where the real export has a square end (user, 2026-08-30).
        rail_routes = {r["id"] for r in self.routes
                       if r.get("presentation") == "power-rail"}
        on_rail = set()
        for rid, x0, y0, x1, y1 in self.segments():
            if rid in rail_routes:
                on_rail.add((x0, y0))
                on_rail.add((x1, y1))
        dirs = {}
        for _rid, x0, y0, x1, y1 in self.segments():
            for (px, py), (qx, qy) in (((x0, y0), (x1, y1)),
                                       ((x1, y1), (x0, y0))):
                d = (0 if qx == px else (1 if qx > px else -1),
                     0 if qy == py else (1 if qy > py else -1))
                dirs.setdefault((px, py), set()).add(d)
        for j in self.junctions:
            p = (j["position"]["x"], j["position"]["y"])
            if len(dirs.get(p, ())) < 3 or p in on_rail:
                # no dot anywhere a POWER RAIL touches: the site's own filter
                # drops any contact whose incidents include a power-rail route
                # (bundle dist-CE3Pi34B.js), and the textbook draws the rail as
                # a plain thick bar with branches meeting it (user, 2026-08-30).
                continue
            P.append('<circle cx="%g" cy="%g" r="%g" fill="#111" '
                     'stroke="none"/>' % (p[0], p[1], 2.8 * J))
        P.append('</g><g font-family="' + FONT_STACK + '" fill="#111">')
        base = BASE_FONT * FONT_SCALE * LABEL_SIZE
        for _lid, rt, x, y, align, _o in self.label_records():
            parts, prev = [], False
            for t, sub, ital, bold in flat(rt):
                dy = (base * SUB_SHIFT if sub and not prev
                      else (-base * SUB_SHIFT if prev and not sub else 0))
                parts.append('<tspan font-size="%.2f" dy="%.2f" '
                             'font-style="%s" font-weight="%d">%s</tspan>'
                             % (base * (SUB_SCALE if sub else 1.0), dy,
                                "italic" if ital else "normal",
                                700 if bold else 400,
                                t.replace("&", "&amp;").replace("<", "&lt;")))
                prev = sub
            P.append('<text x="%g" y="%g" text-anchor="%s">%s</text>'
                     % (x, y, align, "".join(parts)))
        P.append('</g></svg>')
        with open(self.out_svg, "w", encoding="utf-8") as f:
            f.write("".join(P))
        import xml.etree.ElementTree as ET
        ET.parse(self.out_svg)
        if os.environ.get("AC_FAST"):        # _verify prints the render line
            print("preview -> %s   --window-size=%d,%d"
                  % (os.path.basename(self.out_svg), self.preview_px[0] + 20,
                     self.preview_px[1] + 20))
