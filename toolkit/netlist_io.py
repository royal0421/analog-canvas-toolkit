# -*- coding: utf-8 -*-
"""Lane 2 part 1: a real netlist in and out of an `.icproj.json`.

The deck is SPICE-flavoured and carries ONLY netlist information -- devices,
nodes, device types, sub-circuit ports and their direction, printed device
names.  It carries no geometry: no coordinates, no mirror, no column order,
no rail-versus-marker choice.  Everything a drawing needs beyond that is the
placer's job (`autoplace.py`), which is the whole point of lane 2.

    python netlist_io.py                 # export every project, report health
    python netlist_io.py <file.icproj.json>

Directives beyond plain SPICE (all of them still netlist-domain facts):

    .iodir  <node>=input|output          port direction, as `.subckt` cannot
    .name   <ref> <printed name>         reference designator -> printed name
    .show   <node> ...                   nodes whose name the figure prints
    .alias  <spicename> <ref>            when the ref lacks its type letter
"""
import json
import os
import re
import sys
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir, "out")          # analog-canvas/
DECKS = os.path.join(HERE, "decks")

# symbolId -> (SPICE letter, ordered pin names, model token)
DEVICES = {
    "nmos":               ("M", ["D", "G", "S", "B"], "nmos"),
    "pmos":               ("M", ["D", "G", "S", "B"], "pmos"),
    "npn":                ("Q", ["C", "B", "E"], "npn"),
    "pnp":                ("Q", ["C", "B", "E"], "pnp"),
    "resistor":           ("R", ["1", "2"], None),
    "capacitor":          ("C", ["1", "2"], None),
    "inductor":           ("L", ["1", "2"], None),
    "inductor-compact":   ("L", ["1", "2"], "compact"),
    "variable-resistor":  ("R", ["P1", "P2"], "variable"),
    "variable-capacitor": ("C", ["P1", "P2"], "variable"),
    "variable-inductor":  ("L", ["P1", "P2"], "variable"),
    "diode":              ("D", ["A", "K"], "diode"),
    "zener-diode":        ("D", ["A", "K"], "zener"),
    "current-source":     ("I", ["+", "-"], None),
    "voltage-source":     ("V", ["+", "-"], None),
    "pulse-voltage-source": ("V", ["+", "-"], "pulse"),
}
# everything else placeable is a sub-circuit call: X<ref> <pins...> <model>
BLOCKS = {s: pins for s, pins in (
    ("opamp", ["IN+", "IN-", "OUT"]),
    ("opamp-inputs-swapped", ["IN+", "IN-", "OUT"]),
    ("comparator", ["IN+", "IN-", "OUT"]),
    ("comparator-unmarked", ["IN+", "IN-", "OUT"]),
    ("comparator-inputs-swapped", ["IN+", "IN-", "OUT"]),
    ("voltage-amplifier", ["IN", "OUT"]),
    ("nor-gate", ["A", "B", "Y"]), ("nand-gate", ["A", "B", "Y"]),
    ("and-gate", ["A", "B", "Y"]), ("or-gate", ["A", "B", "Y"]),
    ("xor-gate", ["A", "B", "Y"]), ("xnor-gate", ["A", "B", "Y"]),
    ("inverter", ["A", "Y"]), ("buffer", ["A", "Y"]),
    ("d-flip-flop", ["D", "CK", "Q", "QBAR"]),
    ("adder", ["A", "B", "Y"]), ("multiplier", ["A", "B", "Y"]),
    ("integrator", ["A", "Y"]), ("unit-delay", ["A", "Y"]),
    ("quantizer", ["A", "Y"]), ("delay-cell", ["A", "Y"]),
    ("ideal-switch", ["1", "2"]), ("closed-switch", ["1", "2"]),
    ("voltage-controlled-switch", ["P", "N", "CP", "CN"]),
)}
# schematic-only: they declare a node, they are not devices
MARKERS = {"ground", "port", "port-filled", "vdd-port"}

