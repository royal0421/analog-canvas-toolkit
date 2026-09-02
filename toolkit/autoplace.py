# -*- coding: utf-8 -*-
"""Lane 2 part 2: netlist -> schematic, with no original figure to copy.

The rules it applies are SOP 3A turned into code.  Nothing here reads the
reference drawing; the only input is the deck from `netlist_io.py`.

    python autoplace.py decks/Razavi_Fig_7_94_source-follower.cir [-o out.json]

Layout model
------------
* ROWS come from electrical depth.  Supply is the top row, ground the bottom
  row, everything else is layered by rank = d_vdd / (d_vdd + d_gnd) over the
  device graph.  A device body sits between its two node rows with a stub at
  each end (SOP 3A: 10-20).
* COLUMNS come from branches.  A branch is a chain of vertically stacked
  devices; each branch owns one column, columns are 60 apart (SOP 3A says
  50-70), and a column's "conduction x" is where D/S, C/E and passive pins
  line up -- a MOS centre is therefore 10 to the side of it.
* MIRROR follows the gate: the gate faces the column that drives it.
* A node with three or more pins gets a BUS ROW 10 outside the pin row and a
  riser per pin, because a junction may not sit on a terminal (SOP 6).
"""
import os
import sys
import io
import json
import contextlib

import netlist_io as N
from icproj import ink_box
from icproj import (Schematic, name, plain, LABEL_PORT, dy_above,
                    dy_below, label_box, _box_gap, _box_gap_box,
                    NEIGHBOUR_GAP, LABEL_INK_GAP)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir, "out")

# ------------------------------------------------------------------ constants
COL_PITCH = int(os.environ.get("AC_PITCH", 80))          # SOP 3A: 50-70, and 80 is the hard ceiling
STUB = 20               # node row -> device pin
STUB_GND = 10           # last pin -> ground symbol pin
STUB_PORT = 20          # bus end -> port pin
BUS_OFFSET = 10         # bus row sits this far outside the pin row
RAIL_Y = 100
RAIL_OVERHANG = 20
X0 = 120                # left-most conduction column

# symbol -> (top pin, bottom pin) when drawn vertically.  For a transistor the
# convention is fixed by the device, not by the netlist: nmos drain up, pmos
# source up, npn collector up, pnp emitter up.
FIXED_VERT = {"nmos": ("D", "S"), "pmos": ("S", "D"),
              "npn": ("C", "E"), "pnp": ("E", "C")}
# symmetric two-terminal parts: the netlist decides which end is up
SYMM_VERT = {"resistor": ("1", "2"), "capacitor": ("1", "2"),
             "inductor": ("1", "2"), "inductor-compact": ("1", "2"),
             "variable-resistor": ("P1", "P2"), "variable-capacitor": ("P1", "P2"),
             "variable-inductor": ("P1", "P2"),
             "current-source": ("+", "-"), "voltage-source": ("+", "-"),
             "pulse-voltage-source": ("+", "-"), "diode": ("A", "K")}
SPAN = {"nmos": 40, "pmos": 40, "npn": 60, "pnp": 60, "diode": 40}
CTRL = {"nmos": "G", "pmos": "G", "npn": "B", "pnp": "B"}
# label offset from the instance centre, per SOP 3A (ink edge + 8)
LBL_DX = {"nmos": 18, "pmos": 18, "npn": 8, "pnp": 8,
          "current-source": 18, "voltage-source": 18,
          "resistor": 13, "variable-resistor": 13,
          "capacitor": 16, "variable-capacitor": 16,
          "inductor": 15, "inductor-compact": 15, "variable-inductor": 15,
          "diode": 16}


def span_of(sym):
    return SPAN.get(sym, 40)