SUPPLY_NODE = "VDD"
GROUND_NODE = "0"


class Device(object):
    __slots__ = ("ref", "sym", "model", "pins", "label", "top", "bot")

    def __init__(self, ref, sym, model, pins, label=None):
        self.ref, self.sym, self.model = ref, sym, model
        self.pins = pins                 # {pinName: node}
        self.label = label or ref

    def node(self, pin):
        return self.pins[pin]

    def __repr__(self):
        return "<%s %s %s>" % (self.sym, self.ref, self.pins)


class Circuit(object):
    def __init__(self, name):
        self.name = name
        self.title = name
        self.devices = []                # [Device]
        self.ports = []                  # [(node, printed name, direction)]
        self.globals = []                # ["VDD"]
        self.show = []                   # nodes whose name the figure prints

    # ---------------------------------------------------------- queries
    @property
    def by_ref(self):
        return {d.ref: d for d in self.devices}

    def nodes(self):
        out = []
        for d in self.devices:
            for n in d.pins.values():
                if n not in out:
                    out.append(n)
        return out

    def pins_on(self, node):
        return [(d, p) for d in self.devices
                for p, n in d.pins.items() if n == node]

    def port_of(self, node):
        for nd, nm, di in self.ports:
            if nd == node:
                return (nm, di)
        return None

    def is_supply(self, node):
        return node in self.globals and node != GROUND_NODE

    def is_ground(self, node):
        return node == GROUND_NODE


# ------------------------------------------------------------------ export
def _flat_name(rt):
    """RichText -> 'R_G' (base plus one subscript run)."""
    if not isinstance(rt, dict):
        return None
    base, sub = [], []
    def walk(n, in_sub):
        if n.get("kind") == "text":
            (sub if in_sub else base).append(n.get("value", ""))
            return
        s = n.get("style")
        for c in n.get("children", []):
            walk(c, in_sub or s == "subscript")
    for r in rt.get("runs", []):
        walk(r, False)
    b, s = "".join(base), "".join(sub)
    return b + ("_" + s if s else "")