class Placer(object):
    def __init__(self, circuit, out_proj, out_svg, project_id=None,
                 pitch=None, rowgap=60, portstub=STUB_PORT, style=None):
        self.style = dict(style or {})
        self.pitch = pitch or COL_PITCH
        self.rowgap = rowgap
        self.portstub = portstub
        self.c = circuit
        self.out_proj, self.out_svg = out_proj, out_svg
        self.pid = project_id or ("project-" + circuit.name.lower())
        self.log = []

    def opt(self, name, default):
        """One discrete layout choice.

        These used to be environment variables I flipped by hand to A/B a
        rule.  They are now per-drawing options so `place_deck` can SEARCH
        them: the same figure is drawn several ways and the best-scoring one
        is kept, instead of me guessing one rule per rejection.
        """
        if name in self.style:
            return self.style[name]
        return os.environ.get("AC_" + name.upper(), default)

    # ------------------------------------------------------------ topology
    def _graph(self):
        """undirected node graph over two-terminal conduction paths"""
        g = {}
        for d in self.c.devices:
            pair = self.vpins(d)
            if not pair:
                continue
            a, b = d.pins[pair[0]], d.pins[pair[1]]
            g.setdefault(a, set()).add(b)
            g.setdefault(b, set()).add(a)
        for n in self.c.nodes():
            g.setdefault(n, set())
        return g

    def vpins(self, d):
        if d.sym in FIXED_VERT:
            return FIXED_VERT[d.sym]
        if d.sym in SYMM_VERT:
            return SYMM_VERT[d.sym]
        return None                      # a block: horizontal, IN -> OUT

    @staticmethod
    def _bfs(g, roots):
        dist = {r: 0 for r in roots if r in g}
        q = list(dist)
        while q:
            n = q.pop(0)
            for m in g[n]:
                if m not in dist:
                    dist[m] = dist[n] + 1
                    q.append(m)
        return dist

    def rank(self):
        """Vertical order of the nodes, 0 at the top.

        With a supply present the textbook order is "how far down from the
        rail", which is d_vdd / (d_vdd + d_gnd).  With no rail -- an op-amp
        network, a small-signal model -- the only anchor is ground, so the
        order is simply distance from it, counted upwards.
        """
        g = self._graph()
        sup = [n for n in g if self.c.is_supply(n)]
        gnd = [n for n in g if self.c.is_ground(n)]
        dg = self._bfs(g, gnd)
        BIG = len(g) + 5
        self.dgnd = {n: dg.get(n, BIG) for n in g}
        if sup:
            dv = self._bfs(g, sup)
            r = {}
            for n in g:
                a, b = dv.get(n, BIG), dg.get(n, BIG)
                r[n] = 0.0 if self.c.is_supply(n) else (
                    1.0 if self.c.is_ground(n) else float(a) / max(1, a + b))
            return r
        top = max([1] + [v for v in self.dgnd.values() if v < BIG])
        return {n: (top - min(self.dgnd[n], top)) / float(top) for n in g}

    def _signal_chain(self):
        """Which two-terminal parts carry the signal from left to right.

        With no rail the only thing that orders the drawing horizontally is
        the signal: it enters at an input port and walks through a string of
        series parts until it reaches an amplifier input.  The textbook lays
        THAT string down (Sallen-Key's R1/R2, a summing network's resistors);
        everything hanging off it to ground is a shunt and stands up.
        `dgnd`-equality alone cannot see this -- R1 and R2 sit at different
        distances from ground and were being stacked into a column
        (user 2026-09-02: "慢到極致").
        """
        mode = str(self.opt("sigpath", "1"))
        if mode == "0":
            return {}
        if (mode != "rail"
                and any(self.c.is_supply(n) for n in self.c.nodes())):
            return {}
        adj = {}
        for d in self.c.devices:
            pr = self.vpins(d)
            if not pr:
                continue
            a, b = d.pins[pr[0]], d.pins[pr[1]]
            if a == b or self.c.is_ground(a) or self.c.is_ground(b):
                continue
            adj.setdefault(a, []).append((b, d))
            adj.setdefault(b, []).append((a, d))
        tgt = set()
        for d in self.c.devices:
            if self.vpins(d) is None and d.sym in N.BLOCKS:
                tgt.update(d.pins[p] for p in N.BLOCKS[d.sym][:-1])
            elif d.sym in CTRL:
                # with a rail the amplifier is a transistor, and the thing
                # the signal is walking towards is its gate or base: Fig
                # 5.170's C_1 and R_in are a horizontal run from V_in to
                # Q1's base in the book, and a vertical stack without this
                tgt.add(d.pins[CTRL[d.sym]])
        if not tgt:
            tgt = set(nd for nd, _nm, di in self.c.ports if di == "output")
        out = {}
        roots = [(nd, 1) for nd, _nm, di in self.c.ports if di == "input"]
        roots += [(nd, 0) for nd, _nm, di in self.c.ports if di == "output"]
        for root, fwd in roots:
            prev, q, hit = {root: None}, [root], None
            while q:
                n = q.pop(0)
                if n in tgt and n != root:
                    hit = n
                    break
                for m, d in adj.get(n, ()):
                    if m not in prev:
                        prev[m] = (n, d)
                        q.append(m)
            while hit is not None and prev.get(hit):
                n, d = prev[hit]
                # walking out from an output port, the flow is the other way
                out.setdefault(d.ref, (n, hit) if fwd else (hit, n))
                hit = n
        return out

    def orient(self):
        """Vertical or horizontal, and which end is up.

        A two-terminal part whose two nodes are the SAME distance from ground
        is a lateral element -- a coupling capacitor, a feedback resistor, a
        series element in the signal path -- and the textbook draws it lying
        down.  Everything else stacks.
        """
        r = self.rank()
        self.rank_of = r
        vert, horiz, blocks = [], [], []
        # a node an amplifier or a port owns is a SIGNAL node; a part strung
        # between two of them is a series element in the signal path and the
        # textbook lays it down (Fig 8.55's summing resistors)
        chain = self._signal_chain()
        # a node a port or an amplifier owns is a SIGNAL node, and so is
        # every node the input walks through on its way in.  A part strung
        # between two of them is in the signal path -- series (R1, R2) or
        # feedback over the top (C1) -- and the textbook lays it down.
        signal = set(nd for nd, _nm, _di in self.c.ports)
        for d in self.c.devices:
            if self.vpins(d) is None:
                signal.update(d.pins.values())
            elif d.sym in CTRL:
                # a gate or a base is a signal node too: Razavi draws R_fb
                # LYING DOWN between Q1's base and Q2's base (Fig 5.170),
                # and the same for any part strung between two control nodes
                signal.add(d.pins[CTRL[d.sym]])
        for up, dn in chain.values():
            signal.update((up, dn))
        for d in self.c.devices:
            p = self.vpins(d)
            if p is None:
                blocks.append(d)
                continue
            a, b = p
            na, nb = d.pins[a], d.pins[b]
            if d.sym in FIXED_VERT:
                d.top, d.bot = p
                vert.append(d)
                continue
            lateral = (self.dgnd.get(na) == self.dgnd.get(nb)
                       or (na in signal and nb in signal))
            if (na != nb and lateral
                    and not self.c.is_ground(na)
                    and not self.c.is_ground(nb)
                    and not self.c.is_supply(na)
                    and not self.c.is_supply(nb)):
                # lying down: pin 1 ends up on the RIGHT after rotation 90,
                # so the signal has to leave by pin 1 or the drawing reads
                # right-to-left (V_in landed on R1's right, 2026-09-02)
                dn = chain.get(d.ref, (None, None))[1]
                d.top, d.bot = (b, a) if nb == dn else (a, b)
                horiz.append(d)
                continue
            d.top, d.bot = (a, b) if r[na] <= r[nb] else (b, a)
            vert.append(d)
        self.vert, self.horiz, self.blocks = vert, horiz, blocks

    # -------------------------------------------------------------- levels
    def levels(self):
        """longest-path layering over the oriented vertical devices.

        Ground is NOT a layer: a branch that ends at ground ends wherever its
        own stack ends, and the ground symbols are aligned afterwards (SOP
        3E rule 4) only when that does not stretch a stub past the 40 budget.
        """
        parent = {}

        def find(n):
            parent.setdefault(n, n)
            while parent[n] != n:
                parent[n] = parent[parent[n]]
                n = parent[n]
            return n

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra
        for n in self.c.nodes():
            find(n)
        for d in self.horiz + self.blocks:
            ns = [v for v in d.pins.values() if not self.c.is_ground(v)]
            if d in self.horiz:
                for k in ns[1:]:
                    union(ns[0], k)
        self.find = find
        succ = {}
        for d in self.vert:
            a, b = find(d.pins[d.top]), find(d.pins[d.bot])
            if a == b or self.c.is_ground(d.pins[d.bot]) \
                    or self.c.is_ground(d.pins[d.top]):
                continue
            succ.setdefault(a, []).append((b, d))
        roots = {n: 0 for n in self.c.nodes() if not self.c.is_ground(n)}
        roots = {find(n): 0 for n in roots}
        for _ in range(len(roots) + 2):
            changed = False
            for a, outs in succ.items():
                if a not in roots:
                    continue
                for b, _d in outs:
                    if b in roots and roots[b] < roots[a] + 1:
                        roots[b] = roots[a] + 1
                        changed = True
            if not changed:
                break
        if str(self.opt("levels", "asap")) == "alap":
            # ASAP floats every unconstrained node to the top row, which is
            # where a bias node that only feeds a gate ends up.  ALAP hangs
            # each node from the thing below it instead -- the same layering,
            # read from the bottom.  Which one matches the textbook depends
            # on the circuit, so it is a search axis, not a rule.
            top = max(roots.values()) if roots else 0
            alap = {n: top for n in roots}
            for _ in range(len(roots) + 2):
                changed = False
                for a, outs in succ.items():
                    if a not in alap:
                        continue
                    for b, _d in outs:
                        if b in alap and alap[a] > alap[b] - 1:
                            alap[a] = alap[b] - 1
                            changed = True
                if not changed:
                    break
            lo = min(alap.values()) if alap else 0
            roots = {n: v - lo for n, v in alap.items()}
        lvl = {n: roots[find(n)] for n in self.c.nodes()
               if not self.c.is_ground(n) and find(n) in roots}
        if any(self.c.is_supply(n) for n in lvl):
            # the rail is a row of its own: nothing else may share it
            for n in lvl:
                if not self.c.is_supply(n):
                    lvl[n] = max(1, lvl[n])
                else:
                    lvl[n] = 0
        self.lvl = lvl
        need = {}
        for d in self.vert:
            if d.pins[d.top] not in lvl or d.pins[d.bot] not in lvl:
                continue
            a, b = lvl[d.pins[d.top]], lvl[d.pins[d.bot]]
            if b <= a:
                continue
            per = (span_of(d.sym) + 2 * STUB) / float(b - a)
            for k in range(a, b):
                need[k] = max(need.get(k, 0), per)
        top = max(lvl.values()) if lvl else 0
        # with no rail there is nothing above the first row, and feedback
        # parts need somewhere to run, so the first row starts lower
        y, ys = (RAIL_Y if any(self.c.is_supply(n) for n in lvl)
                 else RAIL_Y + 100), {}
        for k in range(0, top + 1):
            ys[k] = int(round(y / 10.0)) * 10
            y += max(need.get(k, self.rowgap), self.rowgap)
        self.ylevel = ys
        self.ynode = {n: ys[lvl[n]] for n in lvl}

    # ----------------------------------------------------------- columns
    def columns(self):
        """One column per series chain.

        A chain is a run of vertical parts stacked node to node.  Two parts
        across the SAME pair of nodes are parallel branches and must land in
        different columns, which is why the column key is the chain and not
        the node.  Blocks (op-amp, gate) own a column of their own.

        Left to right: a controlled device sits right of whatever drives its
        gate, a block sits between its inputs and its output, and a chain
        that hangs off another chain's node sits next to it.
        """
        # ties break on the order the netlist declares the parts: that is
        # the only ordering a deck actually carries, and a reader reads a
        # deck top down (the reference branch of a mirror is written first)
        decl = {d.ref: i for i, d in enumerate(self.c.devices)}
        self.decl = decl
        left = sorted(self.vert, key=lambda d: (self.lvl.get(d.pins[d.top], 0),
                                                decl[d.ref]))
        chains, used = [], set()
        for seed in left:
            if seed.ref in used:
                continue
            ch, node = [seed], seed.pins[seed.bot]
            used.add(seed.ref)
            while not self.c.is_ground(node) and not self.c.is_supply(node):
                cand = [d for d in left if d.ref not in used
                        and d.pins[d.top] == node]
                if not cand:
                    break
                # the leg that reaches ground keeps the column going
                cand.sort(key=lambda d: (0 if self.c.is_ground(d.pins[d.bot])
                                         else 1, decl[d.ref]))
                ch.append(cand[0])
                used.add(cand[0].ref)
                node = cand[0].pins[cand[0].bot]
            chains.append(ch)
        self.chains = chains
        self.owner = {}
        for i, ch in enumerate(chains):
            for d in ch:
                self.owner[d.ref] = i
        for d in self.blocks:
            self.owner[d.ref] = "blk:" + d.ref
        self.node_cols = {}
        # "share": a node that is only some device's GATE is not a column of
        # its own -- it is a wire between two columns.  Razavi's drawings are
        # narrow (Fig 10.34 is two branches wide); giving every gate node its
        # own slot is what spreads mine out.
        share = str(self.opt("freecol", "own")) == "share"
        for i, ch in enumerate(chains):
            for d in ch:
                pins = d.pins.keys() if share else (d.top, d.bot)
                for p in pins:
                    if p == "B" and d.sym in ("nmos", "pmos"):
                        continue
                    n = d.pins[p]
                    if not (self.c.is_ground(n) or self.c.is_supply(n)):
                        if i not in self.node_cols.setdefault(n, []):
                            self.node_cols[n].append(i)
        # ---- constraint graph -------------------------------------
        # Slots are chains, blocks and any node no chain owns.  Positions
        # count in half columns so a block can sit between two nodes.
        def nvars(n):
            if n in self.node_cols:
                return [("c", i) for i in self.node_cols[n]]
            if self.c.is_ground(n) or self.c.is_supply(n):
                return []
            return [("n", n)]

        slots = set()
        for i in range(len(chains)):
            slots.add(("c", i))
        for d in self.blocks:
            slots.add(("b", d.ref))
        for n in self.c.nodes():
            slots.update(nvars(n))
        edges = []                            # (from, to, step)
        # "forward" edges: a gate driver ahead of what it drives, a block
        # ahead of its own output.  Neither of them is ever feedback, so
        # they are the ones worth honouring INSIDE a cycle (see below).
        fwd_edges = []
        for d in self.c.devices:
            if d.sym in CTRL and d.ref in self.owner:
                me = ("c", self.owner[d.ref])
                for u in nvars(d.pins[CTRL[d.sym]]):
                    if u != me:
                        edges.append((u, me, 2))
                        fwd_edges.append((u, me))
        # lateral parts: the first direction the signal reaches is forward,
        # anything pointing back is feedback and gets no ordering constraint
        adj = {}
        for d in self.horiz:
            p1, p2 = self.vpins(d)
            n1, n2 = d.pins[p1], d.pins[p2]
            if self.c.is_ground(n1) or self.c.is_ground(n2):
                continue
            adj.setdefault(n1, []).append((n2, d))
            adj.setdefault(n2, []).append((n1, d))
        for d in self.blocks:
            pins = N.BLOCKS[d.sym]
            for p in pins[:-1]:
                adj.setdefault(d.pins[p], []).append((d.pins[pins[-1]], d))
        seeds = [nd for nd, _nm, di in self.c.ports if di == "input"]
        if not seeds and adj:
            seeds = [min(adj, key=lambda n: (len(adj[n]), n))]
        seen, q = set(seeds), list(seeds)
        ordn = {n: i for i, n in enumerate(seeds)}
        self.fwd = set()
        while q:
            n = q.pop(0)
            for m, d in adj.get(n, []):
                if m in seen:
                    continue
                seen.add(m)
                ordn[m] = len(ordn)
                q.append(m)
                if d in self.horiz:
                    self.fwd.add((d.ref, n, m))
                    for u in nvars(n):
                        for v in nvars(m):
                            if u != v:
                                edges.append((u, v, 2))
        # The output is on the RIGHT.  Razavi taps V_out at the right-hand
        # end of every stage (5.43, 7.32, 9.42), so whatever feeds the
        # output node is ordered before it; a cycle through feedback is left
        # to the SCC pass as usual.
        for ond, _onm, odi in self.c.ports:
            if odi != "output":
                continue
            for d in self.c.devices:
                if ond not in d.pins.values():
                    continue
                for n2 in set(d.pins.values()):
                    if (n2 == ond or self.c.is_ground(n2)
                            or self.c.is_supply(n2)):
                        continue
                    for u in nvars(n2):
                        for v in nvars(ond):
                            if u != v:
                                edges.append((u, v, 1))
        BIGN = len(ordn) + 99
        for d in self.blocks:
            pins, me = N.BLOCKS[d.sym], ("b", d.ref)
            for p in pins[:-1]:
                # every input is an ordering constraint; the cycle a feedback
                # input closes is handled by the SCC pass below, and that
                # pass orders the stages the way the deck declares them
                for u in nvars(d.pins[p]):
                    if u != me:
                        edges.append((u, me, 1))
            for v in nvars(d.pins[pins[-1]]):
                if v != me:
                    edges.append((me, v, 1))
                    fwd_edges.append((me, v))
        # Ordering constraints go round in circles whenever the circuit does
        # -- a self-biased mirror (each branch drives the other's gate), an
        # op-amp whose input comes back from a later stage.  Collapse every
        # cycle to a point and order inside it the way the deck declares the
        # parts: the reference branch and the first stage are written first.
        adj = {}
        for u, v, _w in edges:
            adj.setdefault(u, set()).add(v)
        slots = sorted(slots)
        comp = self._scc(slots, adj)
        cdepth = {}
        for _ in range(len(slots) + 2):
            moved = False
            for u, outs in adj.items():
                for v in outs:
                    if comp[u] == comp[v]:
                        continue
                    if cdepth.get(comp[v], 0) <= cdepth.get(comp[u], 0):
                        cdepth[comp[v]] = cdepth.get(comp[u], 0) + 1
                        moved = True
            if not moved:
                break
        decl = self.decl
        node_first = {}
        for i, d in enumerate(self.c.devices):
            for n in d.pins.values():
                node_first.setdefault(n, i)

        def key(slot):
            if slot[0] == "c":
                return min(decl[d.ref] for d in chains[slot[1]])
            if slot[0] == "b":
                return decl[slot[1]]
            return node_first.get(slot[1], 9999)

        members = {}
        for k in slots:
            members.setdefault(comp[k], []).append(k)
        # Inside a cycle the deck's declaration order is only a tiebreak,
        # and it is the wrong one whenever an amplifier drives a transistor:
        # Fig 8.69 declares Q1 before the op amp, so the op amp landed to the
        # RIGHT of the transistor it feeds and its output had to loop round
        # the whole drawing.  In "ctrl" mode the cycle is ordered by the
        # forward edges it contains (driver before driven, block before its
        # own output) and the declaration order only breaks what is left.
        local = {}
        if str(self.opt("sccorder", "decl")) == "ctrl":
            sub = {}
            for u, v in fwd_edges:
                if u in comp and v in comp and comp[u] == comp[v]:
                    sub.setdefault(u, set()).add(v)
            for _ in range(len(slots) + 2):
                moved = False
                for u, outs in sub.items():
                    for v in outs:
                        if local.get(v, 0) <= local.get(u, 0):
                            local[v] = min(local.get(u, 0) + 1, len(slots))
                            moved = True
                if not moved:
                    break
        groups = sorted(members, key=lambda c: (cdepth.get(c, 0),
                                                min(key(k)
                                                    for k in members[c])))
        order_all = []
        for cid in groups:
            order_all += sorted(members[cid],
                                key=lambda k: (local.get(k, 0), key(k)))
        if str(self.opt("colorder", "decl")) == "bary":
            # The deck's declaration order is an arbitrary tiebreak between
            # slots the constraints do not separate.  Sorting them by the
            # average position of what they CONNECT TO is the standard
            # crossing-reduction sweep, and it is the only step here that
            # looks at a whole row at once.  Whole SCC components move, and
            # only within their own constraint depth, so every hard
            # ordering still holds.
            touch = {k: set() for k in order_all}
            for nd2 in self.c.nodes():
                if self.c.is_ground(nd2) or self.c.is_supply(nd2):
                    continue
                slots = set(nvars(nd2))
                for d in self.c.devices:
                    if nd2 not in d.pins.values():
                        continue
                    o = self.owner.get(d.ref)
                    slots.add(("b", d.ref) if o is None or isinstance(o, str)
                              else ("c", o))
                slots = {u for u in slots if u in touch}
                for u in slots:
                    touch[u] |= slots - {u}
            bylvl = {}
            for cid in groups:
                bylvl.setdefault(cdepth.get(cid, 0), []).append(cid)
            for _sweep in range(6):
                pos0 = {k: i for i, k in enumerate(order_all)}

                def cbary(cid):
                    ns = [pos0[u] for k in members[cid]
                          for u in touch.get(k, ()) if u in pos0]
                    own = [pos0[k] for k in members[cid] if k in pos0]
                    return (sum(ns) / float(len(ns)) if ns
                            else (own[0] if own else 0))
                out = []
                for lvl in sorted(bylvl):
                    for cid in sorted(bylvl[lvl],
                                      key=lambda c: (cbary(c),
                                                     min(pos0[k] for k
                                                         in members[c]))):
                        out += sorted(members[cid],
                                      key=lambda k: (local.get(k, 0), key(k)))
                if out == order_all:
                    break
                order_all = out
        pos = {k: i for i, k in enumerate(order_all)}
        order = [k for k in order_all if k[0] == "c"]
        # a chain that hangs off another chain's node sits beside it
        anchor = {}
        amode = str(self.opt("anchor", "1"))
        if amode != "0":
            for i, ch in enumerate(chains):
                # A branch hanging off another chain's node belongs NEXT TO
                # that chain, whichever side it currently sits on.  The old
                # rule only fired when the anchor was already to the left, so
                # a load capacitor whose node is the right-most column got
                # stranded on the far left and its wire crossed the whole
                # figure (user, 2026-09-02: "明明右邊空曠").
                cand = list(self.node_cols.get(ch[0].pins[ch[0].top], []))
                if amode in ("lat", "tight"):
                    # A branch can also hang off another column through a
                    # LYING-DOWN part.  12.57(c)'s R_M2 is the return leg of
                    # the V_X test source: nothing orders it, so it landed
                    # five columns away from the node V_X connects it to and
                    # the source stretched across the whole drawing.
                    mine = set()
                    for d in ch:
                        mine.update(d.pins.values())
                    for d in self.horiz:
                        q1, q2 = self.vpins(d)
                        a, b = d.pins[q1], d.pins[q2]
                        for n1, n2 in ((a, b), (b, a)):
                            if n1 in mine and not self.c.is_ground(n2):
                                cand += self.node_cols.get(n2, [])
                    cand += self.node_cols.get(ch[-1].pins[ch[-1].bot], [])
                for j in cand:
                    if (j != i and len(chains[i]) <= len(chains[j])
                            and anchor.get(j) != i):
                        anchor[i] = j
                        break
        seq = [k for k in order_all
               if not (k[0] == "c" and k[1] in anchor)]
        for k in order_all:                    # then drop each hanger beside
            if k[0] != "c" or k[1] not in anchor:
                continue
            j = anchor[k[1]]
            if ("c", j) not in seq:
                seq.append(k)
                continue
            q = seq.index(("c", j)) + 1
            if amode != "tight":
                # walk past the anchor's other hangers, so several branches
                # off one node keep their declaration order
                while q < len(seq) and seq[q][0] == "c"                         and anchor.get(seq[q][1]) == j:
                    q += 1
            # "tight": each hanger goes straight after its anchor instead.
            # Fig 10.35(a) has M3 hanging off M1's drain and M2 hanging off
            # M1's source; walking past siblings pushed the diode load to
            # the far right, while the book puts it right beside M1.
            seq.insert(q, k)
        pos = {k: i for i, k in enumerate(seq)}
        order = [k for k in seq if k[0] == "c"]
        lo = min(pos.values()) if pos else 0
        self.colpos = {k: pos[k] - lo for k in pos}
        self.col_order = order
        self._spread()

    def _slot_half(self, key):
        """How much room this column needs either side of its centre."""
        if key[0] == "b":
            d = next(x for x in self.blocks if x.ref == key[1])
            from icproj import sym as _sym
            return max(abs(p["at"]["x"]) for p in _sym(d.sym)["pins"])
        if key[0] == "c":
            return 20                       # a MOS reaches 20 to its gate
        return 10

    def _spread(self):
        """Columns are not evenly spaced: a block is 100 wide and a plain
        branch is 40, so the gap is measured edge to edge (SOP 3A) rather
        than centre to centre."""
        half = {}
        for k, p in self.colpos.items():
            half[p] = max(half.get(p, 10), self._slot_half(k))
        xs, cur = {}, float(X0)
        for i, p in enumerate(sorted(half)):
            if i:
                prev = sorted(half)[i - 1]
                cur += half[prev] + self.pitch // 2 + half[p]
            xs[p] = int(round(cur / 10.0)) * 10
        self.col_x = {k: xs[self.colpos[k]] for k in self.colpos}

    @staticmethod
    def _scc(nodes, edge):
        """Kosaraju: node -> component id, components numbered any way."""
        order, seen = [], set()
        for n in nodes:
            if n in seen:
                continue
            stack = [(n, iter(edge.get(n, ())))]
            seen.add(n)
            while stack:
                v, it = stack[-1]
                for w in it:
                    if w not in seen:
                        seen.add(w)
                        stack.append((w, iter(edge.get(w, ()))))
                        break
                else:
                    order.append(v)
                    stack.pop()
        rev = {}
        for u, outs in edge.items():
            for v in outs:
                rev.setdefault(v, set()).add(u)
        comp, cid = {}, 0
        for n in reversed(order):
            if n in comp:
                continue
            stack = [n]
            comp[n] = cid
            while stack:
                v = stack.pop()
                for w in rev.get(v, ()):
                    if w not in comp:
                        comp[w] = cid
                        stack.append(w)
            cid += 1
        for n in nodes:
            comp.setdefault(n, cid)
            cid += 1
        return comp

    def _slot_x(self, key):
        return self.col_x.get(key)

    def _cond_x(self, d):
        k = self.owner[d.ref]
        return self.col_x[("b", d.ref) if isinstance(k, str) else ("c", k)]

    def _node_x(self, n, which="mid"):
        cols = [self.col_x[("c", i)] for i in self.node_cols.get(n, [])]
        if not cols and ("n", n) in self.col_x:
            cols = [self.col_x[("n", n)]]
        if not cols:
            return None
        return (min(cols) if which == "min" else
                max(cols) if which == "max" else
                sum(cols) / float(len(cols)))

    def _mirror(self, d):
        """The gate faces whatever drives it.

        "Whatever drives it" is the centre of the gate net's other pins, not
        the nearest one: a mirror pair shares one gate bus that runs between
        the two devices, and both gates have to face it.
        """
        if d.sym not in CTRL:
            return "none"
        gnode = d.pins[CTRL[d.sym]]
        me = self._cond_x(d)
        xs = [self._cond_x(e) for e in self.c.devices
              if e.ref != d.ref and e.ref in self.owner
              and gnode in e.pins.values()]
        if not xs:
            # Nothing drives this gate but a port, so the gate faces whichever
            # side has the most room -- that is where the port lands, and a
            # port squeezed against the neighbouring column is exactly the
            # case the user says to mirror the MOS for (2026-09-02).
            # only columns that actually HOLD something count as crowding:
            # the slot list also carries free nodes and ports, and a phantom
            # column on the right made the gate turn back into its neighbour
            if (str(self.opt("inleft", "1")) == "1"
                    and os.environ.get("AC_INMIR", "1") == "1"
                    and any(nd == gnode and di == "input"
                            for nd, _nm, di in self.c.ports)):
                # the input comes in from the left edge (user, 2026-09-02),
                # so the gate has to face it
                return "none"
            allx = sorted({self._cond_x(e) for e in self.vert
                           if e.ref in self.owner}
                          | {self.col_x[("b", e.ref)] for e in self.blocks})
            left = [x for x in allx if x < me]
            right = [x for x in allx if x > me]
            gl = (me - left[-1]) if left else 10 ** 6
            gr = (right[0] - me) if right else 10 ** 6
            return "x" if gr >= gl else "none"
        gx = sum(xs) / float(len(xs))
        if gx == me:
            return "none"
        return "x" if gx > me else "none"

    # -------------------------------------------------------------- geometry
    def place_all(self):
        f = self.f = Schematic(
            self.pid, self.c.title, self.c.name,
            out_proj=self.out_proj, out_svg=self.out_svg,
            nmos_bulk_net="net-0",
            supply_net="net-" + (self.c.globals[0] if self.c.globals
                                 else "VDD"))
        f.lane2_audits = True      # the netlist lane opts into its own checks
        self.pinxy = {}
        self._lat = []
        # a lateral the signal never traverses forward is feedback: it goes
        # over the top, the longest span highest, so the spans nest
        fb = ([] if any(self.c.is_supply(n) for n in self.c.nodes())
              else [d for d in self.horiz
                    if not any(f[0] == d.ref
                               for f in getattr(self, "fwd", ()))
                    or (str(self.opt("spans", "1")) == "1"
                        and self._spans_over(d))])

        def span(d):
            xs = [self._node_x(n) for n in d.pins.values()
                  if self._node_x(n) is not None]
            return (max(xs) - min(xs)) if len(xs) > 1 else 0
        fb.sort(key=span)
        self.fb_track = {d.ref: i + 1 for i, d in enumerate(fb)}
        # transistors first: a part hanging on a gate has to know where the
        # gate is before it can stop there (Razavi Fig 7.32 puts R_G's lower
        # end exactly on the gate line, not on a row of its own)
        for d in sorted(self.vert, key=lambda e: 0 if e.sym in CTRL else 1):
            self._place_vert(d)
        for d in self.blocks:
            self._place_block(d)          # blocks first: a lying-down part
        for d in self.horiz:              # has to be able to see them
            self._place_horiz(d)

    def _spans_over(self, d):
        """Does this lying-down part reach across something?

        A lateral between two ADJACENT columns is a series element and stays
        on the main row.  One that jumps a column has to clear whatever sits
        in between, so it belongs on a track above -- Sallen-Key's C1 goes
        from n1 all the way to the output, over R2 and over the op-amp, and
        parking it on the main row landed it on top of both.

        "Not traversed forward" alone does not catch it: the BFS reaches the
        output through C1 as readily as through the amplifier.
        """
        xs = [self._node_x(n) for n in d.pins.values()]
        xs = [x for x in xs if x is not None]
        if len(xs) < 2:
            return False
        lo, hi = min(xs), max(xs)
        own = set(d.pins.values())
        for n in self.c.nodes():
            if n in own or self.c.is_ground(n) or self.c.is_supply(n):
                continue
            x = self._node_x(n)
            if x is not None and lo < x < hi:
                return True
        for b in self.blocks:
            x = self._slot_x(("b", b.ref))
            if x is not None and lo < x < hi:
                return True
        return False

    def _record(self, d):
        for p in d.pins:
            if p == "B" and d.sym in ("nmos", "pmos"):
                continue          # bulk is bound, not wired (SOP 6)
            try:
                self.pinxy[(d.ref, p)] = self.f.pin(d.ref, p)
            except KeyError:
                pass

    def _place_vert(self, d):
        cx = self._cond_x(d)
        span = span_of(d.sym)
        tn, bn = d.pins[d.top], d.pins[d.bot]

        def gate_y(n):
            # only when this part is the node's ONLY conduction pin: if
            # something else also conducts into it, that thing decides the
            # row and the gate is just a tap off it (9.30's I_REF sits above
            # a diode-connected Q_REF, not on Q_1's base line)
            for e in self.c.devices:
                if e.ref == d.ref or e not in self.vert:
                    continue
                if n in (e.pins[e.top], e.pins[e.bot]):
                    return None
            for e in self.c.devices:
                if (e.sym in CTRL and e.ref in self.f.placed
                        and e.pins[CTRL[e.sym]] == n
                        and n not in (e.pins[e.top], e.pins[e.bot])
                        and (e.ref, CTRL[e.sym]) in self.pinxy):
                    return self.pinxy[(e.ref, CTRL[e.sym])][1]
            return None

        gt, gb = gate_y(tn), gate_y(bn)
        ytop = self.ynode[tn] + STUB if tn in self.ynode else None
        ybot = self.ynode[bn] - STUB if bn in self.ynode else None
        if ytop is None and ybot is None:
            ytop = RAIL_Y + STUB
        if ytop is None:
            cy = ybot - span / 2.0
        elif ybot is None:
            cy = ytop + span / 2.0
        else:
            lt = self.lvl.get(tn, 0)
            lb = self.lvl.get(bn, lt + 1)
            # straddling an intermediate row would put the body across that
            # row's bus, so a tall span hugs the node it hangs from
            cy = (ytop + span / 2.0 if lb - lt > 1 else (ytop + ybot) / 2.0)
        # A part that ends on a gate puts its PIN on the gate line, so the
        # bus along that line only grazes its boundary.  Splitting the
        # difference between the two rows instead left R_G straddling the
        # gate row and the bus had to detour round it (Razavi Fig 7.32).
        if gb is not None:
            cy = gb - span / 2.0
        elif gt is not None:
            cy = gt + span / 2.0
        cy = int(round(cy / 10.0)) * 10
        # A symmetric two-terminal part is drawn with pin 1 on top, always.
        # When the netlist puts the UPPER node on pin 2 the part has to be
        # turned over, or the drawing hangs it upside down: `RO1 0 out1`
        # left the grounded end above the output end, and the ground symbol
        # then landed inside the resistor (12.57(c), the bridge rectifier's
        # R, the degenerated pair's C_LR, the small-signal I_2).
        rot = 0
        if d.sym in SYMM_VERT and d.top != SYMM_VERT[d.sym][0]:
            rot = 180
        self._emit(d, cx, cy, self._mirror(d), rot)
        self._record(d)

    def _place_horiz(self, d):
        """Lying down between the two columns it joins.

        Two lateral parts across the same span would land on each other, so
        the second one steps down a row -- the horizontal twin of "parallel
        branches need their own column".
        """
        first = self.vpins(d)[0]
        p1, p2 = self.vpins(d)
        rightpin = None
        x1, x2 = self._node_x(d.pins[p1]), self._node_x(d.pins[p2])
        if x1 is not None and x2 is not None and x1 != x2:
            hi, lo = (p1, p2) if x1 > x2 else (p2, p1)
            x1 = self._node_x(d.pins[hi], "min")
            x2 = self._node_x(d.pins[lo], "max")
            p1, p2 = hi, lo
            rightpin = hi
        # A lying-down part that ends on a GATE sits at the gate's own
        # height, not on a node row.  Razavi draws v_in - R_B - A - base as
        # one straight line at the base (Fig 5.43); putting R_B on the node
        # row below it made the wire double back on itself.
        ys = []
        for n in (d.pins[p1], d.pins[p2]):
            gy = None
            for e in self.c.devices:
                if (e.sym in CTRL and e.ref in self.f.placed
                        and e.pins[CTRL[e.sym]] == n
                        and n not in (e.pins[e.top], e.pins[e.bot])
                        and (e.ref, CTRL[e.sym]) in self.pinxy):
                    gy = self.pinxy[(e.ref, CTRL[e.sym])][1]
                    break
            if gy is not None:
                ys.insert(0, gy)
            elif n in self.ynode:
                ys.append(self.ynode[n])
        cy = ys[0] if ys else RAIL_Y + 100
        if d.ref in getattr(self, "fb_track", {}):
            cy -= 40 * self.fb_track[d.ref]
        if x1 is None or x2 is None or x1 == x2:
            base = x1 if x1 is not None else (x2 if x2 is not None else X0)
            cx, rot = base + self.pitch / 2.0, 90
        else:
            cx = (x1 + x2) / 2.0
            # rotation 90 puts the symbol's pin 1 on the right, 270 puts
            # pin 2 there.  Comparing the (already swapped) x values instead
            # always chose 90, so a part declared "R vin a" came out with
            # v_in on the RIGHT and its wire doubled back round the body
            # (Razavi Fig 5.43's R_B).
            rot = 90 if rightpin == first else 270
        cx = int(round(cx / 10.0)) * 10
        half = span_of(d.sym) / 2 + 10
        cx = self._clear_x(d, cx, cy, half)
        while self._collides(d, cx, int(cy)):
            cy += 40
        self._lat.append((cy, cx - half, cx + half))
        self._emit(d, cx, int(cy), "none", rot)
        self._record(d)

    def _collides(self, d, cx, cy, span=None):
        """Would a lying-down part at (cx, cy) overlap something already
        placed?  Two parts on one spot is the horizontal twin of two
        branches in one column.

        The box is the real rotated ink plus a small margin.  A crude
        span/2+10 by +/-25 rectangle counts the shunt part hanging off the
        node at this part's own right-hand end as a collision, and R2 was
        being pushed three rows down the page to get away from C2.
        """
        if span is None:
            bb = ink_box(d.sym, None, cx, cy, "none", 90)
            box = (bb[0] - 6, bb[1] - 6, bb[2] + 6, bb[3] + 6)
        else:
            w = span / 2 + 10
            box = (cx - w, cy - 25, cx + w, cy + 25)
        for iid in self.f.placed:
            if iid == d.ref:
                continue
            b = self.f.ink(iid)
            if not (box[2] < b[0] or box[0] > b[2]
                    or box[3] < b[1] or box[1] > b[3]):
                return True
        return False

    def _clear_x(self, d, cx, cy, half):
        """A part up on a feedback track drops a riser at each of its pins.
        Slide it along the track until neither riser has to pass through a
        body sitting on the main row."""
        pins = self.vpins(d)
        span = span_of(d.sym) / 2
        rows = [self.ynode.get(d.pins[p]) for p in pins]
        best, bestn = cx, None
        for off in (0, 10, -10, 20, -20, 30, -30, 40, -40, 50, -50):
            x = cx + off
            n = 0
            for i, px in enumerate((x - span, x + span)):
                r = rows[i if len(rows) > i else 0]
                if r is None:
                    continue
                lo, hi = (cy, r) if cy < r else (r, cy)
                for iid in self.f.placed:
                    bb = self.f.ink(iid)
                    if (bb[0] - 8 <= px <= bb[2] + 8
                            and not (hi < bb[1] or lo > bb[3])):
                        n += 1
            for ly, lx0, lx1 in self._lat:
                if abs(cy - ly) < 40 and not (x + half < lx0
                                              or x - half > lx1):
                    n += 1
            if bestn is None or n < bestn:
                best, bestn = x, n
            if n == 0:
                break
        return best

    def _place_block(self, d):
        f = self.f
        pins = N.BLOCKS[d.sym]
        cx = self._cond_x(d)
        ys = [self.ynode[d.pins[p]] for p in pins if d.pins[p] in self.ynode]
        cy = int(round((sum(ys) / float(len(ys)) if ys else 200) / 10.0)) * 10
        f.place(d.ref, d.sym, cx, cy, extra={
            "schematicReference": d.ref, "schematicName": name(d.label)})
        self._record(d)

    def _emit(self, d, cx, cy, mir, rot):
        f, lab = self.f, d.label
        if d.sym in ("nmos", "pmos"):
            x = cx - 10 if mir == "none" else cx + 10
            f.mos(d.ref, d.sym, x, cy, mir, lab)
        elif d.sym in ("npn", "pnp"):
            f.bjt(d.ref, d.sym, cx, cy, mir, lab)
        elif d.sym == "current-source":
            f.isrc(d.ref, cx, cy, lab,
                   rotation=rot or (0 if d.top == "+" else 180))
        elif d.sym == "diode":
            f.place(d.ref, "diode", cx, cy,
                    rotation=(rot if rot else (90 if d.top == "A" else 270)),
                    extra={
                        "schematicReference": d.ref, "schematicName": name(lab),
                        "netlist": {"binding": {"kind": "primitive",
                                                "deviceClass": "diode"},
                                    "parameters": {}, "reference": d.ref}})
        elif d.sym in ("resistor", "capacitor"):
            f.passive(d.ref, d.sym, cx, cy, lab, rotation=rot)
        else:
            cls = {"inductor": "inductor", "inductor-compact": "inductor",
                   "variable-resistor": "resistor",
                   "variable-capacitor": "capacitor",
                   "variable-inductor": "inductor",
                   "voltage-source": "voltage-source",
                   "pulse-voltage-source": "voltage-source"}[d.sym]
            f.place(d.ref, d.sym, cx, cy, rotation=rot, extra={
                "schematicReference": d.ref, "schematicName": name(lab),
                "netlist": {"binding": {"kind": "primitive",
                                        "deviceClass": cls},
                            "parameters": {}, "reference": d.ref}})

    # ---------------------------------------------------------------- tracks
    def tracks(self):
        """One net, one trunk -- and the trunk may be a row OR a column.

        A net whose pins are spread more vertically than horizontally (the
        feedback around an op-amp chain) belongs on a vertical trunk at its
        own column; forcing it onto a row makes it cross half the drawing.
        Either way the trunk has to clear three things: another net's trunk,
        any body it would run through, and any terminal a junction on it
        would land on.  Decided once, here.
        """
        self.trunk = {}
        self.bus_y = {}
        need = []
        for nd in self.c.nodes():
            if self.c.is_ground(nd) or self.c.is_supply(nd):
                continue
            pts = [self.pinxy[t] for t in self.netterms.get(nd, [])
                   if t in self.pinxy]
            if len(set(p[0] for p in pts)) < 2 and len(set(
                    p[1] for p in pts)) < 2:
                if nd in self.ynode:
                    self.bus_y[nd] = self.ynode[nd]
                    self.trunk[nd] = ("h", self.ynode[nd])
                continue
            w = max(p[0] for p in pts) - min(p[0] for p in pts)
            h = max(p[1] for p in pts) - min(p[1] for p in pts)
            need.append((max(w, h), nd, pts, w, h))
        need.sort(reverse=True, key=lambda t: (t[0], t[1]))
        taken = []                      # every segment already committed
        inks = [(iid, self.f.ink(iid)) for iid in self.f.placed]
        # A transistor's name has exactly one legal spot, so its box is known
        # before any wire is drawn -- the bus has to dodge IT, not the other
        # way round (SOP 3A; user 2026-09-02).
        for iid, (sym, x, y, mir, _rot) in self.f.placed.items():
            d = next((e for e in self.c.devices if e.ref == iid), None)
            if d is None or sym not in CTRL:
                continue
            dx = LBL_DX.get(sym, 13)
            first = -dx if mir == "x" else dx
            box = label_box(name(d.label), x + first, y + 5,
                            "start" if first > 0 else "end")
            inks.append(("lbl:" + iid, box))
        # a port's name has one legal spot too (2026-09-02), and the ports
        # are already placed by the time the trunks are picked, so the bus
        # can dodge those boxes as well instead of landing on them
        for nd2, (pid, nm, _di) in self.ports_placed.items():
            if pid not in self.f.placed:
                continue
            _sid, x, y, mir, _rot = self.f.placed[pid]
            dx = LABEL_PORT if mir == "x" else -LABEL_PORT
            inks.append(("lbl:" + pid,
                         label_box(name(nm), x + dx, y + 5,
                                   "start" if dx > 0 else "end")))
        # A passive's name still has alternatives, so it may not FORBID a
        # row -- but the bus should still rather not land on it.  Its first
        # choice goes in as a soft obstacle only.
        for d in self.c.devices:
            if d.ref not in self.f.placed or d.sym in CTRL:
                continue
            try:
                dx, dy, al = self._label_candidates(d.ref, d.sym)[0]
            except (IndexError, KeyError):
                continue
            _sid, x, y, _mir, _rot = self.f.placed[d.ref]
            inks.append(("soft:" + d.ref,
                         label_box(name(d.label), x + dx, y + dy, al)))
        member = {}
        for nd in self.c.nodes():
            member[nd] = set(t[0] for t in self.netterms.get(nd, []))
        self._allpins = set(self.pinxy.values())
        # which net each pin belongs to: a trunk or a riser that runs OVER a
        # foreign pin draws a connection that does not exist
        self._pinnet = {}
        for nd2 in self.c.nodes():
            for t in self.netterms.get(nd2, []):
                if t in self.pinxy:
                    self._pinnet.setdefault(self.pinxy[t], set()).add(nd2)
        taken += self._power_segments()
        for _m, nd, pts, w, h in need:
            cands = []
            for axis in ("h", "v"):
                base = (self.ynode.get(nd, pts[0][1]) if axis == "h"
                        else self._trunk_x(nd, pts))
                offs = [0]
                for k in range(1, 13):
                    offs += [10 * k, -10 * k]
                for off in offs:
                    c = base + off
                    key = self._trunk_cost(nd, axis, c, pts, taken, inks,
                                           member)
                    bias = 0 if (axis == "h") == (w >= h) else 1
                    # NB tried ranking "how far the trunk sits from its own
                    # pins" right after the hard constraints: on-wire went
                    # 3 -> 7 and one more figure stopped being clean, so the
                    # distance stays a last-resort tiebreaker
                    cands.append((key + (bias, abs(off)), axis, c))
                    if key == (0, 0, 0, 0) and bias == 0:
                        break
                else:
                    continue
                break
            cands.sort()
            _k, axis, c = cands[0]
            self.trunk[nd] = (axis, c)
            if axis == "h":
                self.bus_y[nd] = c
            taken += [(nd,) + sg for sg in self._net_segments(axis, c, pts)]

    def _power_segments(self):
        """The drops off the rail and down to ground.

        They are drawn before any signal net picks a trunk, and they were
        not in the model at all -- which is where the last shorts came from
        (a rail drop and a signal riser sharing 10 units of one column).
        """
        out = []
        for nd in self.c.nodes():
            if not (self.c.is_ground(nd) or self.c.is_supply(nd)):
                continue
            pins = [self.pinxy[t] for t in self.netterms.get(nd, [])
                    if t in self.pinxy]
            if self.c.is_supply(nd):
                for x, y in pins:
                    if y != RAIL_Y:
                        out.append((nd, "v", x, min(RAIL_Y, y),
                                    max(RAIL_Y, y)))
            else:
                bycol = {}
                for x, y in pins:
                    bycol.setdefault(x, []).append(y)
                for x, ys in bycol.items():
                    if len(ys) > 1:
                        out.append((nd, "v", x, min(ys), max(ys)))
        return out

    @staticmethod
    def _net_segments(axis, c, pts):
        """Every line this net will draw: the trunk, plus one cross leg per
        pin.  The cross legs are the part the old cost model ignored, and
        they are exactly where Fig 7.94's V_in/V_out short came from.

        A segment is (axis, fixed coordinate, lo, hi) along the other axis.
        """
        ai, ci = (0, 1) if axis == "h" else (1, 0)
        a0 = min(p[ai] for p in pts)
        a1 = max(p[ai] for p in pts)
        out = [(axis, c, a0, a1)]
        other = "v" if axis == "h" else "h"
        for p in pts:
            if p[ci] == c:
                continue
            lo, hi = sorted((p[ci], c))
            out.append((other, p[ai], lo, hi))
        return out

    def _trunk_x(self, nd, pts):
        """Where a vertical trunk starts looking.

        It must be AMONG THE PINS.  The node's nominal column can be far
        outside them -- a free node whose column index is 0 while every pin
        it owns sits at x=320 -- and a trunk there sends the wire off the
        side of the drawing and back (2026-08-31: net-inp of a 5T OTA ran
        200 units out to the left and returned).
        """
        xs = sorted(p[0] for p in pts)
        x = self._node_x(nd)
        if x is None or not (xs[0] <= x <= xs[-1]):
            x = xs[len(xs) // 2]
        return int(round(x / 10.0)) * 10

    def _trunk_cost(self, nd, axis, c, pts, taken, inks, member):
        """(hard, bodies, risers, overlap) -- lower is better.

        `hard` is what the drawing may not contain at all: a junction landing
        on a terminal (the schema rejects it) and two nets sharing one line
        (the reader sees a short).  The rest is comfort.
        """
        M = 8
        ai, ci = (0, 1) if axis == "h" else (1, 0)   # along, across index
        a0 = min(p[ai] for p in pts)
        a1 = max(p[ai] for p in pts)
        mine = self._net_segments(axis, c, pts)
        sep = int(os.environ.get("AC_SEP", 30))
        shorted = overlap = cross = 0
        for onet, oax, oc, o0, o1 in taken:
            if onet == nd:
                continue
            for max_, mc, m0, m1 in mine:
                if max_ != oax:
                    # perpendicular: do they actually cross?  Crossing is
                    # legal (no junction, no connection) but it is what makes
                    # a drawing hard to read, so count it (user, 2026-09-02).
                    if m0 < oc < m1 and o0 < mc < o1:
                        cross += 1
                    continue
                if m1 < o0 or m0 > o1:
                    continue
                if mc == oc:
                    shorted += 1
                elif abs(mc - oc) < sep:
                    overlap += 1
        hard = shorted
        # a wire that passes through someone else's pin reads as a solder
        # joint -- Sallen-Key ran n1's bus over R1's V_in pin and the output
        # riser straight through the op-amp's IN+ (user 2026-09-02)
        for pxy, owners in self._pinnet.items():
            if nd in owners:
                continue
            px, py = pxy
            for max_, mc, m0, m1 in mine:
                if max_ == "h":
                    if py == mc and m0 <= px <= m1:
                        hard += 1
                        break
                elif px == mc and m0 <= py <= m1:
                    hard += 1
                    break
        bytap = {}
        for p in pts:
            bytap.setdefault(p[ai], []).append(p[ci])
        keys = sorted(bytap)
        for i, k in enumerate(keys):
            ends = 1 if i in (0, len(keys) - 1) else 2
            segs = ends + len([1 for v in bytap[k] if v != c])
            pt = (k, c) if axis == "h" else (c, k)
            if segs >= 3 and pt in self._allpins:
                hard += 1
        # how much wire this trunk costs: the trunk itself plus one riser
        # per pin.  Minimised at the median of the pins, which is also what
        # stops the bus wandering off and dragging every riser with it.
        wire = (a1 - a0) + sum(abs(p[ci] - c) for p in pts)
        bodies = risers = 0
        for iid, bb in inks:
            if iid in member.get(nd, ()):
                # A wire may touch its own component's pin -- it may not go
                # INSIDE the body to get there.  This one exemption is what
                # let a bus ride over a gate lead, cut across an op-amp
                # triangle and come back up through a capacitor (user,
                # 2026-09-02).  Entering is forbidden, not merely costly.
                lo, hi = ((bb[1] + 1, bb[3] - 1) if axis == "h"
                          else (bb[0] + 1, bb[2] - 1))
                alo, ahi = ((bb[0] + 1, bb[2] - 1) if axis == "h"
                            else (bb[1] + 1, bb[3] - 1))
                if lo < c < hi and not (a1 <= alo or a0 >= ahi):
                    hard += 1                    # the trunk itself is inside
                for p in pts:
                    if not (alo < p[ai] < ahi):
                        continue
                    q0, q1 = (p[ci], c) if p[ci] < c else (c, p[ci])
                    if q0 < hi and q1 > lo:      # the riser dips inside
                        hard += 1
                        break
                continue
            lo, hi = (bb[1], bb[3]) if axis == "h" else (bb[0], bb[2])
            alo, ahi = (bb[0], bb[2]) if axis == "h" else (bb[1], bb[3])
            # Entering someone else's body is exactly as illegal as entering
            # your own: `_body_audit` does not care whose part it is.  The
            # cost model used to price a foreign body as a soft `bodies`
            # point, so the search happily drove a bus through a diode
            # (bridge rectifier) and through an op-amp triangle (14.36(b)).
            if (not iid.startswith("soft:") and lo + 1 < c < hi - 1
                    and not (a1 <= alo + 1 or a0 >= ahi - 1)):
                hard += 1
                continue
            if lo - M <= c <= hi + M and not (a1 < alo - M or a0 > ahi + M):
                # `_wire_clearance` calls anything closer than M a wire that
                # "reads as a connection that is not there", so on some
                # figures the soft price is too cheap (14.36(b) parked three
                # wires 5 units off OA2).  Which price is right depends on
                # how much room the figure has, so it is an axis.
                if (str(self.opt("bodycost", "soft")) == "hard"
                        and not iid.startswith("soft:")):
                    hard += 1
                else:
                    bodies += 1
                continue
            deep = False
            for p in pts:
                if iid.startswith("soft:"):
                    break
                if alo + 1 < p[ai] < ahi - 1:
                    q0, q1 = (p[ci], c) if p[ci] < c else (c, p[ci])
                    if q0 < hi - 1 and q1 > lo + 1:
                        hard += 1
                        deep = True
                        break
            if deep:
                continue
            for p in pts:
                if not (alo - M <= p[ai] <= ahi + M):
                    continue
                q0, q1 = (p[ci], c) if p[ci] < c else (c, p[ci])
                if not (q1 < lo - M or q0 > hi + M):
                    risers += 1
                    break
        order = self.opt("cost", "hbRwo")
        vals = {"h": hard, "b": bodies, "r": risers, "w": wire // 10,
                "o": overlap, "x": cross,
                # "R" weighs a crossing and a body-crossing riser the same:
                # both are "this wire has to get past something"
                "R": risers + cross,
                "S": risers + 2 * cross}
        return tuple(vals[k] for k in order)

    def netterms_raw(self, nd):
        return [(d.ref, p) for d in self.c.devices
                for p, n in d.pins.items() if n == nd]

    # ---------------------------------------------------------------- wiring
    def wire(self):
        f = self.f
        self.netid = {}
        self.netterms = {}
        for nd in self.c.nodes():
            self.netid[nd] = "net-" + nd
            self.netterms[nd] = [(d.ref, p) for d in self.c.devices
                                 for p, n in d.pins.items() if n == nd]
        self.ports_placed = {}
        self.grounds = []
        self._settle_mirrors()
        self._add_ports()
        self._spread_for_labels()
        if str(self.opt("compact", "0")) == "1":
            self._compact()
        self._add_supply()
        self.tracks()
        self._settle_ports()
        self._settle_laterals()
        # grounds go in AFTER the lying-down parts have slid into place: a
        # lateral that moves into a column can land between two pins that
        # were already grouped onto one ground symbol, and then the drop
        # wire runs straight through it (R_O1, C_LR, R, I_2 -- all four
        # WIRE INSIDE BODY left on 2026-09-02 were this)
        self._add_grounds()
        self.tracks()               # positions moved, so pick the rows again
        self._settle_ports()
        for nd in self.c.nodes():
            f.net(self.netid[nd], self.netterms[nd])
        self.long_haul, self.rail_ends = set(), set()
        for nd in self.c.nodes():
            if self.c.is_ground(nd):
                self._wire_ground(nd)
            elif self.c.is_supply(nd):
                self._wire_supply(nd)
            else:
                self._wire_node(nd)

    def _set_mirror(self, iid, m):
        sid, x, y, _mir, rot = self.f.placed[iid]
        for i in self.f.instances:
            if i["id"] == iid:
                i["placement"]["mirror"] = m
        self.f.placed[iid] = (sid, x, y, m, rot)
        for t in list(self.pinxy):
            if t[0] == iid:
                self.pinxy[t] = self.f.pin(*t)

    def _gate_cost(self, d):
        """How bad this transistor's mirror is, in real coordinates.

        Only the gate moves when a MOS or a BJT is mirrored -- drain and
        source sit on the centre line -- so the choice is purely "which side
        does the control lead come out of", and it can be made AFTER every
        part is placed, when the other pins of the gate net are actually
        known.  Deciding it during placement (from column indices alone) is
        what left gates pointing away from the wire that drives them.
        """
        g = CTRL[d.sym]
        gnode = d.pins[g]
        gp = self.pinxy.get((d.ref, g))
        if gp is None:
            return 0
        others = [self.pinxy[t] for t in self.netterms_raw(gnode)
                  if t != (d.ref, g) and t in self.pinxy]
        pen = 0
        for iid in self.f.placed:
            if iid == d.ref:
                continue
            b = self.f.ink(iid)
            if (b[0] - 8 <= gp[0] <= b[2] + 8
                    and b[1] - 8 <= gp[1] <= b[3] + 8):
                pen += 10000          # the lead ends up in someone's body
        if not others:
            # nothing but a port drives it.  The input comes in from the
            # left edge (user, 2026-09-02), so the gate faces left; any
            # other lone port goes to the side with more room.
            if (str(self.opt("inleft", "1")) == "1"
                    and any(nd == gnode and di == "input"
                            for nd, _nm, di in self.c.ports)):
                _sid, x, _y, mir, _rot = self.f.placed[d.ref]
                return pen + (0 if gp[0] < x else 500)
            free = min([abs(gp[0] - self.f.ink(i)[2 if gp[0] > 0 else 0])
                        for i in self.f.placed if i != d.ref] or [0])
            return pen - free
        return pen + sum(abs(gp[0] - q[0]) + abs(gp[1] - q[1])
                         for q in others)

    def _settle_mirrors(self):
        """Pick every gate's side once the whole drawing is on the page.

        User, 2026-09-02: "MOS 鏡像就可以讓很多擺起來很好看".  A
        few sweeps, because flipping one gate moves the centre the next one
        is aiming at.
        """
        if str(self.opt("mirfix", "1")) != "1":
            return
        forced = dict(self.opt("formir", ()) or ())
        # A differential pair's two inputs face OUTWARD, one port each side
        # (Razavi Fig 10.34, 10.35): the pair is two control devices sharing
        # a tail node whose gates are driven by different nets.
        if str(self.opt("diffpair", "1")) == "1":
            bybot = {}
            for d in self.c.devices:
                if d.sym not in CTRL or d.ref not in self.f.placed:
                    continue
                bot = d.pins[FIXED_VERT[d.sym][1]] if d.sym in FIXED_VERT                     else None
                if bot is None or self.c.is_ground(bot):
                    continue
                bybot.setdefault(bot, []).append(d)
            for bot, ds in bybot.items():
                if len(ds) != 2:
                    continue
                a, b = ds
                ga, gb = a.pins[CTRL[a.sym]], b.pins[CTRL[b.sym]]
                if ga == gb or a.sym != b.sym:
                    continue
                if len(self.netterms_raw(ga)) != 1 or                         len(self.netterms_raw(gb)) != 1:
                    continue          # a gate that is also driven elsewhere
                left, right = sorted((a, b),
                                     key=lambda e: self.f.placed[e.ref][1])
                forced.setdefault(left.ref, "none")   # gate out to the left
                forced.setdefault(right.ref, "x")     # gate out to the right
        for ref, m in forced.items():
            if ref in self.f.placed:
                self._set_mirror(ref, m)
        for _ in range(4):
            moved = False
            for d in self.c.devices:
                if (d.sym not in CTRL or d.ref not in self.f.placed
                        or d.ref in forced):
                    continue
                cur = self.f.placed[d.ref][3]
                best, bestk = cur, None
                for m in ("none", "x"):
                    self._set_mirror(d.ref, m)
                    k = self._gate_cost(d)
                    if bestk is None or k < bestk:
                        best, bestk = m, k
                self._set_mirror(d.ref, best)
                moved = moved or best != cur
            if not moved:
                return

    def _add_ports(self):
        f = self.f
        declared = [p[0] for p in self.c.ports]
        extra = []
        for nd in self.c.nodes():
            if nd in declared or self.c.is_ground(nd) or self.c.is_supply(nd):
                continue
            if len(self.netterms_raw(nd)) == 1:
                # a node with one pin is an open end; a schematic draws that
                # as a port, and the schema needs the terminal wired anyway
                extra.append((nd, self.c.port_of(nd)[0] if self.c.port_of(nd)
                              else nd.upper(), "output"))
        inrows = set()
        for nd, nm, di in list(self.c.ports) + extra:
            pins = [self.pinxy[t] for t in self.netterms[nd]
                    if t in self.pinxy]
            if not pins:
                continue
            # A port is a SHORT STRAIGHT stub, never a dog-leg (user,
            # 2026-09-02).  When the port is the only other thing on the
            # net, sit it on the pin's own row so the wire is one segment;
            # if that crowds something, the mirror rule turns the gate
            # outwards and the retry widens the columns.
            devpins = [t for t in self.netterms[nd] if t in self.pinxy]
            # A port that feeds nothing but ONE gate is a bias, not the
            # signal: Razavi puts V_b right beside the transistor it biases
            # (Fig 9.83) and the two inputs of a differential pair one each
            # side (Fig 10.35(a)).  Dragging those to the left edge makes
            # their wire cross the whole drawing.  The signal input -- the
            # one that reaches a conduction path or a passive -- still comes
            # in from the left (user, 2026-09-02).
            gateonly = (len(devpins) == 1
                        and any(d.ref == devpins[0][0] and d.sym in CTRL
                                and devpins[0][1] == CTRL[d.sym]
                                for d in self.c.devices))
            leftrow = None
            if (di == "input" and not gateonly
                    and str(self.opt("inleft", "1")) == "1"):
                leftrow = (self.pinxy[[t for t in self.netterms[nd]
                                       if t in self.pinxy][0]][1]
                           if len([t for t in self.netterms[nd]
                                   if t in self.pinxy]) == 1
                           else self.ynode.get(nd, pins[0][1]))
            if leftrow is not None and leftrow not in inrows:
                # An input port sits at the LEFT EDGE of the drawing, on the
                # row of the pin it feeds -- "我認為這符合絕大多數的電路"
                # (user, 2026-09-02).  Before this the stub simply left along
                # whatever direction its pin happened to face, so Fig 5.170's
                # V_in came in from underneath the drawing.
                # ...unless another input is already using that row: two
                # ports at the same x AND the same y are one on top of the
                # other, which is what a differential pair asks for (its two
                # gates share a row, and the book puts V_in1 left, V_in2
                # right).  The second one keeps the old behaviour.
                inrows.add(leftrow)
                y = leftrow
                edge = min([self.f.ink(iid)[0] for iid in self.f.placed]
                           or [X0])
                x = min(edge, min(p[0] for p in pins)) - self.portstub - 10
                mir = "none"
            elif len(devpins) == 1:
                # One pin: the stub leaves along the direction that pin
                # actually FACES.  Reading `input` as "put it on the left"
                # drops the port inside a mirrored MOS and drags the wire
                # back through the body to reach the gate (user 2026-09-02:
                # "pin 就是短短的一個直線").
                t = devpins[0]
                px, py = self.pinxy[t]
                d = self.f.pin_dir(*t) or ((-1, 0) if di == "input"
                                           else (1, 0))
                if d[0]:
                    x, y = px + d[0] * (self.portstub + 10), py
                    mir = "none" if d[0] < 0 else "x"
                else:
                    x, y = px, py + d[1] * (self.portstub + 10)
                    mir = "none"
            elif di == "input":
                y = self.ynode.get(nd, pins[0][1])
                x = min(p[0] for p in pins) - self.portstub - 10
                mir = "none"
            else:
                y = self.ynode.get(nd, pins[0][1])
                x = max(p[0] for p in pins) + self.portstub + 10
                mir = "x"
            pid = "P" + nd.upper().replace("-", "")
            f.port(pid, int(round(x / 10.0)) * 10, y, mirror=mir)
            self.pinxy[(pid, "P")] = f.pin(pid, "P")
            self.netterms[nd].append((pid, "P"))
            self.ports_placed[nd] = (pid, nm, di)
            f.terminal("t-" + nd, nm, self.netid[nd], di, [pid])

    def _insert_space(self, cut, delta):
        """Push everything to the right of `cut` further right.

        Called before any wire exists, so nothing has to be re-routed: the
        column table moves with the parts, and the pins are recomputed.
        """
        f = self.f
        for iid, (sid, x, y, mir, rot) in list(f.placed.items()):
            if x <= cut:
                continue
            for i in f.instances:
                if i["id"] == iid:
                    i["placement"]["position"] = {"x": x + delta, "y": y}
            f.placed[iid] = (sid, x + delta, y, mir, rot)
        for t in list(self.pinxy):
            if t[0] in f.placed:
                try:
                    self.pinxy[t] = f.pin(*t)
                except KeyError:
                    pass
        for k, v in list(self.col_x.items()):
            if v > cut:
                self.col_x[k] = v + delta

    def _col_boxes(self):
        """Everything that occupies horizontal room, grouped by column.

        Ink plus the two kinds of label whose position is fixed before any
        wire exists (a transistor's name and a port's name).  A passive's
        name still has alternatives, so it is not allowed to hold a column
        apart.
        """
        cols = {}
        for iid, (sid, x, y, mir, _rot) in self.f.placed.items():
            b = self.f.ink(iid)
            cols.setdefault(x, []).append(b)
            d = next((e for e in self.c.devices if e.ref == iid), None)
            if d is not None and sid in CTRL:
                dx = LBL_DX.get(sid, 13)
                first = -dx if mir == "x" else dx
                cols[x].append(label_box(name(d.label), x + first, y + 5,
                                         "start" if first > 0 else "end"))
        for nd, (pid, nm, _di) in self.ports_placed.items():
            if pid not in self.f.placed:
                continue
            _sid, x, y, mir, _rot = self.f.placed[pid]
            dx = LABEL_PORT if mir == "x" else -LABEL_PORT
            cols.setdefault(x, []).append(
                label_box(name(nm), x + dx, y + 5,
                          "start" if dx > 0 else "end"))
        return cols

    def _compact(self, gap=None):
        """Squeeze out the space the widening did not actually need.

        "It does not fit" is answered by a wider grid, but the grid is
        global: one crowded column pushes every column to pitch 180 and the
        rest of the drawing floats apart (Diff-amp shunt-peak came out 753
        wide against a 340-wide original).  Nothing is routed yet, so the
        columns can simply be pulled back together until each pair is `gap`
        apart at its closest point.
        """
        gap = int(os.environ.get("AC_CGAP", "20")) if gap is None else gap
        for _ in range(3):
            cols = self._col_boxes()
            xs = sorted(cols)
            moved = False
            for i in range(len(xs) - 1):
                left = max(b[2] for x in xs[:i + 1] for b in cols[x])
                right = min(b[0] for b in cols[xs[i + 1]])
                slack = int((right - left - gap) // 10 * 10)
                if slack > 0:
                    self._insert_space(xs[i], -slack)
                    moved = True
                    break
            if not moved:
                return

    def _fixed_boxes(self):
        """Everything whose position is settled before any wire exists.

        Component ink, a transistor's name (one legal spot, SOP 3A) and a
        port's name (one legal spot beside its circle).  A passive's name
        still has alternatives, so it is not in here -- it can move itself.
        Each entry carries the x of the instance it belongs to, which is
        what decides who gets pushed when room has to be made.
        """
        out = []
        for iid, (sid, x, y, mir, _rot) in self.f.placed.items():
            out.append((iid, x, self.f.ink(iid)))
            d = next((e for e in self.c.devices if e.ref == iid), None)
            if d is not None and sid in CTRL:
                dx = LBL_DX.get(sid, 13)
                first = -dx if mir == "x" else dx
                out.append((iid, x,
                            label_box(name(d.label), x + first, y + 5,
                                      "start" if first > 0 else "end")))
        for _nd, (pid, nm, _di) in self.ports_placed.items():
            if pid not in self.f.placed:
                continue
            _sid, x, y, mir, _rot = self.f.placed[pid]
            dx = LABEL_PORT if mir == "x" else -LABEL_PORT
            out.append((pid, x,
                        label_box(name(nm), x + dx, y + 5,
                                  "start" if dx > 0 else "end")))
        return out

    def _spread_for_labels(self):
        """A name that does not fit gets ROOM, not a new position.

        The user's ruling on transistor names -- one legal spot, and if it
        does not fit you pull the circuit apart (2026-09-02) -- applies to
        every name whose place is already decided.  Widening the whole grid
        is the blunt version and leaves a hole in the middle; here only the
        gap that is actually short gets wider, and nothing is routed yet so
        nothing has to be re-drawn.
        """
        for _ in range(6):
            boxes = self._fixed_boxes()
            worst = None
            for i in range(len(boxes)):
                oi, xi, bi = boxes[i]
                for j in range(i + 1, len(boxes)):
                    oj, xj, bj = boxes[j]
                    if oi == oj or xi == xj:
                        continue
                    gap = _box_gap_box(bi, bj)
                    if gap >= LABEL_INK_GAP:
                        continue
                    need = int(LABEL_INK_GAP - gap + 9) // 10 * 10
                    cut = min(xi, xj)
                    if worst is None or need > worst[1]:
                        worst = (cut, need)
            if worst is None:
                return
            self._insert_space(*worst)

    def _add_supply(self):
        """A rail needs no symbol, a single tap does.  Either way the marker
        has to exist before the nets are declared, or the route that reaches
        it is not a member of its own net."""
        nd = next((n for n in self.c.nodes() if self.c.is_supply(n)), None)
        self.supply_node = nd
        self.supply_marker = None
        if nd is None:
            return
        pins = [t for t in self.netterms[nd] if t in self.pinxy]
        if len(pins) >= 2:
            self.f.rail_end = "jvdd-end"
            return
        if not pins:
            return
        x, y = self.pinxy[pins[0]]
        self.f.place("VDDP", "vdd-port", x, y - 40,
                     extra={"schematicReference": "VDD"})
        self.pinxy[("VDDP", "P")] = self.f.pin("VDDP", "P")
        self.netterms[nd].append(("VDDP", "P"))
        self.f.rail_end = "VDDP"
        self.supply_marker = "VDDP"

    def _settle_ports(self):
        """A port marks the end of its bus, so it follows the row the bus
        finally took."""
        for nd, (pid, _nm, _di) in self.ports_placed.items():
            y = self.bus_y.get(nd)
            if y is None:
                continue
            others = [t for t in self.netterms[nd]
                      if t in self.pinxy and t[0] != pid]
            if len(others) == 1:
                continue          # a straight one-segment stub: leave it
            sid, x, oy, mir, rot = self.f.placed[pid]
            if y == oy:
                continue
            for i in self.f.instances:
                if i["id"] == pid:
                    i["placement"]["position"]["y"] = y
            self.f.placed[pid] = (sid, x, y, mir, rot)
            self.pinxy[(pid, "P")] = self.f.pin(pid, "P")

    def _settle_laterals(self):
        """A lying-down part belongs ON its own net's row.  If the row moved,
        the part follows it -- otherwise it floats beside its own bus and
        every other net's bus is free to run through it."""
        for d in self.horiz:
            p1, p2 = self.vpins(d)
            ys = set(self.bus_y.get(d.pins[p]) for p in (p1, p2))
            ys.discard(None)
            if len(ys) != 1:
                continue
            y = ys.pop()
            sid, x, oy, mir, rot = self.f.placed[d.ref]
            if y == oy or d.ref in getattr(self, "fb_track", {}):
                continue
            if self._collides(d, x, y):
                continue
            for i in self.f.instances:
                if i["id"] == d.ref:
                    i["placement"]["position"]["y"] = y
            self.f.placed[d.ref] = (sid, x, y, mir, rot)
            for pn in d.pins:
                try:
                    self.pinxy[(d.ref, pn)] = self.f.pin(d.ref, pn)
                except KeyError:
                    pass

    def _add_grounds(self):
        """One symbol per RUN of pins in a column, at the bottom of the run.

        SOP 3E rule 4 wants the row shared, but only while every stub stays
        inside the 40-unit leg budget -- past that the stub is the defect.

        A column is not always one run.  Two grounded parts can sit in the
        same column with a third part between them, and chaining their pins
        into one wire drives that wire straight through the part in between
        (12.57(c) through R_O1, the bridge rectifier through R, the
        degenerated pair through C_LR).  So the column is cut wherever the
        chain would enter a body, and each piece grounds itself.
        """
        f = self.f
        nd = N.GROUND_NODE
        self.ggroups = []
        if nd not in self.netterms:
            self.gpairs = []
            return
        pins = [t for t in self.netterms[nd] if t in self.pinxy]
        if not pins:
            self.gpairs = []
            return
        bycol = {}
        for t in pins:
            x, y = self.pinxy[t]
            bycol.setdefault(x, []).append((y, t))
        row = max(max(y for y, _t in v) for v in bycol.values()) + STUB_GND
        out = []
        n = 0
        for x in sorted(bycol):
            seq = sorted(bycol[x])
            runs = [[seq[0]]]
            for prev, cur in zip(seq, seq[1:]):
                if self._body_between(x, prev[0], cur[0]):
                    runs.append([cur])
                else:
                    runs[-1].append(cur)
            for run in runs:
                low = max(y for y, _t in run)
                gy = (row if len(runs) == 1 and row - low <= 60
                      and not self._body_between(x, low, row)
                      else low + STUB_GND)
                n += 1
                gid = "G%d" % n
                f.gnd(gid, x, gy + 10)
                self.pinxy[(gid, "0")] = f.pin(gid, "0")
                self.netterms[nd].append((gid, "0"))
                out.append((gid, x))
                self.ggroups.append((x, [t for _y, t in run] + [(gid, "0")]))
        self.gpairs = out

    def _body_between(self, x, y0, y1, skip=()):
        """Would a straight drop down column x, from y0 to y1, enter a body?

        Nothing is exempt, not even the part the wire ends on: a pin sits on
        the boundary, so a stub that only touches it does not register, but
        a wire coming down from ABOVE a part to its LOWER pin crosses the
        whole body and must (12.57(c) did exactly that through R_O1).
        """
        lo, hi = min(y0, y1), max(y0, y1)
        for iid in self.f.placed:
            if iid in skip:
                continue
            b = self.f.ink(iid)
            if b[0] + 1 < x < b[2] - 1 and lo < b[3] - 1 and hi > b[1] + 1:
                return True
        return False

    # -- helpers -------------------------------------------------------
    def _route_pair(self, rid, net, a, b, bus_y=None):
        """orthogonal route between two pin coordinates"""
        f = self.f
        (ax, ay), (bx, by) = self.pinxy[a], self.pinxy[b]
        steps = []
        if ax != bx and ay != by:
            steps.append(("bend", ax, by) if bus_y is None else
                         ("bend", ax, bus_y))
            if bus_y is not None and by != bus_y:
                steps.append(("bend", bx, bus_y))
        f.route(rid, net, f.term(*a), steps + [("to", f.term(*b))])
        self._note_legs(rid, [(ax, ay)] + [(s[1], s[2]) for s in steps]
                        + [(bx, by)])

    def _note_legs(self, rid, pts):
        for i in range(len(pts) - 1):
            d = abs(pts[i][0] - pts[i + 1][0]) + abs(pts[i][1] - pts[i + 1][1])
            if d > 40:
                self.long_haul.add(rid)

    def _wire_ground(self, nd):
        """Each run of pins drops straight onto its own ground symbol; the
        symbols themselves are not wired to each other (SOP 3I)."""
        f = self.f
        for gi, (x, seq) in enumerate(getattr(self, "ggroups", [])):
            ys = [(self.pinxy[t][1], t) for t in seq if t in self.pinxy]
            ys.sort()
            for i in range(len(ys) - 1):
                if ys[i][0] == ys[i + 1][0]:
                    continue                  # pin on pin: already connected
                rid = "r-gnd-%d-%d-%d" % (x, gi, i)
                f.route(rid, self.netid[nd], f.term(*ys[i][1]),
                        [("to", f.term(*ys[i + 1][1]))])
                self._note_legs(rid, [(x, ys[i][0]), (x, ys[i + 1][0])])

    @staticmethod
    def _supply_label():
        return "V_DD"

    def _wire_supply(self, nd):
        f = self.f
        pins = [(self.pinxy[t][0], t) for t in self.netterms[nd]
                if t in self.pinxy and t[0] != self.supply_marker]
        pins.sort()
        xs = [p[0] for p in pins]
        if self.supply_marker is None and len(pins) >= 2:
            lo, hi = min(xs) - RAIL_OVERHANG, max(xs) + RAIL_OVERHANG
            taps = [lo] + sorted(set(xs)) + [hi]
            for i, x in enumerate(taps):
                jid = ("jvdd-start" if i == 0 else
                       "jvdd-end" if i == len(taps) - 1 else "jvdd-%d" % i)
                f.junction(jid, self.netid[nd], x, RAIL_Y)
            f.rail(self.netid[nd], RAIL_Y, taps)
            for i in range(len(taps) - 1):
                self.long_haul.add("r-vdd-rail-%d" % i)
            self.rail_ends |= {"jvdd-start", "jvdd-end"}
            for x, t in pins:
                jid = f._jat(x, RAIL_Y)
                rid = "r-vdd-%s-%s" % (t[0].lower(), t[1].lower())
                f.route(rid, self.netid[nd], f.jn(jid), [("to", f.term(*t))])
                self._note_legs(rid, [(x, RAIL_Y), self.pinxy[t]])
            f.power_label("label-vdd", self.netid[nd], "jvdd-end", 12, 6,
                          self._supply_label())
            self.f.rail_end = "jvdd-end"
        elif pins:
            t = pins[0][1]
            self._route_pair("r-vdd-0", self.netid[nd], ("VDDP", "P"), t)

    def _seg_clear(self, nd, axis, c, a0, a1):
        """Is this straight run free of bodies and of foreign pins?

        `axis` is the run's direction, `c` the coordinate it holds, `a0..a1`
        how far it goes.  Bodies count from one unit inside their ink, so a
        wire that only touches a pin on the boundary is fine.
        """
        lo, hi = min(a0, a1), max(a0, a1)
        for iid in self.f.placed:
            b = self.f.ink(iid)
            if axis == "h":
                if b[1] + 1 < c < b[3] - 1 and lo < b[2] - 1 and hi > b[0] + 1:
                    return False
            elif b[0] + 1 < c < b[2] - 1 and lo < b[3] - 1 and hi > b[1] + 1:
                return False
        for (px, py), owners in getattr(self, "_pinnet", {}).items():
            if nd in owners:
                continue
            if axis == "h":
                if py == c and lo <= px <= hi:
                    return False
            elif px == c and lo <= py <= hi:
                return False
        # ...and it may not lie ON another net's wire: two nets sharing one
        # line read as one wire (the bridge rectifier's input run landed on
        # top of net-act for 50 units once the input port moved to the left
        # edge)
        mine = self.netid.get(nd)
        net_of = {r["id"]: r.get("netId") for r in self.f.routes}
        for rid, x0, y0, x1, y1 in self.f.segments():
            if net_of.get(rid) == mine:
                continue
            if axis == "h":
                if y0 == y1 == c and min(x0, x1) < hi and max(x0, x1) > lo:
                    return False
            elif x0 == x1 == c and min(y0, y1) < hi and max(y0, y1) > lo:
                return False
        return True

    def _xy(self, axis, along, across):
        return (along, across) if axis == "h" else (across, along)

    def _crosses_committed(self, nd, pts):
        """How many wires of OTHER nets this polyline would cross.

        A detour is free to pick any offset that clears the obstacle, so it
        may as well pick the one that walks over the fewest other wires --
        otherwise dodging a body just moves the mess into the crossings
        count (26 crossings after detours went in, from 23).
        """
        mine = self.netid[nd]
        net_of = {r["id"]: r.get("netId") for r in self.f.routes}
        segs = list(zip(pts, pts[1:]))
        n = 0
        for rid, x0, y0, x1, y1 in self.f.segments():
            if net_of.get(rid) == mine:
                continue
            for (ax0, ay0), (ax1, ay1) in segs:
                if x0 == x1 and ay0 == ay1:
                    if (min(y0, y1) < ay0 < max(y0, y1)
                            and min(ax0, ax1) < x0 < max(ax0, ax1)):
                        n += 1
                elif y0 == y1 and ax0 == ax1:
                    if (min(x0, x1) < ax0 < max(x0, x1)
                            and min(ay0, ay1) < y0 < max(ay0, ay1)):
                        n += 1
        return n

    def _cross_detour(self, nd, axis, k, v, c):
        """A jog for the leg that joins a pin to its trunk.

        The leg runs across the trunk's direction at position `k`, from the
        pin at `v` to the trunk at `c`.  Straight is the default; when
        something sits on it -- Fig 8.57's net-x rose from IN- straight
        through IN+ -- the leg steps sideways for its whole length and
        comes back at both ends.
        """
        other = "v" if axis == "h" else "h"
        if self._seg_clear(nd, other, k, v, c):
            return None
        best, bestk = None, None
        for dk in (10, -10, 20, -20, 30, -30):
            k2 = k + dk
            if not (self._seg_clear(nd, other, k2, v, c)
                    and self._seg_clear(nd, axis, v, k, k2)
                    and self._seg_clear(nd, axis, c, k, k2)):
                continue
            pts = [self._xy(axis, k, v), self._xy(axis, k2, v),
                   self._xy(axis, k2, c), self._xy(axis, k, c)]
            key = (self._crosses_committed(nd, pts), abs(dk))
            if bestk is None or key < bestk:
                best, bestk = k2, key
        return best

    def _bus_detour(self, nd, axis, c, k0, k1):
        """A jog around whatever sits on the straight run between two taps.

        Until now every leg of a net was a straight line, so a bus with a
        part or a foreign pin in the way had no answer at all -- the trunk
        search could only pick a different row for the WHOLE net.  Here the
        run steps aside for the middle of its span and comes back, which is
        what a person draws (SOP 3J, "引線遇到障礙要繞路", 2026-08-31).

        Returns (offset row/column, inset) or None when the straight run is
        already clear or no jog works.
        """
        if self._seg_clear(nd, axis, c, k0, k1):
            return None
        e = 10
        if k1 - k0 <= 3 * e:
            return None
        other = "v" if axis == "h" else "h"
        if not (self._seg_clear(nd, axis, c, k0, k0 + e)
                and self._seg_clear(nd, axis, c, k1 - e, k1)):
            return None
        best, bestk = None, None
        for off in (10, -10, 20, -20, 30, -30, 40, -40):
            c2 = c + off
            lo, hi = min(c, c2), max(c, c2)
            if not (self._seg_clear(nd, axis, c2, k0 + e, k1 - e)
                    and self._seg_clear(nd, other, k0 + e, lo, hi)
                    and self._seg_clear(nd, other, k1 - e, lo, hi)):
                continue
            pts = [self._xy(axis, k0, c), self._xy(axis, k0 + e, c),
                   self._xy(axis, k0 + e, c2), self._xy(axis, k1 - e, c2),
                   self._xy(axis, k1 - e, c), self._xy(axis, k1, c)]
            key = (self._crosses_committed(nd, pts), abs(off))
            if bestk is None or key < bestk:
                best, bestk = (c2, e), key
        return best

    def _wire_node(self, nd):
        """One net, one trunk.

        Pins are grouped by their coordinate ALONG the trunk.  A tap gets a
        junction only where three or more wires really meet -- that is what
        draws the dot (SOP 3H rule 4) -- and a two-wire corner gets a bend.
        """
        f = self.f
        ts = [t for t in self.netterms[nd] if t in self.pinxy]
        if len(ts) < 2:
            return
        axis, c = self.trunk.get(nd, ("h", self.bus_y.get(
            nd, self.ynode.get(nd, self.pinxy[ts[0]][1]))))
        ai, ci = (0, 1) if axis == "h" else (1, 0)

        def xy(along, across):
            return (along, across) if axis == "h" else (across, along)

        groups = {}
        for t in ts:
            p = self.pinxy[t]
            groups.setdefault(p[ai], []).append((p[ci], t))
        keys = sorted(groups)
        if len(keys) == 1:                      # a plain collinear stack
            seq = sorted(groups[keys[0]])
            for i in range(len(seq) - 1):
                if seq[i][0] == seq[i + 1][0]:
                    continue      # pin on pin: connected, no wire needed
                rid = "r-%s-%d" % (nd, i)
                f.route(rid, self.netid[nd], f.term(*seq[i][1]),
                        [("to", f.term(*seq[i + 1][1]))])
                self._note_legs(rid, [xy(keys[0], seq[i][0]),
                                      xy(keys[0], seq[i + 1][0])])
            return
        anchor, kind = {}, {}
        for i, k in enumerate(keys):
            on = [t for v, t in groups[k] if v == c]
            ends = 1 if i in (0, len(keys) - 1) else 2
            segs = ends + len([1 for v, _t in groups[k] if v != c])
            if segs >= 3:
                jid = "j-%s-%d" % (nd, i)
                x, y = xy(k, c)
                f.junction(jid, self.netid[nd], x, y)
                anchor[k], kind[k] = f.jn(jid), "j"
            elif on:
                anchor[k], kind[k] = f.term(*on[0]), "t"
            else:
                anchor[k], kind[k] = None, "corner"
        for k in keys:
            if anchor[k] is None:
                continue
            for v, t in sorted(groups[k]):
                if kind[k] == "t" and v == c:
                    continue
                rid = "r-%s-%s%s" % (nd, t[0].lower(), t[1].lower())
                pts = [xy(k, c), xy(k, v)]
                steps = []
                k2 = self._cross_detour(nd, axis, k, v, c)
                if k2 is not None:
                    mid = [xy(k2, c), xy(k2, v)]
                    steps = [("bend", q[0], q[1]) for q in mid]
                    pts = pts[:1] + mid + pts[1:]
                f.route(rid, self.netid[nd], anchor[k],
                        steps + [("to", f.term(*t))])
                self._note_legs(rid, pts)
        for i in range(len(keys) - 1):
            k0, k1 = keys[i], keys[i + 1]
            rid = "r-%s-bus%d" % (nd, i)
            pts = [xy(k0, c), xy(k1, c)]
            if anchor[k0] is None:
                v0, t0 = sorted(groups[k0])[0]
                start = f.term(*t0)
                pre = []
                k2 = self._cross_detour(nd, axis, k0, v0, c)
                if k2 is not None:
                    pre = [xy(k2, v0), xy(k2, c)]
                bx, by = xy(k0, c)
                steps = [("bend", q[0], q[1]) for q in pre] + [
                    ("bend", bx, by)]
                pts = [xy(k0, v0)] + pre + pts
            else:
                start, steps = anchor[k0], []
            if anchor[k1] is None:
                v1, t1 = sorted(groups[k1])[0]
                post = []
                k2 = self._cross_detour(nd, axis, k1, v1, c)
                if k2 is not None:
                    post = [xy(k2, c), xy(k2, v1)]
                bx, by = xy(k1, c)
                steps += [("bend", bx, by)] + [
                    ("bend", q[0], q[1]) for q in post] + [
                    ("to", f.term(*t1))]
                pts = pts + post + [xy(k1, v1)]
                jog = self._bus_detour(nd, axis, c, k0, k1)
                if jog:
                    c2, e = jog
                    mid = [xy(k0 + e, c), xy(k0 + e, c2),
                           xy(k1 - e, c2), xy(k1 - e, c)]
                    steps = [("bend", q[0], q[1]) for q in mid] + steps
                    pts = pts[:1] + mid + pts[1:]
            else:
                jog = self._bus_detour(nd, axis, c, k0, k1)
                if jog:
                    c2, e = jog
                    mid = [xy(k0 + e, c), xy(k0 + e, c2),
                           xy(k1 - e, c2), xy(k1 - e, c)]
                    steps += [("bend", q[0], q[1]) for q in mid]
                    pts = pts[:-1] + mid + pts[-1:]
                steps += [("to", anchor[k1])]
            f.route(rid, self.netid[nd], start, steps)
            self._note_legs(rid, pts)
            self.long_haul.add(rid)

    def _nudge_ports(self):
        """A port is a leaf: if anything grazes it, push it one grid step
        further out.  Its route is anchored to the pin, so the wire simply
        gets longer -- nothing else has to move.

        "Anything" includes the port's NAME.  A port label has exactly one
        legal spot beside its circle (user, 2026-09-02: "都上浮了，對整齊"),
        so when it lands on a wire or on top of a part, the label cannot
        move -- the port has to.  That is the same ruling as "放不進去就把
        電路拉開", applied to the one thing that is free to slide.
        """
        f = self.f
        for nd, (pid, nm, di) in self.ports_placed.items():
            step = -10 if di == "input" else 10
            axis = self.trunk.get(nd, ("h", 0))[0]
            ci = 1 if axis == "h" else 0
            others = [t for t in self.netterms[nd]
                      if t in self.pinxy and t[0] != pid]

            def clear():
                """How close the port and its NAME come to anything else."""
                box = f.ink(pid)
                _sid, px, py, mir, _rot = f.placed[pid]
                dx = LABEL_PORT if mir == "x" else -LABEL_PORT
                lb = label_box(name(nm), px + dx, py + 5,
                               "start" if dx > 0 else "end")
                lab = str(self.opt("portnudge", "label")) == "label"
                worst = 999
                ix = (box[0] + 1, box[1] + 1, box[2] - 1, box[3] - 1)
                for rid, x0, y0, x1, y1 in f.segments():
                    seg = (x0, y0, x1, y1)
                    net = next((r["netId"] for r in f.routes
                                if r["id"] == rid), None)
                    if net != self.netid[nd]:
                        worst = min(worst, _box_gap(box, seg))
                    elif (min(x0, x1) < ix[2] and max(x0, x1) > ix[0]
                          and min(y0, y1) < ix[3] and max(y0, y1) > ix[1]):
                        # its OWN wire may touch the pin, never cross the
                        # circle -- flipping the port to the side the wire
                        # comes from does exactly that
                        return -1
                    if lab:
                        worst = min(worst, _box_gap(lb, seg))
                if lab:
                    for iid in f.placed:
                        if iid == pid:
                            continue
                        worst = min(worst, _box_gap_box(lb, f.ink(iid)))
                return worst

            def move(nx, ny, nmir=None):
                sid, x, y, mir, rot = f.placed[pid]
                nmir = mir if nmir is None else nmir
                for i in f.instances:
                    if i["id"] == pid:
                        i["placement"]["position"] = {"x": nx, "y": ny}
                        i["placement"]["mirror"] = nmir
                f.placed[pid] = (sid, nx, ny, nmir, rot)
                self.pinxy[(pid, "P")] = f.pin(pid, "P")
                return (sid, x, y, mir, rot)

            # Enumerate where the port may legally sit and take the best.
            #  * flipping puts the CIRCLE on the other side of its own pin.
            #    The pin does not move, so every route stays exactly where
            #    it is -- only the circle and the name (pinned to it) swap.
            #    That is what rescues a gate port whose name sat on the
            #    transistor (Fig 10.35(a)'s V_in2 over M4).
            #  * sliding moves the pin too, so it is only offered when the
            #    stub stays straight.
            sid0, x0, y0, mir0, rot0 = f.placed[pid]
            px0, _py0 = self.pinxy[(pid, "P")]
            cands = [(x0, y0, mir0)]
            fmir = "none" if mir0 == "x" else "x"
            cands.append((px0 - 10 if fmir == "none" else px0 + 10,
                          y0, fmir))
            # a port sitting exactly on a device pin is CONNECTED by that
            # coincidence and draws no wire at all (SOP 3F).  Sliding it
            # away invents a wire, and that wire then has to get back past
            # whatever is in between (Fig 10.35(a): V_in2 slid off M4's gate
            # and its new bus ran through M2 and through its own circle).
            onpin = any(self.pinxy[t] == self.pinxy[(pid, "P")]
                        for t in others)
            slide = not onpin and not self._has_bend(pid) and not (
                len(others) == 1
                and self.pinxy[others[0]][ci] != self.pinxy[(pid, "P")][ci])
            if slide:
                for k in (1, 2, 3):
                    for bx, by, bm in list(cands):
                        cands.append((bx + step * k, by, bm) if axis == "h"
                                     else (bx, by + step * k, bm))
            best, bestk = None, None
            for cx, cy, cm in cands:
                move(cx, cy, cm)
                g = clear()
                # enough clearance is enough: past 12 units, prefer the
                # placement that moved least, or the port drifts off into
                # the margin and drags its wire with it
                disp = abs(cx - x0) + abs(cy - y0) + (0 if cm == mir0 else 5)
                k = (min(g, 12), -disp, g)
                if bestk is None or k > bestk:
                    best, bestk = (cx, cy, cm), k
            move(*best)

    def _has_bend(self, iid):
        """Does any route touching this instance carry a hand-placed bend?
        Those bends are absolute coordinates, so moving the instance would
        leave a diagonal behind."""
        for r in self.f.routes:
            touches = (r["start"].get("instanceId") == iid)
            bend = False
            for lg in r["legs"]:
                to = lg["to"]
                if to["kind"] == "bend":
                    bend = True
                elif to.get("endpoint", {}).get("instanceId") == iid:
                    touches = True
            if touches and bend:
                return True
        return False

    # ----------------------------------------------------------- annotation
    def _label_candidates(self, iid, sym):
        """Canonical spot first, then the smallest departures from it.

        SOP 3A puts a label at "the ink edge on the D/S side plus 8" and
        leaves it there; lane 1 never moves it.  The search is only here to
        break a genuine collision, so the ladder is short and ordered by how
        far it strays -- an unordered 12-candidate search scattered the
        labels all over the figure (user, 2026-09-02).
        """
        dx = LBL_DX.get(sym, 13)
        half = self.f.ink(iid)
        cy = self.f.placed[iid][2]
        hi = max(abs(half[1] - cy), abs(half[3] - cy))
        mir = self.f.placed[iid][3]
        # the canonical side: away from the gate, i.e. the side the ink is on
        first = -dx if mir == "x" and sym in CTRL else dx
        # every candidate stays within `dx` of the device: the label may
        # move UP or DOWN beside it, never away from it
        if sym in CTRL:
            # A transistor's name goes at its OPENING -- the side away from
            # the gate, where the drain/source leads are -- at the fixed
            # SOP 3A distance, and it does not move.  If it does not fit,
            # the layout gets spread (the retry widens the columns), not the
            # label (user, 2026-09-02).
            return [(first, 5, "start" if first > 0 else "end")]
        out = []
        if sym in N.BLOCKS:
            # a block's name belongs INSIDE the triangle, as the textbook
            # prints it -- not out on the sloping edge
            out.append((-10, 6, "middle"))
        for sx in (first, -first):
            al = "start" if sx > 0 else "end"
            for ddy in (5, -14, 24):
                out.append((sx, ddy, al))
        out.insert(2, (0, dy_above(hi), "middle"))
        out.insert(3, (0, dy_below(hi), "middle"))
        # only if every tight spot collides: step further out.  These are the
        # last entries so the early-exit never reaches them unless it must.
        for k in (1, 2):
            for sx in (first, -first):
                out.append((sx + 12 * k * (1 if sx > 0 else -1), 5,
                            "start" if sx > 0 else "end"))
        return out

    def _score_label(self, iid, rt, dx, dy, align, placed=()):
        """How safe is this spot?  (wire gap, neighbour gap) -- both bigger
        is better, and the audit needs wire >= 2 and neighbour >= 17."""
        f = self.f
        x, y = f.placed[iid][1] + dx, f.placed[iid][2] + dy
        box = label_box(rt, x, y, align)
        wire = min([_box_gap(box, s[1:]) for s in f.segments()] or [999])
        kind = f.placed[iid][0]
        near = 999
        for jid in f.placed:
            if jid == iid or f.placed[jid][0] != kind:
                continue
            b = f.ink(jid)
            if align in ("start", "end") and (b[1] > box[3] or b[3] < box[1]):
                continue
            near = min(near, _box_gap_box(box, b))
        own = _box_gap_box(box, f.ink(iid))
        other = min([_box_gap_box(box, b) for b in placed] or [999])
        # `near` only looks at the SAME kind of part, because that is what
        # makes a name ambiguous.  But a label sitting on top of any other
        # body is simply unreadable, so that gets its own term.
        anyink = min([_box_gap_box(box, f.ink(j)) for j in f.placed
                      if j != iid] or [999])
        return wire, near, own, other, anyink

    def annotate(self):
        f = self.f
        self._lbox = []
        for nd, (pid, nm, di) in self.ports_placed.items():
            rt = name(nm)
            # A pin's name sits beside its CIRCLE, at the fixed SOP 3A
            # distance, on the row of the pin -- one position, no search.
            # Letting it hunt for clearance left the labels floating at
            # different heights (user, 2026-09-02: "都上浮了，對整齊").
            mir = f.placed[pid][3]
            dx = LABEL_PORT if mir == "x" else -LABEL_PORT
            cands = [(dx, 5, "start" if dx > 0 else "end")]
            best, bestkey = None, None
            for dx, dy, al in cands:
                wire, near, own, other, anyink = self._score_label(
                    pid, rt, dx, dy, al, self._lbox)
                ok = (2 if wire >= LABEL_INK_GAP else 1 if wire >= 2.0
                      else 0) + (1 if near >= NEIGHBOUR_GAP else 0) + (
                    2 if other >= LABEL_INK_GAP else 0) + (
                    2 if anyink >= LABEL_INK_GAP else 0)
                key = (ok, min(wire, 40), min(anyink, 30), min(near, 60),
                       min(other, 40))
                if bestkey is None or key > bestkey:
                    best, bestkey = (dx, dy, al), key
            f.port_label(pid, "t-" + nd, best[0], best[1], best[2])
            self._lbox.append(label_box(rt, f.placed[pid][1] + best[0],
                                        f.placed[pid][2] + best[1], best[2]))
        for d in self.c.devices:
            if d.ref not in f.placed:
                continue
            rt = name(d.label)
            best, bestkey = None, None
            for dx, dy, al in self._label_candidates(d.ref, d.sym):
                wire, near, own, other, anyink = self._score_label(
                    d.ref, rt, dx, dy, al, self._lbox)
                if (wire >= 2.0 and anyink >= 2.0 and other >= 2.0
                        and near >= NEIGHBOUR_GAP
                        and near >= 2.0 * own):
                    best = (dx, dy, al)       # good enough: stop straying
                    break
                ok = (2 if wire >= LABEL_INK_GAP else 1 if wire >= 2.0
                      else 0) + (
                    2 if (near >= NEIGHBOUR_GAP and near >= 2.0 * own) else 0
                ) + (2 if other >= LABEL_INK_GAP else 0) + (
                    2 if anyink >= LABEL_INK_GAP else 0)
                key = (ok, min(wire, 40), min(anyink, 30), min(near, 60),
                       min(other, 40), -abs(dx))
                if bestkey is None or key > bestkey:
                    best, bestkey = (dx, dy, al), key
            f.inst_label(d.ref, best[0], best[1], best[2])
            self._lbox.append(label_box(rt, f.placed[d.ref][1] + best[0],
                                        f.placed[d.ref][2] + best[1], best[2]))
        for nd in self.c.show:
            if nd not in self.trunk:
                continue
            axis, c = self.trunk[nd]
            pts = [self.pinxy[t] for t in self.netterms.get(nd, [])
                   if t in self.pinxy]
            if not pts:
                continue
            rt = name(nd.upper() if len(nd) == 1 else nd)
            lo = min(p[0] for p in pts), min(p[1] for p in pts)
            hi = max(p[0] for p in pts), max(p[1] for p in pts)
            cands = []
            if axis == "h":
                for x in (lo[0], (lo[0] + hi[0]) // 2, hi[0]):
                    cands += [(x - 12, c - 8, "end"), (x + 12, c - 8, "start"),
                              (x - 12, c + 20, "end"), (x + 12, c + 20,
                                                        "start")]
            else:
                for y in (lo[1], (lo[1] + hi[1]) // 2, hi[1]):
                    cands += [(c - 12, y - 8, "end"), (c + 12, y - 8, "start"),
                              (c - 12, y + 20, "end"), (c + 12, y + 20,
                                                        "start")]
            best, bestkey = cands[0], None
            for x, y, al in cands:
                box = label_box(rt, x, y, al)
                wire = min([_box_gap(box, sg[1:])
                            for sg in f.segments()] or [999])
                ink = min([_box_gap_box(box, f.ink(i))
                           for i in f.placed] or [999])
                other = min([_box_gap_box(box, b)
                             for b in self._lbox] or [999])
                key = ((2 if wire >= LABEL_INK_GAP else 1 if wire >= 2
                        else 0) + (2 if other >= LABEL_INK_GAP else 0)
                       + (2 if ink >= LABEL_INK_GAP else 0),
                       min(wire, 30), min(other, 30), min(ink, 30))
                if bestkey is None or key > bestkey:
                    best, bestkey = (x, y, al), key
            f.text("n-" + nd, best[0], best[1], best[2], rt)
            self._lbox.append(label_box(rt, best[0], best[1], best[2]))

    # ---------------------------------------------------------------- drive
    def run(self, verbose=True):
        self.orient()
        self.levels()
        self.columns()
        self.place_all()
        self.wire()
        self._nudge_ports()
        self.annotate()
        xs, ys = [], []
        for iid in self.f.placed:
            b = self.f.ink(iid)
            xs += [b[0], b[2]]
            ys += [b[1], b[3]]
        for j in self.f.junctions:
            xs.append(j["position"]["x"])
            ys.append(j["position"]["y"])
        # a label outside the ink box is still part of the picture
        for lid, rt, lx, ly, al, _own in self.f.label_records():
            b = label_box(rt, lx, ly, al)
            xs += [b[0], b[2]]
            ys += [b[1], b[3]]
        vb = (int(min(xs) - 20), int(min(ys) - 20),
              int(max(xs) - min(xs) + 40), int(max(ys) - min(ys) + 40))
        # the netlist lane evaluates candidate layouts that still have audit
        # errors -- the search reads those counts, so build must REPORT rather
        # than raise.  Upstream's strict gate stays on for the hand-drawn 29.
        return self.f.build(strict=False, long_haul=self.long_haul,
                            rail_ends=self.rail_ends,
                            viewbox=vb, extra_evidence=None
                            if self.c.globals else [],
                            verbose=verbose,
                            expect_differ=self._plain_labels())

    def _plain_labels(self):
        """Names the editor's own generator would subscript but the page
        does not: the rail label, and any port whose name is a bare word
        (`Vout`, `CK`) rather than base plus subscript."""
        out = set()
        for _nd, (pid, nm, _di) in self.ports_placed.items():
            if "_" not in nm and len(nm) > 1:
                out.add("instance-label-" + pid)
        return out


AUDIT_KEYS = ("self-check errors:", "audits:")


def _audit_count(log):
    n = 0
    for line in log.splitlines():
        if line.startswith("self-check errors:"):
            n += int(line.split(":")[1])
        if line.startswith("audits:"):
            for part in line.split("audits:")[1].split("(")[0].split("|"):
                n += int(part.split()[1])
    return n


def _cross_from(log):
    for line in log.splitlines():
        if "crossings" in line:
            try:
                return int(line.split("crossings")[1].split()[0])
            except (IndexError, ValueError):
                pass
    return 0


# The discrete choices the pipeline used to hard-code.  Each one changes an
# EARLY decision -- which parts lie down, which ride a track, how the trunk
# cost is ordered -- and an early decision cannot be repaired downstream, so
# the only honest way to pick is to draw the figure both ways and score it.
STYLE_AXES = (("sigpath", (1, 0)),
              ("spans", (1, 0)),
              ("cost", ("hbRwo", "hbrwo", "hbxrwo", "hbrxwo")),
              ("anchor", (1, 0, "lat", "tight")),
              ("sccorder", ("decl", "ctrl")),
              ("levels", ("asap", "alap")),
              ("colorder", ("decl", "bary")),
              ("compact", (0, 1)),
              ("freecol", ("own", "share")),
              ("portnudge", ("label", "pin")),
              ("bodycost", ("soft", "hard")))
STYLE0 = {"sigpath": "rail", "spans": 1, "cost": "hbRwo", "anchor": 1,
          "sccorder": "decl", "levels": "asap", "colorder": "decl", "compact": 0, "freecol": "own",
          "portnudge": "label", "bodycost": "soft"}


def _grids(tune):
    out = [(COL_PITCH, 60, 20)]
    if tune:
        # "It does not fit" is a real answer, and widening is what a person
        # does by hand.  A transistor's name has exactly one legal spot
        # (SOP 3A), so a label that will not fit means a wider drawing.
        for pitch in (80, 90, 100, 110, 120, 140, 160, 180, 200):
            for rowgap in (60, 70, 80, 100):
                out.append((pitch, rowgap, 30))
    return out


def place_deck(path, out_proj=None, out_svg=None, verbose=True, tune=True):
    """Draw the deck, searching the layout choices instead of guessing them.

    Two things are being chosen: HOW to draw (which parts lie down, which
    ride a feedback track, how the trunk cost is ordered, whether branches
    hug their anchor) and HOW MUCH ROOM to use (column pitch, row gap, port
    stub).  Both used to be fixed by hand -- one rule per rejection -- and
    each new rule reshuffled all 23 training figures because it changes a
    decision the later stages cannot undo.

    So: coordinate descent.  Sweep one axis at a time, keep whatever scores
    best, repeat.  The score is lexicographic
    `(audit errors, crossings, total wire)`: nothing illegal, then as few
    unconnected crossings as the drawing can manage, then the shortest wire
    -- the three numbers that already decide whether a figure is clean.
    """
    c = N.parse(open(path, encoding="utf-8").read())
    stem = os.path.basename(path)[:-4]
    out_proj = out_proj or os.path.join(HERE, "auto", stem + ".icproj.json")
    out_svg = out_svg or os.path.join(HERE, "auto", "preview_" + stem + ".svg")
    d = os.path.dirname(out_proj)
    if d and not os.path.isdir(d):
        os.makedirs(d)

    tried = {}

    def score(grid, style):
        key = (grid, tuple(sorted(style.items())))
        if key in tried:
            return tried[key]
        buf = io.StringIO()
        p = Placer(c, out_proj, out_svg, pitch=grid[0], rowgap=grid[1],
                   portstub=grid[2], style=style)
        try:
            with contextlib.redirect_stdout(buf):
                p.run(verbose=True)
            log = buf.getvalue()
            wire = sum(abs(x1 - x0) + abs(y1 - y0)
                       for _rid, x0, y0, x1, y1 in p.f.segments())
            # every corner is a place the eye has to follow the wire round,
            # so a drawing full of jogs reads as "太繞" even when the total
            # length is fine (user, 2026-09-02)
            bends = sum(max(0, len(r["legs"]) - 1) for r in p.f.routes)
            # crossings and wire trade against each other, so they share
            # one number: ranking crossings strictly above wire buys one
            # crossing with several hundred units of extra wire (measured).
            # measured over the 23-figure bench: 10 -> wire 1.31x but 24
            # crossings, 20 -> 1.35x/22, 40 -> 1.37x/22 and one more figure
            # fully clean.  Clean figures are the gate, so 40.
            xw = int(os.environ.get("AC_XW", "40"))
            # measured on the 21-figure bench: 0 -> bends 1.18x,
            # 10 -> 1.11x, 25 -> 1.01x, 60 -> 1.00x and place back to 39%.
            # 60 puts the corner count at the hand-drawn level for one
            # extra crossing across the whole library.
            bw = int(os.environ.get("AC_BW", "60"))
            out = (_audit_count(log),
                   _cross_from(log) * xw + wire // 10 + bends * bw, wire)
        except Exception:                      # a style that cannot be drawn
            out = (999, 999, 10 ** 9)          # scores itself out
        tried[key] = out
        return out

    fast = os.environ.get("AC_FAST")
    os.environ["AC_FAST"] = "1"
    try:
        style, grid = dict(STYLE0), (COL_PITCH, 60, 20)
        best = score(grid, style)
        grids = _grids(tune)
        # descend until a whole pass changes nothing.  Every point is
        # memoised, so a pass that re-walks ground already covered is free.
        for _round in range(4):
            moved = False
            for axis, vals in STYLE_AXES:
                for v in vals:
                    if v == style[axis]:
                        continue
                    cand = dict(style, **{axis: v})
                    sc = score(grid, cand)
                    if sc < best:
                        best, style, moved = sc, cand, True
            for g in grids:
                if g == grid:
                    continue
                sc = score(g, style)
                if sc < best:
                    best, grid, moved = sc, g, True
            if not moved:
                break
        # A transistor is free to face either way, and turning one round is
        # the cheapest way to take a crossing out of the picture (user,
        # 2026-09-02: "MOS 鏡像可以降低很多交叉點").  The gate-side rule
        # inside the placer only knows wire length, so the decision is made
        # again HERE, against the real score -- crossings included.
        buf = io.StringIO()
        probe = Placer(c, out_proj, out_svg, pitch=grid[0], rowgap=grid[1],
                       portstub=grid[2], style=style)
        try:
            with contextlib.redirect_stdout(buf):
                probe.run(verbose=True)
            refs = [(iid, pl[3]) for iid, pl in probe.f.placed.items()
                    if pl[0] in CTRL]
        except Exception:
            refs = []
        # one probe per transistor: try it the OTHER way round and keep the
        # flip if the score drops.  Trying both values twice over cost four
        # runs each and the extra three never found anything.
        formir = {}
        for ref, cur in refs:
            m = "x" if cur != "x" else "none"
            cand = dict(formir)
            cand[ref] = m
            st = dict(style)
            st["formir"] = tuple(sorted(cand.items()))
            sc = score(grid, st)
            if sc < best:
                best, formir = sc, cand
        if formir:
            style = dict(style)
            style["formir"] = tuple(sorted(formir.items()))
    finally:
        if fast is None:
            os.environ.pop("AC_FAST", None)
        else:
            os.environ["AC_FAST"] = fast
    p = Placer(c, out_proj, out_svg, pitch=grid[0], rowgap=grid[1],
               portstub=grid[2], style=style)
    p.run(verbose=verbose)
    if verbose:
        print("  search: %d layouts tried | %s | pitch %d row %d stub %d"
              % (len(tried), " ".join("%s=%s" % kv
                                      for kv in sorted(style.items())),
                 grid[0], grid[1], grid[2]))
    return p


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    place_deck(args[0])