def export_project(path):
    proj = json.load(open(path, encoding="utf-8"))
    doc = proj["documents"][0]
    inst = {i["id"]: i for i in doc["instances"]}
    nets = {n["id"]: n for n in doc["nets"]}

    # --- node names ---------------------------------------------------
    supply_net = None
    for r in doc["routes"]:
        if r.get("presentation") == "power-rail":
            supply_net = r["netId"]
    node_of = {}
    for nid, net in nets.items():
        syms = [inst[t["instanceId"]]["symbolId"] for t in net["terminals"]
                if t["instanceId"] in inst]
        if "ground" in syms:
            node_of[nid] = GROUND_NODE
        elif nid == supply_net or "vdd-port" in syms or nid.endswith("power-vdd"):
            node_of[nid] = SUPPLY_NODE
        else:
            node_of[nid] = re.sub(r"^net-", "", nid)
    # mos bulk nets are implicit in SPICE (B pin), keep the mapping usable
    for nid in nets:
        node_of.setdefault(nid, re.sub(r"^net-", "", nid))

    pin_node = {}                       # (instanceId, pinName) -> node
    for nid, net in nets.items():
        for t in net["terminals"]:
            pin_node[(t["instanceId"], t["pinName"])] = node_of[nid]

    # v36 dropped instance.schematicName: the printed form now lives on the
    # label annotation's formatOverride, and the instance carries only the
    # flattened `reference`.
    printed = {}
    for a in doc.get("annotations", []):
        b = a.get("binding", {})
        if b.get("kind") == "instance-reference" and "formatOverride" in a:
            printed[b["instanceId"]] = _flat_name(a["formatOverride"])

    c = Circuit(doc["netlist"]["name"])
    c.title = proj.get("name", c.name)
    if SUPPLY_NODE in node_of.values():
        c.globals.append(SUPPLY_NODE)

    problems = []
    for i in doc["instances"]:
        sid, iid = i["symbolId"], i["id"]
        if sid in MARKERS:
            continue
        if sid in DEVICES:
            letter, pins, model = DEVICES[sid]
        elif sid in BLOCKS:
            letter, pins, model = "X", BLOCKS[sid], sid
        else:
            problems.append("unknown symbol %s (%s)" % (sid, iid))
            continue
        m = {}
        for p in pins:
            if p == "B" and (iid, "B") not in pin_node:
                bb = i.get("mosBulkBinding", {}).get("netId")
                m[p] = node_of.get(bb, GROUND_NODE)
                continue
            if (iid, p) not in pin_node:
                problems.append("%s.%s is not on any net" % (iid, p))
                m[p] = "?"
            else:
                m[p] = pin_node[(iid, p)]
        c.devices.append(Device(iid, sid, model, m,
                                printed.get(iid)
                                or _flat_name(i.get("schematicName"))
                                or i.get("reference") or iid))

    seen = set()
    for t in doc["netlist"].get("terminals", []):
        nd = node_of.get(t["netId"], t["netId"])
        if nd in seen:
            continue
        seen.add(nd)
        c.ports.append((nd, t["name"], t.get("direction", "input")))

    # drafting text that is exactly a node name -> that node is printed
    for o in doc.get("drafting", {}).get("objects", []):
        if o.get("kind") != "text":
            continue
        s = _flat_name(o.get("content"))
        for nd in node_of.values():
            if s and s.lower() == nd.lower() and nd not in c.show:
                c.show.append(nd)

    # a construction line is a connection the netlist cannot see
    if any(o.get("kind") == "construction-line"
           for o in doc.get("drafting", {}).get("objects", [])):
        problems.append("construction-line: a connection the netlist loses")
    boxes = [o for o in doc.get("drafting", {}).get("objects", [])
             if o.get("kind") == "rectangle"]
    if boxes:
        problems.append("%d drafting rectangle(s): block/cross-section art "
                        "the netlist has no room for" % len(boxes))
    problems += topology_defects(c)
    return c, problems


# a bulk pin is bound, not wired, so it does not count as a terminal
_TWO_TERMINAL = {"resistor", "capacitor", "inductor", "inductor-compact",
                 "variable-resistor", "variable-capacitor",
                 "variable-inductor", "current-source", "voltage-source",
                 "pulse-voltage-source", "diode", "zener-diode"}


def topology_defects(c):
    """Faults in the NETLIST itself, whatever the drawing looks like.

    A two-terminal part with both ends on one node is a short: it cannot be
    placed or routed, and every wire that reaches either of its pins runs
    through its body.  Found in two already-delivered figures on 2026-09-02
    -- Diff-amp_LC-load's L_2 (both ends on dl / dr) and the two-stage
    small-signal model's I_2 (both ends on ground) -- so it is checked here
    rather than left for the placer to trip over.
    """
    out = []
    for d in c.devices:
        pins = [n for pn, n in d.pins.items()
                if not (pn == "B" and d.sym in ("nmos", "pmos"))]
        if d.sym in _TWO_TERMINAL and len(set(pins)) == 1:
            out.append("%s (%s) is shorted: both terminals on node %s"
                       % (d.ref, d.sym, pins[0]))
    return out


def deck_text(c):
    L = ["* generated by netlist_io.py -- topology only, no geometry",
         ".title " + c.title]
    if c.globals:
        L.append(".global " + " ".join(c.globals))
    names = [c.port_of(nd)[0] if c.port_of(nd) else nd for nd, _, _ in c.ports]
    L.append(".subckt %s %s" % (c.name, " ".join(nd for nd, _, _ in c.ports)))
    if c.ports:
        L.append(".iodir " + " ".join("%s=%s" % (nd, di)
                                      for nd, _, di in c.ports))
        for nd, nm, _ in c.ports:
            if nm != nd:
                L.append(".name %s %s" % (nd, nm))
    for d in c.devices:
        letter, pins, _model = (DEVICES[d.sym] if d.sym in DEVICES
                                else ("X", BLOCKS[d.sym], d.sym))
        spice = d.ref if d.ref[:1].upper() == letter else letter + d.ref
        row = [spice] + [d.pins[p] for p in pins]
        if d.model:
            row.append(d.model)
        elif d.sym in BLOCKS:
            row.append(d.sym)
        L.append(" ".join(row))
        if spice != d.ref:
            L.append(".alias %s %s" % (spice, d.ref))
        if d.label != d.ref:
            L.append(".name %s %s" % (d.ref, d.label))
    if c.show:
        L.append(".show " + " ".join(c.show))
    L.append(".ends")
    del names
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ parse
_LETTER_SYM = {}
for _s, (_l, _p, _m) in DEVICES.items():
    _LETTER_SYM.setdefault(_l, []).append((_m, _s))


def parse(text):
    c, g, title = None, [], None
    alias, names, pending = {}, {}, []
    for raw in text.splitlines():
        line = raw.split(";")[0].strip()
        if not line or line.startswith("*"):
            continue
        tok = line.split()
        low = tok[0].lower()
        if low == ".title":
            title = " ".join(tok[1:])
        elif low == ".global":
            g = tok[1:]
        elif low == ".subckt":
            c = Circuit(tok[1])
            c.subckt_nodes = tok[2:]
            c.globals = list(g)
            c.title = title or c.name
        elif low == ".iodir":
            for kv in tok[1:]:
                k, v = kv.split("=")
                c.ports.append([k, k, v])
        elif low == ".name":
            names[tok[1]] = " ".join(tok[2:])
        elif low == ".alias":
            alias[tok[1]] = tok[2]
        elif low == ".show":
            c.show = tok[1:]
        elif low == ".ends":
            break
        else:
            pending.append(tok)
    for tok in pending:
        spice, letter = tok[0], tok[0][0].upper()
        ref = alias.get(spice, spice)
        if letter == "X":
            sym = tok[-1]
            pins = BLOCKS[sym]
            model = None
        else:
            cands = _LETTER_SYM[letter]
            tail = tok[-1]
            sym = None
            for m, s in cands:
                if m and m == tail:
                    sym, model = s, m
                    break
            if sym is None:
                sym, model = next((s, m) for m, s in cands if not m)
            pins = (DEVICES[sym][1])
        nodes = tok[1:1 + len(pins)]
        c.devices.append(Device(ref, sym, model, dict(zip(pins, nodes)),
                                names.get(ref)))
    for p in c.ports:
        p[1] = names.get(p[0], p[0])
    c.ports = [tuple(p) for p in c.ports]
    return c


# ------------------------------------------------------------------- main
def roundtrip(path):
    c, problems = export_project(path)
    txt = deck_text(c)
    c2 = parse(txt)
    same = deck_text(c2) == txt
    return c, txt, problems, same


def main(argv):
    files = argv[1:] or sorted(glob.glob(os.path.join(ROOT, "*.icproj.json")))
    if not os.path.isdir(DECKS):
        os.makedirs(DECKS)
    clean, dirty = [], []
    for p in files:
        c, txt, problems, same = roundtrip(p)
        stem = os.path.basename(p)[:-len(".icproj.json")]
        with open(os.path.join(DECKS, stem + ".cir"), "w",
                  encoding="utf-8") as fh:
            fh.write(txt)
        tag = "OK " if (not problems and same) else "-- "
        if not same:
            problems = problems + ["deck does not round-trip"]
        (clean if not problems else dirty).append(stem)
        print("%s%-52s %2d dev %2d node %d port  %s"
              % (tag, stem[:52], len(c.devices), len(c.nodes()), len(c.ports),
                 "; ".join(problems)))
    print("\nnetlist-clean: %d / %d" % (len(clean), len(files)))
    return clean, dirty


if __name__ == "__main__":
    main(sys.argv)
