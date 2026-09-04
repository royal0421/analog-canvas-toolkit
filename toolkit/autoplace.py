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
        self.dvdd = {}
        if sup:
            dv = self._bfs(g, sup)
            self.dvdd = {n: dv.get(n, BIG) for n in g}
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
            # NB "same distance from the SUPPLY" was tried as a second way
            # to spell "same level" (Razavi Fig 7.47 lays R_P down between
            # two branches that hang off V_DD at equal depth).  It turned
            # R_P horizontal but the placer then had nowhere to put it and
            # the figure gained a crossing -- reverted; orientation alone is
            # not worth a crossing (user, 2026-09-03).
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
        # A multi-stage figure is drawn STAGE BY STAGE (user, 2026-09-03:
        # "這張明顯是有多stage的圖形，如果是多stage的，你就要強制分割
        # 一個stage一個stage畫").
        #
        # Every ordering constraint can hold globally and the stages still
        # interleave, because nothing says a stage has to be CONTIGUOUS.
        # Fig 14.36(b) put OA2 at x=280 while OA1's own input node sat at
        # x=180 and OA1 itself at x=540: legal (the block is between its
        # input and its output) and unreadable, because the input then had
        # to travel underneath the whole of the second stage to reach its
        # own op-amp.  Here each block claims its output node and any input
        # node that is not another block's output, and the claimed slots are
        # gathered at the position where the stage first appears.
        # Not a style axis: the split is the SKELETON of a multi-stage
        # figure and it outranks crossings and bends (user,
        # 2026-09-03: "Stage分割優先度是不是放在優化交叉點和彎折點上
        # 會比較好" -- yes).  Weighed against them it always lost,
        # because splitting costs a crossing before the later moves
        # get a chance to take it back.  Split first, then let the
        # grid / swaps / flips minimise inside that structure.
        if len(self.blocks) > 1:
            produced = set()
            for d in self.blocks:
                produced |= set(nvars(d.pins[N.BLOCKS[d.sym][-1]]))
            stage_of = {}
            for d in self.blocks:
                pins = N.BLOCKS[d.sym]
                stage_of[("b", d.ref)] = d.ref
                for u in nvars(d.pins[pins[-1]]):
                    stage_of.setdefault(u, d.ref)
                for p in pins[:-1]:
                    for u in nvars(d.pins[p]):
                        if u not in produced:
                            stage_of.setdefault(u, d.ref)
            seq, held = [], {}
            for k in order_all:
                s = stage_of.get(k)
                if s is None:
                    seq.append((None, k))
                elif s in held:
                    held[s].append(k)
                else:
                    held[s] = [k]
                    seq.append((s, None))
            regrouped = []
            for s, k in seq:
                regrouped += held[s] if s is not None else [k]
            order_all = regrouped
            # ...and the input node comes before every stage.  Gathering the
            # stages can leave the input's own column to the RIGHT of stage
            # one, and then the series resistor that feeds the first op-amp
            # doubles back to reach it (user, 2026-09-03: "如果stage1在最左,
            # 應該要符合vin port在最左的規則").  Putting the port beside its
            # own pin fixes the stub length, not the column order -- both
            # have to hold.
            feed = set()
            for nd2, _nm2, di2 in self.c.ports:
                if di2 == "input":
                    feed |= set(nvars(nd2))
            head = [k for k in order_all if k in feed]
            if head:
                order_all = head + [k for k in order_all if k not in head]
            self._stage_of = stage_of
            # Which stage is first, second, third -- and which NODE belongs
            # to which stage.  Feedback cannot be classified without this:
            # "is this part carrying the signal on to the next stage, or
            # taking it back to an earlier one" is a question about stage
            # numbers, not about how far the part reaches (user, 2026-09-03:
            # "把stage分割，哪些是回授路徑，納入你的畫電路思考").
            self._stage_idx, i = {}, 0
            for s, _k in seq:
                if s is not None:
                    self._stage_idx[s] = i
                    i += 1
            self._produced = set()
            self._stage_node = {}
            for d in self.blocks:
                pins = N.BLOCKS[d.sym]
                out = d.pins[pins[-1]]
                self._produced.add(out)
                self._stage_node[out] = d.ref
            for d in self.blocks:
                for p in N.BLOCKS[d.sym][:-1]:
                    n = d.pins[p]
                    if n not in self._produced:
                        self._stage_node.setdefault(n, d.ref)
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
        # Swapping two neighbouring columns is a layout move like turning a
        # transistor over, and it is the one that actually removes crossings.
        # The search hands the swaps down here (user, 2026-09-03: the run
        # itself should be minimising bends and crossings, not me afterwards).
        # ...but a swap may not carry a slot ACROSS a stage boundary: the
        # whole point of drawing stage by stage is that the stages stay
        # contiguous, and a search that is free to interleave them again
        # undoes the split it was just given (Fig 14.36(b): the stage order
        # came out right and six colmoves shuffled it back).
        stg = getattr(self, "_stage_of", None)

        def same_stage(a, b):
            return not stg or stg.get(a) == stg.get(b)

        for i, j in (self.opt("colswap", ()) or ()):
            if (0 <= i < len(seq) and 0 <= j < len(seq)
                    and same_stage(seq[i], seq[j])):
                seq[i], seq[j] = seq[j], seq[i]
        # ...and a whole branch may be lifted out and dropped somewhere else
        # entirely.  Swapping neighbours cannot reach "this column belongs
        # three places over", which is what Fig 3.57 and 15.32(b) needed.
        for i, j in (self.opt("colmove", ()) or ()):
            if (0 <= i < len(seq) and 0 <= j < len(seq)
                    and same_stage(seq[i], seq[j])):
                seq.insert(j, seq.pop(i))
        self.ncols = len(seq)
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
        # With the stages known, a part's track is decided by WHERE IT GOES,
        # not by how far it reaches.  Razavi's 14.36(b):
        #   R_4, R_1, R_2   stage i out -> stage i+1 in   feed-forward, main row
        #   R_6, C_1, C_2   stage i out -> stage i in      local, one layer up
        #   R_5 (1 stage), R_3 (2 stages) back to an earlier input
        #                                                  layer = 1 + stages
        # Sorting by span put R_1 and R_2 -- plain feed-forward -- up on the
        # tracks, which is why the middle of the figure filled with parallel
        # horizontals that had nothing to do with feedback.
        sidx = getattr(self, "_stage_idx", None)
        if sidx and len(self.blocks) > 1:
            snode = self._stage_node
            produced = self._produced

            def track_of(d):
                ns = list(d.pins.values())
                if len(ns) != 2 or ns[0] == ns[1]:
                    return None
                src = [n for n in ns if n in produced]
                if len(src) != 1:
                    return None
                s = src[0]
                t = ns[1] if ns[0] == s else ns[0]
                si, ti = sidx.get(snode.get(s)), sidx.get(snode.get(t))
                if si is None or ti is None:
                    return None
                if ti == si + 1:
                    return 0                  # feed-forward: stays on the row
                if ti == si:
                    return 1                  # its own stage's feedback
                return 1 + abs(si - ti)       # reaches back (or skips) further

            picked = {}
            for d in self.horiz:
                lv = track_of(d)
                if lv:
                    picked[d.ref] = lv
            if picked:
                fb = [d for d in self.horiz if d.ref in picked]
                self.fb_track = picked
        # Which side each feedback part rides is chosen ONE PART AT A TIME by
        # the search (`fbside`), not by a global rule.  Razavi runs R_3/R_6
        # above and R_5 below in 14.36(b) -- he picks per part, and dealing
        # them out by span alternately (tried 2026-09-03) was measurably
        # worse because it broke the nesting of the spans that stay up.
        self.fb_side = dict(self.opt("fbside", ()) or ())
        # NB dealing the feedback parts out to an UPPER and a LOWER track was
        # tried and reverted (2026-09-03).  Razavi runs R_3/R_6 above and
        # R_5 below in 14.36(b), but he picks which one goes under; dealing
        # them out alternately breaks the nesting that makes a one-sided
        # tower readable, and every leg on the lower side then has to reach
        # past the circuit.  Measured on 14.36(b): floor-anchored 4
        # crossings, own-row 7, one-sided 0.  8.48 and 8.55 saw no change.
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
        if d.sym in ("diode", "zener-diode"):
            # the diode symbol is drawn HORIZONTALLY (pins at +/-20 in x),
            # so standing it up is 90 or 270 -- not 0/180.  Flipping it with
            # 180 left it lying down and the net's bus had to detour round
            # its body (Fig 3.57's D_1).
            rot = 90 if d.top == "A" else 270
        elif d.sym in SYMM_VERT and d.top != SYMM_VERT[d.sym][0]:
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
            if self.fb_side.get(d.ref, 1) < 0:
                # below: hang under the part's own row, deepest span lowest
                cy += 40 * self.fb_track[d.ref]
            else:
                cy -= 40 * self.fb_track[d.ref]
        # the search may move a lying-down part up or down a row: two parts
        # of one net landing on different rows is what makes the net loop
        # round (Fig 3.57's C_1 and D_2)
        cy += dict(self.opt("latrow", ()) or ()).get(d.ref, 0)
        if x1 is None or x2 is None or x1 == x2:
            base = x1 if x1 is not None else (x2 if x2 is not None else X0)
            # the diode symbol is drawn horizontal already, so 0 lies it
            # down and 90 would stand it up -- the same exception the
            # two-column branch below makes.  Missing it here is why Fig
            # 3.57's D_2 stood up: its two nodes share a column, so it
            # never reached the branch that knew about diodes.
            cx, rot = (base + self.pitch / 2.0,
                       0 if d.sym in ("diode", "zener-diode") else 90)
        else:
            cx = (x1 + x2) / 2.0
            # rotation 90 puts the symbol's pin 1 on the right, 270 puts
            # pin 2 there.  Comparing the (already swapped) x values instead
            # always chose 90, so a part declared "R vin a" came out with
            # v_in on the RIGHT and its wire doubled back round the body
            # (Razavi Fig 5.43's R_B).
            if d.sym in ("diode", "zener-diode"):
                # the diode symbol is already horizontal, so 0 and 180 are
                # the lying-down rotations and 90/270 would stand it up --
                # the opposite of every other two-terminal part
                rot = 0 if rightpin != first else 180
            else:
                rot = 90 if rightpin == first else 270
        cx = int(round(cx / 10.0)) * 10
        half = span_of(d.sym) / 2 + 10
        cx = self._clear_x(d, cx, cy, half)
        # a lying-down part that will not fit on its row goes UP first --
        # the book keeps bridges and feedback above the devices they span
        # (Razavi Fig 7.47's R_P) and only the main row runs below
        step = -40 if str(self.opt("latup", "1")) == "1" else 40
        tries = 0
        while self._collides(d, cx, int(cy)):
            cy += step
            tries += 1
            if tries == 4 and step < 0:
                cy += 40 * (tries + 1)      # give up on going up
                step = 40
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
        # NB pulling the rest of a column onto the MOS line (a MOS sits 10
        # off its column line) was tried 2026-09-04 and reverted: it moved
        # every non-MOS part in the library and cost place 34%->23%, col
        # 47%->34%, bends 1.32x->1.38x.  9.83's I_REF is not that case
        # anyway -- it is 30 from M_REF, i.e. a different COLUMN.
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
            # `rot or default` was wrong: 0 is a REAL rotation for a diode
            # (the symbol is born horizontal, so 0 is anode-left) and it is
            # exactly the one a lying-down diode asks for.  Being falsy, it
            # was silently replaced by the standing-up default, which is why
            # Fig 3.57's D_2 kept standing however the placer was fixed.
            f.place(d.ref, "diode", cx, cy,
                    rotation=(rot if rot is not None
                              else (90 if d.top == "A" else 270)),
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
                    self.trunk[nd] = ("h", self.ynode[nd], None)
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
            first, ldy, lal = self._ctrl_label_at(iid, sym, mir)
            box = label_box(name(d.label), x + first, y + ldy, lal)
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
        # which way each pin faces: the trunk cost needs it to tell a pin
        # the wire can enter straight from a pin it has to turn on
        # only a transistor's GATE/BASE pin earns the pass-through
        # exemption; an op-amp input must never let a net cross the triangle
        self._pinowner = {}
        for (iid, pn), xy in self.pinxy.items():
            sid = self.f.placed.get(iid, (None,))[0]
            if CTRL.get(sid) == pn:
                self._pinowner.setdefault(xy, set()).add(iid)
        self._pindir = {}
        for (iid, pn), xy in self.pinxy.items():
            try:
                d = self.f.pin_dir(iid, pn)
            except KeyError:
                continue
            if d:
                self._pindir.setdefault(xy, set()).add("H" if d[0] else "V")
        # which net each pin belongs to: a trunk or a riser that runs OVER a
        # foreign pin draws a connection that does not exist
        self._pinnet = {}
        for nd2 in self.c.nodes():
            for t in self.netterms.get(nd2, []):
                if t in self.pinxy:
                    self._pinnet.setdefault(self.pinxy[t], set()).add(nd2)
        taken += self._power_segments()
        self._inks = inks
        self._member = member
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
                    cands.append((key + (bias, abs(off)), axis, c, None))
                    if key == (0, 0, 0, 0) and bias == 0:
                        break
                else:
                    continue
                break
            if self.opt("ltrunk", 1):
                def _sc(ax, cc, sp, _nd=nd, _pts=pts):
                    return self._trunk_cost(_nd, ax, cc, _pts, taken, inks,
                                            member, sp)
                for axis, c, spur, key in self._spur_search(nd, pts, _sc):
                    bias = 0 if (axis == "h") == (w >= h) else 1
                    cands.append((key + (bias, 0), axis, c, spur))
            # a plain trunk wins an exact tie: the L has to EARN its elbow
            cands.sort(key=lambda t: (t[0], t[1], t[2], t[3] is not None))
            _k, axis, c, spur = cands[0]
            self.trunk[nd] = (axis, c, spur)
            if os.environ.get("AC_TRUNKDBG"):
                # what the corner-minimal choice would have been, and why it
                # lost: `n` is the corner count, `h` the hard blockers
                order = self.opt("cost", "hbRwo")
                ni = order.find("n")
                if ni >= 0:
                    bestn = min(cands, key=lambda t: (t[0][ni], t[0][0]))
                    print("      TRUNK %-6s chose %s c=%-4d cost=%s | "
                          "corner-min %s c=%-4d cost=%s"
                          % (nd, axis, c, _k[:len(order)],
                             bestn[1], bestn[2], bestn[0][:len(order)]))
            if axis == "h":
                self.bus_y[nd] = c
            taken += [(nd,) + sg[1:]
                      for sg in self._spec_segments((axis, c, spur), pts)]

    def _spur_search(self, nd, pts, score):
        """L trunks worth pricing: a bus along one group's column that turns
        onto the row the OTHER group already sits on.

        Nothing here is a free parameter -- every coordinate offered is one
        the net's own pins already occupy:

        * `c2`  a line carrying two or more pins that FACE along it.  That
                is the gate row of a current mirror, and it is the whole
                reason this exists: a gate faces sideways and a drain faces
                up, so ONE straight trunk always makes one of the two
                groups turn at the pin.  Razavi turns the wire instead.
        * `c`   the line most of the remaining pins already sit on.
        * `hc`  where the connector leaves the main arm -- strictly between
                two of its pins, so the tap is a real three-legged tee.
        * `j`   where it joins the spur, likewise.  The gaps between
                adjacent spur pins are also where a body is least likely to
                be in the way (HW2's gate bus leaves between M_1 and M_3,
                exactly as the hand-drawn figure does).

        Searched in two stages -- first where the main arm goes, then where
        the connector crosses -- because the product of the two is several
        hundred candidates a net and the trunk search is already the
        expensive part of a layout.
        """
        out = []
        for axis in ("h", "v"):
            ax2 = "v" if axis == "h" else "h"
            ci2 = 1 if ax2 == "h" else 0
            ai2 = 1 - ci2
            ai, ci = (0, 1) if axis == "h" else (1, 0)
            d2 = "H" if ax2 == "h" else "V"
            lev = {}
            for p in pts:
                if d2 in self._pindir.get(p, ()):
                    lev.setdefault(p[ci2], []).append(p)
            for c2 in sorted(lev, key=lambda v: (-len(lev[v]), v))[:2]:
                if len(lev[c2]) < 2:
                    continue
                main, sp = self._split_pins((ax2, c2, 0, 0), pts)
                if len(main) < 2 or len(sp) < 2:
                    continue
                alongs = sorted(set(p[ai] for p in main))
                sal = sorted(set(p[ai2] for p in sp))
                if len(alongs) < 2 or len(sal) < 2:
                    continue
                hcs = [10 * ((alongs[i] + alongs[i + 1]) // 20)
                       for i in range(len(alongs) - 1)]
                hcs = [h for h in hcs if alongs[0] < h < alongs[-1]][:2]
                js = [10 * ((sal[i] + sal[i + 1]) // 20)
                      for i in range(len(sal) - 1)]
                js = [x for x in js if sal[0] < x < sal[-1]][:3]
                if not hcs or not js:
                    continue
                cnt = {}
                for p in main:
                    cnt[p[ci]] = cnt.get(p[ci], 0) + 1
                seed = [max(cnt, key=lambda v: (cnt[v], -v)),
                        sorted(p[ci] for p in main)[len(main) // 2]]
                cs, seen = [], set()
                for v in seed:
                    for off in (0, -10, 10):
                        if v + off not in seen:
                            seen.add(v + off)
                            cs.append(v + off)
                # stage 1: where does the main arm run?
                best = None
                for c in cs:
                    spur = (ax2, c2, hcs[0], js[0])
                    k = score(axis, c, spur)
                    if k is None:
                        continue
                    out.append((axis, c, spur, k))
                    if best is None or k < best[0]:
                        best = (k, c)
                if best is None:
                    continue
                # stage 2: and where does the connector cross to the spur?
                for hc in hcs:
                    for j in js:
                        if hc == hcs[0] and j == js[0]:
                            continue
                        spur = (ax2, c2, hc, j)
                        k = score(axis, best[1], spur)
                        if k is not None:
                            out.append((axis, best[1], spur, k))
        return out

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
    def _arm_segments(axis, c, pts, extra=()):
        """One straight arm at `c` covering `pts`, plus one riser per pin.

        The risers are the part the old cost model ignored, and they are
        exactly where Fig 7.94's V_in/V_out short came from.

        `extra` are further ALONG coordinates the arm has to reach -- where
        a connector leaves it for the other arm of an L trunk.

        A segment is (kind, axis, fixed coordinate, lo, hi) along the other
        axis.  `kind` is "t" for the trunk itself and "r" for a riser: a
        body the trunk grazes and a body a riser grazes are priced apart.
        """
        ai, ci = (0, 1) if axis == "h" else (1, 0)
        alongs = [p[ai] for p in pts] + list(extra)
        a0, a1 = min(alongs), max(alongs)
        out = [("t", axis, c, a0, a1)]
        other = "v" if axis == "h" else "h"
        for p in pts:
            if p[ci] == c:
                continue
            lo, hi = sorted((p[ci], c))
            out.append(("r", other, p[ai], lo, hi))
        return out

    @staticmethod
    def _net_segments(axis, c, pts):
        """The same lines without the kind tag -- what `taken` stores."""
        return [s[1:] for s in Placer._arm_segments(axis, c, pts)]

    @staticmethod
    def _split_pins(spur, pts):
        """Which pins the spur arm serves, and which stay on the main one.

        Any pin SITTING ON the spur line has to be served by the spur: a
        riser off the main arm that ended there would run along the spur
        and read as a short.
        """
        if not spur:
            return list(pts), []
        ax2, c2 = spur[0], spur[1]
        ci2 = 1 if ax2 == "h" else 0
        return ([p for p in pts if p[ci2] != c2],
                [p for p in pts if p[ci2] == c2])

    def _spec_segments(self, spec, pts):
        """Every line this net draws, for a straight trunk OR an L trunk.

        An L trunk is two perpendicular arms joined by a connector: leave
        the main arm at along `hc`, run across to the spur's along `j`,
        then run parallel to the main arm into the spur.  `j == c` and
        `hc == c2` each collapse one connector leg, so a plain elbow is the
        degenerate case of the same shape.

        Why it exists: the hand-drawn library puts almost NO corner on a
        pin (17 across 27 figures; this lane put 145 there).  A gate faces
        sideways and a drain faces up, so one straight trunk always makes
        one of the two groups turn AT the pin.  Razavi instead runs the
        bus along the drain column and turns it onto the gate row -- the
        corner lands on the wire, where the reader expects it.
        """
        axis, c, spur = spec
        if not spur:
            return self._arm_segments(axis, c, pts)
        ax2, c2, hc, j = spur
        main, sp = self._split_pins(spur, pts)
        if not main or not sp:
            return None
        out = self._arm_segments(axis, c, main, extra=(hc,))
        out += self._arm_segments(ax2, c2, sp, extra=(j,))
        for ax, cc, q0, q1 in ((ax2, hc, c, j), (axis, j, hc, c2)):
            if q0 != q1:
                out.append(("t", ax, cc, min(q0, q1), max(q0, q1)))
        return out

    def _spec_corners(self, spec, pts, segs=None):
        """Corners this trunk makes: any point where an H path meets a V.

        The paths are the segments above AND each pin's escape direction --
        the definition `bend_count` scores the finished drawing with.
        Counting it geometrically instead of per pin is what lets an L
        trunk be judged honestly: it has to pay for its own elbow.
        """
        if segs is None:
            segs = self._spec_segments(spec, pts)
        poi = set(pts)
        # index the lines by the coordinate they are FIXED at, so a point
        # only has to look at the one row and the one column it lies on
        rows, cols = {}, {}
        for _k, ax, cc, a0, a1 in segs:
            if a0 == a1:
                continue
            (rows if ax == "h" else cols).setdefault(cc, []).append((a0, a1))
            poi.add((a0, cc) if ax == "h" else (cc, a0))
            poi.add((a1, cc) if ax == "h" else (cc, a1))
        n = 0
        for p in poi:
            h = any(a0 <= p[0] <= a1 for a0, a1 in rows.get(p[1], ()))
            v = any(a0 <= p[1] <= a1 for a0, a1 in cols.get(p[0], ()))
            if not (h and v):
                faces = self._pindir.get(p, ()) if p in pts else ()
                h = h or "H" in faces
                v = v or "V" in faces
            if h and v:
                n += 1
        return n

    def _junc_hits_pin(self, axis, c, pts, extra=()):
        """A junction dot landing on a terminal -- the schema rejects it."""
        ai, ci = (0, 1) if axis == "h" else (1, 0)
        bytap = {}
        for p in pts:
            bytap.setdefault(p[ai], []).append(p[ci])
        for k in extra:
            bytap.setdefault(k, [])
        keys = sorted(bytap)
        n = 0
        for i, k in enumerate(keys):
            ends = 1 if i in (0, len(keys) - 1) else 2
            legs = ends + len([1 for v in bytap[k] if v != c])
            if k in extra:
                legs += 1
            pt = (k, c) if axis == "h" else (c, k)
            if legs >= 3 and pt in self._allpins:
                n += 1
        return n

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

    def _trunk_cost(self, nd, axis, c, pts, taken, inks, member, spur=None):
        """(hard, bodies, risers, overlap) -- lower is better.

        `hard` is what the drawing may not contain at all: a junction landing
        on a terminal (the schema rejects it) and two nets sharing one line
        (the reader sees a short).  The rest is comfort.
        """
        M = 8
        spec = (axis, c, spur)
        segs = self._spec_segments(spec, pts)
        if segs is None:
            return None
        mine = [s[1:] for s in segs]
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
        _h1 = hard
        main, sp = self._split_pins(spur, pts)
        if spur:
            hard += self._junc_hits_pin(axis, c, main, (spur[2],))
            hard += self._junc_hits_pin(spur[0], spur[1], sp, (spur[3],))
        else:
            hard += self._junc_hits_pin(axis, c, pts)
        # how much wire this trunk costs: the arms themselves plus one riser
        # per pin.  Minimised at the median of the pins, which is also what
        # stops the bus wandering off and dragging every riser with it.
        _h2 = hard
        wire = sum(hi - lo for _k, _ax, _cc, lo, hi in segs)
        trunks = [s for s in segs if s[0] == "t"]
        rsegs = [s for s in segs if s[0] == "r"]

        def _band(seg, bb):
            _k, ax, cc, s0, s1 = seg
            lo, hi = (bb[1], bb[3]) if ax == "h" else (bb[0], bb[2])
            alo, ahi = (bb[0], bb[2]) if ax == "h" else (bb[1], bb[3])
            return cc, s0, s1, lo, hi, alo, ahi

        def inside(seg, bb):
            cc, s0, s1, lo, hi, alo, ahi = _band(seg, bb)
            return (lo + 1 < cc < hi - 1
                    and not (s1 <= alo + 1 or s0 >= ahi - 1))

        def near(seg, bb):
            cc, s0, s1, lo, hi, alo, ahi = _band(seg, bb)
            return (lo - M <= cc <= hi + M
                    and not (s1 < alo - M or s0 > ahi + M))

        bodies = risers = 0
        for iid, bb in inks:
            if iid in member.get(nd, ()):
                # A wire may touch its own component's pin -- it may not go
                # INSIDE the body to get there.  This one exemption is what
                # let a bus ride over a gate lead, cut across an op-amp
                # triangle and come back up through a capacitor (user,
                # 2026-09-02).  Entering is forbidden, not merely costly.
                # ...except along that part's OWN gate pin: Razavi runs the
                # base bus straight through every transistor of a current
                # mirror at base height, and banning it costs one corner per
                # base (user, 2026-09-03).  `_body_audit` allows the same.
                # Never for an op-amp: the owner map only holds CTRL gates.
                onpin = False
                for _k, ax, cc, _s0, _s1 in trunks:
                    ci_ = 1 if ax == "h" else 0
                    if any(abs(p[ci_] - cc) <= 10
                           and iid in self._pinowner.get(p, ())
                           for p in pts):
                        onpin = True
                        break
                if onpin:
                    continue
                if any(inside(s, bb) for s in trunks):
                    hard += 1                    # the trunk itself is inside
                if any(inside(s, bb) for s in rsegs):
                    hard += 1                    # a riser dips inside
                continue
            # Entering someone else's body is exactly as illegal as entering
            # your own: `_body_audit` does not care whose part it is.  The
            # cost model used to price a foreign body as a soft `bodies`
            # point, so the search happily drove a bus through a diode
            # (bridge rectifier) and through an op-amp triangle (14.36(b)).
            # NB treating a NAME as a soft blocker (so the bus could buy a
            # straight run by moving it) was tried 2026-09-04 and reverted:
            # constant-gm went 13.5 -> 19.5.  Changing what blocks the trunk
            # reshapes the whole search space, and the descent then loses the
            # layout it used to find -- the same failure as stage/gaterow.
            soft = iid.startswith("soft:")
            if not soft and any(inside(s, bb) for s in trunks):
                hard += 1
                continue
            if any(near(s, bb) for s in trunks):
                # `_wire_clearance` calls anything closer than M a wire that
                # "reads as a connection that is not there", so on some
                # figures the soft price is too cheap (14.36(b) parked three
                # wires 5 units off OA2).  Which price is right depends on
                # how much room the figure has, so it is an axis.
                if str(self.opt("bodycost", "soft")) == "hard" and not soft:
                    hard += 1
                else:
                    bodies += 1
                continue
            if not soft and any(inside(s, bb) for s in rsegs):
                hard += 1
                continue
            if any(near(s, bb) for s in rsegs):
                risers += 1
        if os.environ.get("AC_HARDDBG") == nd:
            blockers = [i for i, bb in inks
                        if any(inside(s, bb) for s in trunks)]
            print("      HARD %s %s c=%-4d spur=%s short=%d pintouch=%d "
                  "junc=%d body=%d | crossing: %s"
                  % (nd, axis, c, spur, shorted, _h1 - shorted, _h2 - _h1,
                     hard - _h2, blockers[:6]))
        # Corners this trunk creates.  Measured on the library, the netlist
        # lane's excess corners sit almost entirely ON PINS -- 145 of them
        # across 27 figures where the hand-drawn versions have 17.  So the
        # count has to ask which way each pin FACES, not merely whether the
        # trunk passes through it: a lying-down resistor's pins leave
        # horizontally, and a vertical trunk through one of them still turns
        # 90 degrees at the pin.
        corners = self._spec_corners(spec, pts, segs)
        order = self.opt("cost", "hbRwo")
        vals = {"h": hard, "b": bodies, "r": risers, "w": wire // 10,
                "o": overlap, "x": cross, "n": corners,
                # "R" weighs a crossing and a body-crossing riser the same:
                # both are "this wire has to get past something"
                "R": risers + cross,
                "S": risers + 2 * cross}
        return tuple(vals[k] for k in order)

    def netterms_raw(self, nd):
        return [(d.ref, p) for d in self.c.devices
                for p, n in d.pins.items() if n == nd]

    # ---------------------------------------------------------------- wiring
    def _diode_pairs(self):
        """Transistors wired as a diode: gate tied to drain (or collector).

        Both pins are on the same net, so "one net, one trunk" hangs BOTH on
        the bus -- and each one whose face disagrees with the bus direction
        costs a corner.  Razavi instead runs the link between them as its
        own little wire and lets the bus serve only the gate: 9.83's I_REF /
        M_REF and M_4 / M_3 are exactly this (user, 2026-09-04).
        """
        out = []
        for d in self.c.devices:
            if d.sym not in CTRL or d.ref not in self.f.placed:
                continue
            g = CTRL[d.sym]
            top = FIXED_VERT.get(d.sym, ("D", "S"))[0]
            if d.pins.get(g) is None or d.pins.get(g) != d.pins.get(top):
                continue
            out.append((d.ref, top, g, d.pins[g]))
        return out

    def _link_diode_gates(self, pairs):
        """The D->G link: out along D's face, across, then into G."""
        for ref, top, g, nd in pairs:
            try:
                dxy, gxy = self.f.pin(ref, top), self.f.pin(ref, g)
                dv = self.f.pin_dir(ref, top)
            except KeyError:
                continue
            step = 10 * (dv[1] if dv and dv[1] else -1)
            out = dxy[1] + step
            rid = "r-%s-dg" % ref
            self.f.route(rid, self.netid[nd], self.f.term(ref, top),
                         [("bend", dxy[0], out), ("bend", gxy[0], out),
                          ("to", self.f.term(ref, g))])
            self._note_legs(rid, [dxy, (dxy[0], out), (gxy[0], out), gxy])

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
        self._label_above = self._gate_row_labels()
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
        # a diode-connected drain is served by its own link, so the trunk
        # does not have to reach it (it would cost a corner at that pin)
        dpairs = (self._diode_pairs()
                  if str(self.opt("diodelink", "0")) == "1" else [])
        for ref, top, _g, nd in dpairs:
            self.netterms[nd] = [t for t in self.netterms[nd]
                                 if t != (ref, top)]
        if str(self.opt("movelbl", "0")) == "1":
            self._relocate_blocking_labels()
        self.tracks()               # positions moved, so pick the rows again
        self._settle_ports()
        for nd in self.c.nodes():
            terms = self.netterms[nd]
            for ref, top, _g, nd2 in dpairs:
                if nd2 == nd:
                    terms = terms + [(ref, top)]
            f.net(self.netid[nd], terms)
        self.long_haul, self.rail_ends = set(), set()
        for nd in self.c.nodes():
            if self.c.is_ground(nd):
                self._wire_ground(nd)
            elif self.c.is_supply(nd):
                self._wire_supply(nd)
            else:
                self._wire_node(nd)
        self._link_diode_gates(dpairs)

    def _set_mirror(self, iid, m):
        """Flip a device, keeping its conduction pins on the column line.

        `_emit` places a MOS ten units off its column so that D and S land
        ON it, and the offset flips with the mirror.  Turning the device
        over without re-applying that moved the drain 20 units sideways and
        the branch above it grew a jog (Fig 10.6(b), user 2026-09-03).
        """
        sid, x, y, mir, rot = self.f.placed[iid]
        if sid in ("nmos", "pmos") and m != mir:
            x += 20 if m == "x" else -20
        for i in self.f.instances:
            if i["id"] == iid:
                i["placement"]["mirror"] = m
                i["placement"]["position"] = {"x": x, "y": y}
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
        # the name moves with the device (it sits on the open side, SOP 3A),
        # so a flip that parks it on top of another name or another body is
        # not a flip worth making
        sid, x, y, mir, _rot = self.f.placed[d.ref]
        dx = LBL_DX.get(sid, 13)
        first = -dx if mir == "x" else dx
        mine = label_box(name(d.label), x + first, y + 5,
                         "start" if first > 0 else "end")
        for iid in self.f.placed:
            if iid == d.ref:
                continue
            # NB penalising the name landing near another BODY was tried and
            # reverted: it flipped Q1 in Fig 5.43(a) so R_B had to loop under
            # the transistor to reach the base.  `_spread_for_labels` makes
            # room for these afterwards; only name-on-name is decided here.
            e = next((q for q in self.c.devices if q.ref == iid), None)
            if e is None or e.sym not in CTRL:
                continue
            esid, ex, ey, emir, _er = self.f.placed[iid]
            edx = LBL_DX.get(esid, 13)
            ef = -edx if emir == "x" else edx
            other = label_box(name(e.label), ex + ef, ey + 5,
                              "start" if ef > 0 else "end")
            if _box_gap_box(mine, other) < LABEL_INK_GAP:
                pen += 5000
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
                # LEFT of its own pin, at the FIXED stub length -- not out at
                # the drawing's left edge.  "port 的圓圈再接的線，長度固定"
                # (user, 2026-09-03).  Reaching for the edge turned Fig
                # 9.83's V_in into a rail-length wire across the whole
                # figure, and it picked up a crossing against every vertical
                # it passed; the hand-drawn answer simply puts V_in beside
                # the column it feeds.
                x = min(p[0] for p in pins) - self.portstub - 10
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
                # ...and it leaves HORIZONTALLY, always, at a fixed
                # distance: "port 就是一條橫線接入，長度也固定"
                # (user, 2026-09-03).  A drain or source faces up or down,
                # and following that put the port under the device with a
                # corner in the wire (Fig 15.32(a)'s V_out).
                if not d[0]:
                    d = (-1, 0) if di == "input" else (1, 0)
                x, y = px + d[0] * (self.portstub + 10), py
                mir = "none" if d[0] < 0 else "x"
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
        # One output means one place for it: the far right (user,
        # 2026-09-03).  Two or more outputs have no such order, so the rule
        # only arms itself when the figure produces exactly one thing.
        outs = [v[0] for v in self.ports_placed.values() if v[2] == "output"]
        f.lane2_out = outs[0] if len(outs) == 1 else None
        # ...unless the output belongs to a stage that is not the LAST one.
        # Which stage produces the output is a fact about the circuit, not
        # about the layout: Razavi's 14.36(b) takes V_out from the first
        # op-amp and carries on through two more stages, so drawing it stage
        # by stage necessarily leaves the output mid-page (user, 2026-09-03:
        # "原圖違背Vout在最右邊的規定").  Demanding both rules at once asks
        # for a figure that cannot exist.
        sidx = getattr(self, "_stage_idx", None)
        if f.lane2_out and sidx and len(sidx) > 1:
            nd = next((n for n, v in self.ports_placed.items()
                       if v[0] == f.lane2_out), None)
            si = sidx.get(getattr(self, "_stage_node", {}).get(nd))
            if si is not None and si < max(sidx.values()):
                f.lane2_out = None

    def _colline(self, iid):
        """The x of the column this part sits in.

        A MOS is EMITTED ten units off its own column so that its drain and
        source land on the column line (`_emit`), and the offset flips with
        the mirror.  Anything that reasons about columns has to undo that,
        or a cut between a mirrored transistor and the resistor above it
        splits one branch into two (Fig 10.6(b) grew a jog in M2's drain).
        """
        sid, x, _y, mir, _rot = self.f.placed[iid]
        if sid in ("nmos", "pmos"):
            return x + 10 if mir == "none" else x - 10
        return x

    def _insert_space(self, cut, delta):
        """Push everything to the right of `cut` further right.

        Called before any wire exists, so nothing has to be re-routed: the
        column table moves with the parts, and the pins are recomputed.
        """
        f = self.f
        for iid, (sid, x, y, mir, rot) in list(f.placed.items()):
            if self._colline(iid) <= cut:
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
            cols.setdefault(self._colline(iid), []).append(b)
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
            cols.setdefault(self._colline(pid), []).append(
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
            out.append((iid, self._colline(iid), self.f.ink(iid)))
            d = next((e for e in self.c.devices if e.ref == iid), None)
            if d is not None and sid in CTRL:
                first, ldy, lal = self._ctrl_label_at(iid, sid, mir)
                # the x carried here decides who gets PUSHED, and
                # `_insert_space` decides that by COLUMN LINE -- so it has
                # to be the column line here too.  Carrying the instance x
                # instead put the cut 10 units left of M_5's own column, so
                # M_5 was pushed along with the port it was colliding with
                # and the gap never opened (Fig 9.83's M_5 vs V_b).
                out.append((iid, self._colline(iid),
                            label_box(name(d.label), x + first, y + ldy,
                                      lal)))
        for _nd, (pid, nm, _di) in self.ports_placed.items():
            if pid not in self.f.placed:
                continue
            _sid, x, y, mir, _rot = self.f.placed[pid]
            dx = LABEL_PORT if mir == "x" else -LABEL_PORT
            out.append((pid, self._colline(pid),
                        label_box(name(nm), x + dx, y + 5,
                                  "start" if dx > 0 else "end")))
        return out

    def _gate_row_labels(self):
        """Transistors whose gate bus will run AT gate height.

        Their name is fixed at dy=+5 on the far side of the gate -- exactly
        where that bus goes -- so it sits above the symbol instead.  This is
        what the hand-drawn current mirror does, and it is what lets the bus
        reach the pins in a straight line: 9.26(c) goes from 14.5 corners to
        4 (the hand-drawn figure has 6).  Ruling by the user, 2026-09-03.
        """
        # Not every figure wants this: on a two-transistor mirror the move
        # only disturbs the layout, and on the constant-gm pair it pushed
        # the gate bus onto a VDD pin.  So it is an axis, off by default --
        # the search turns it on for the figures it actually helps.
        if str(self.opt("gaterow", "0")) != "1":
            return set()
        above = set()
        byref = {d.ref: d for d in self.c.devices}
        for nd in self.c.nodes():
            rows = {}
            for t in self.netterms.get(nd, []):
                d = byref.get(t[0])
                if d is None or d.sym not in CTRL or CTRL[d.sym] != t[1]:
                    continue
                if t in self.pinxy:
                    rows.setdefault(self.pinxy[t][1], []).append(t[0])
            for _y, ids in rows.items():
                # Two or more.  The threshold was 3 for a while because at 2
                # it cost 9.83 four crossings -- but that was measured before
                # body pass-through was priced and before the feedback side
                # became searchable, so it is worth re-measuring at 2.
                if len(ids) >= 2:
                    above.update(ids)
        return above

    def _ctrl_label_at(self, iid, sym, mir):
        """(dx, dy, align) for a transistor's name -- one legal spot."""
        if iid in getattr(self, "_label_above", ()):
            b = self.f.ink(iid)
            cy = self.f.placed[iid][2]
            # clear the row above as well: that row carries the drain /
            # collector bus, and a name parked right on it is the same
            # defect in a different place
            return (0, dy_above(max(abs(b[1] - cy), abs(b[3] - cy)) + 12),
                    "middle")
        dx = LBL_DX.get(sym, 13)
        first = -dx if mir == "x" else dx
        return (first, 5, "start" if first > 0 else "end")

    def _relocate_blocking_labels(self):
        """Move a transistor's name only when IT ALONE stands between a bus
        and a straight run.

        The straightest trunk is the line most of the net's pins already sit
        on.  If that line is free except for one transistor's name, the name
        moves (above, or below) and the bus gets its straight run.  Every
        other name stays exactly where SOP 3A puts it -- this is the narrow
        case the user carved out (2026-09-04: "特殊情況可以移標籤位置,
        不能都這樣"), not a general licence to shuffle labels.
        """
        moved = {}
        inks = dict((i, b) for i, b in getattr(self, "_inks", []))
        for nd, (axis, c, _spur) in list(self.trunk.items()):
            pts = [self.pinxy[t] for t in self.netterms.get(nd, [])
                   if t in self.pinxy]
            if len(pts) < 3:
                continue
            ci = 1 if axis == "h" else 0
            counts = {}
            for p in pts:
                counts[p[ci]] = counts.get(p[ci], 0) + 1
            best_c, n = max(counts.items(), key=lambda kv: (kv[1], -abs(kv[0] - c)))
            if n < 2 or best_c == c:
                continue
            a0 = min(p[1 - ci] for p in pts)
            a1 = max(p[1 - ci] for p in pts)
            blockers = []
            for iid, bb in inks.items():
                lo, hi = (bb[1], bb[3]) if axis == "h" else (bb[0], bb[2])
                alo, ahi = (bb[0], bb[2]) if axis == "h" else (bb[1], bb[3])
                if lo + 1 < best_c < hi - 1 and not (a1 <= alo + 1
                                                     or a0 >= ahi - 1):
                    blockers.append(iid)
            # a member transistor's BODY is already exempt on its own gate
            # line, so it is not a blocker -- only its name is
            mem = getattr(self, "_member", {}).get(nd, set())
            real = [b for b in blockers
                    if not b.startswith("lbl:") and b not in mem
                    and not b.startswith("soft:")]
            names = [b for b in blockers if b.startswith("lbl:")]
            if not names or real:
                continue            # something REAL is in the way as well
            # ...and no OTHER net's pin may sit on that line: a bus laid
            # over a foreign pin draws a joint that is not there (HW2's
            # gate line carries a V_DD pin at 210,140)
            if any(nd not in owners and pxy[ci] == best_c
                   and a0 <= pxy[1 - ci] <= a1
                   for pxy, owners in getattr(self, "_pinnet", {}).items()):
                continue
            for b in names:
                iid = b.split(":", 1)[1]
                if iid in self.f.placed and self.f.placed[iid][0] in CTRL:
                    moved[iid] = True
        self._label_above = set(self._label_above) | set(moved)
        return moved

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

    def _supply_label(self):
        """Whatever the deck called its supply, subscripted.

        Hard-coding V_DD printed a bipolar stage's rail as V_DD even though
        the deck said `.global VCC` (Razavi Fig 10.6(a)).
        """
        nm = (self.c.globals[0] if self.c.globals else "VDD").upper()
        if len(nm) > 1 and nm.startswith("V"):
            return "V_" + nm[1:]
        return nm

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
        """One net, one trunk -- straight, or an L with two arms.

        The L is drawn as two arms plus a connector: the connector leaves
        the main arm at a T (junction), turns once, and joins the spur at
        another T.  Both taps sit STRICTLY INSIDE their arm's pin span, so
        each really is a three-legged tee and needs no special case.
        """
        ts = [t for t in self.netterms[nd] if t in self.pinxy]
        if len(ts) < 2:
            return
        spec = self.trunk.get(nd)
        if spec is None:
            spec = ("h", self.bus_y.get(nd, self.ynode.get(
                nd, self.pinxy[ts[0]][1])), None)
        axis, c, spur = spec
        if not spur:
            self._wire_arm(nd, ts, axis, c)
            return
        ax2, c2, hc, j = spur
        ci2 = 1 if ax2 == "h" else 0
        main = [t for t in ts if self.pinxy[t][ci2] != c2]
        sp = [t for t in ts if self.pinxy[t][ci2] == c2]
        a1 = self._wire_arm(nd, main, axis, c, tap=hc)
        a2 = self._wire_arm(nd, sp, ax2, c2, tap=j, tag="s")
        if a1 is None or a2 is None:
            return
        p1 = (c, hc) if axis == "v" else (hc, c)
        p2 = (j, c2) if ax2 == "h" else (c2, j)
        mid = (p2[0], p1[1]) if axis == "v" else (p1[0], p2[1])
        rid = "r-%s-link" % nd
        self.f.route(rid, self.netid[nd], a1,
                     [("bend", mid[0], mid[1]), ("to", a2)])
        self._note_legs(rid, [p1, mid, p2])
        self.long_haul.add(rid)

    def _wire_arm(self, nd, ts, axis, c, tap=None, tag=""):
        """Draw one straight arm and everything hanging off it.

        Pins are grouped by their coordinate ALONG the arm.  A tap gets a
        junction only where three or more wires really meet -- that is what
        draws the dot (SOP 3H rule 4) -- and a two-wire corner gets a bend.

        `tap` is an extra along coordinate where the L's connector leaves;
        it adds one leg there, which is what turns it into a tee.  Returns
        the anchor at `tap` (or None).
        """
        f = self.f
        if not ts:
            return None
        ai, ci = (0, 1) if axis == "h" else (1, 0)

        def xy(along, across):
            return (along, across) if axis == "h" else (across, along)

        groups = {}
        for t in ts:
            p = self.pinxy[t]
            groups.setdefault(p[ai], []).append((p[ci], t))
        if tap is not None:
            groups.setdefault(tap, [])
        keys = sorted(groups)
        if len(keys) == 1:                      # a plain collinear stack
            seq = sorted(groups[keys[0]])
            for i in range(len(seq) - 1):
                if seq[i][0] == seq[i + 1][0]:
                    continue      # pin on pin: connected, no wire needed
                rid = "r-%s-%s%d" % (nd, tag, i)
                f.route(rid, self.netid[nd], f.term(*seq[i][1]),
                        [("to", f.term(*seq[i + 1][1]))])
                self._note_legs(rid, [xy(keys[0], seq[i][0]),
                                      xy(keys[0], seq[i + 1][0])])
            return None
        anchor, kind = {}, {}
        for i, k in enumerate(keys):
            on = [t for v, t in groups[k] if v == c]
            ends = 1 if i in (0, len(keys) - 1) else 2
            segs = ends + len([1 for v, _t in groups[k] if v != c])
            if k == tap:
                segs += 1
            if segs >= 3:
                jid = "j-%s-%s%d" % (nd, tag, i)
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
                rid = "r-%s-%s%s%s" % (nd, tag, t[0].lower(), t[1].lower())
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
            rid = "r-%s-%sbus%d" % (nd, tag, i)
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
        return anchor.get(tap)

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
        # a transistor sharing a gate bus at gate height puts its name
        # above the symbol -- one spot, no search (user, 2026-09-03)
        if sym in CTRL and iid in getattr(self, "_label_above", ()):
            # above by default; below is the fallback when the row above is
            # already taken (Q_REF sits under the reference current source)
            up = self._ctrl_label_at(iid, sym, mir)
            # ...and the gate side last: the bus leaves the gate towards the
            # other transistors, so the gate side of the END device is free
            # (Q_REF sits between the reference source above and ground
            # below, with nowhere else to put its name)
            back = dx if mir == "x" else -dx
            first = -dx if mir == "x" else dx
            return [up, (0, dy_below(hi + 12), "middle"),
                    (back, 5, "start" if back > 0 else "end"),
                    (first, 5, "start" if first > 0 else "end")]
        # the canonical side: away from the gate, i.e. the side the ink is on
        first = -dx if mir == "x" and sym in CTRL else dx
        # every candidate stays within `dx` of the device: the label may
        # move UP or DOWN beside it, never away from it
        if sym in ("capacitor", "variable-capacitor"):
            # A capacitor's name sits at a FIXED distance from its plates --
            # above it when it is lying down, beside it when it stands up
            # (user, 2026-09-03: "固定好電容標籤和電容的距離").  Only the
            # side may change, never the gap.
            rot = self.f.placed[iid][4]
            side = [(dx, 5, "start"), (-dx, 5, "end")]
            over = [(0, dy_above(hi), "middle"), (0, dy_below(hi), "middle")]
            # the GAP is fixed; which of the four sides it takes is still
            # free, otherwise a crowded figure has nowhere to put it
            return (over + side) if rot else (side + over)
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
        # A transistor's name has one legal spot and never moves, so every
        # searching label must already know where they all are -- otherwise
        # a part declared earlier in the deck picks a spot that a transistor
        # later takes (Fig 9.83: I_REF's name landed on M_4's).
        for d in self.c.devices:
            if d.ref not in f.placed or d.sym not in CTRL:
                continue
            _sid, x, y, mir, _rot = f.placed[d.ref]
            first, ldy, lal = self._ctrl_label_at(d.ref, d.sym, mir)
            self._lbox.append(label_box(name(d.label), x + first, y + ldy,
                                        lal))
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
            axis, c = self.trunk[nd][:2]
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
              # "n" prices the corners a trunk creates (a pin off the trunk
              # needs a riser, and the riser meets the trunk at one).
              # Ordering it before wire buys a shared line with a
              # longer one; the search decides which figure wants that.
              # NB "hbnRwo" (corners ahead of the avoidance term) was
              # tried and removed: on 8.57 it drove a riser into the op-amp
              # body.  Corners may outrank WIRE, never avoidance.
              # "hnbRwo" puts corners straight after the hard constraints:
              # measured on constant-gm, the corner-minimal trunk is often
              # blocked only by `bodies` (a soft "too close to a part"), and
              # one such point is worth more than four corners.
              ("cost", ("hbRwo", "hbrwo", "hbxrwo", "hbrxwo", "hbRnwo",
                        "hnbRwo")),
              ("anchor", (1, 0, "lat", "tight")),
              ("sccorder", ("decl", "ctrl")),
              ("levels", ("asap", "alap")),
              ("colorder", ("decl", "bary")),
              ("compact", (0, 1)),
              ("freecol", ("own", "share")),
              ("latup", (1, 0)),
              ("portnudge", ("label", "pin")),
              ("bodycost", ("soft", "hard")),
              # last: it reshapes the whole column order, so it
              # is swept only once the cheaper axes have settled
              )
STYLE0 = {"gaterow": 0, "sigpath": "rail", "spans": 1, "cost": "hbRwo", "anchor": 1,
          "sccorder": "decl", "levels": "asap", "colorder": "decl", "compact": 0, "freecol": "own", "latup": 1,
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
            #
            # ⚠️ This used to be `len(legs)-1` per route, and that number is
            # not the drawing's corners: a bus and the stub dropping off it
            # are two routes meeting at an L, and each scores 0.  The search
            # was therefore blind to the very thing it was supposed to be
            # minimising -- adding a corner term to the trunk cost changed
            # nothing because the score could not see the result.  Real
            # definition (user, 2026-09-03) lives in ring_corners.
            import ring_corners as _RC
            _pts, _gates, _x = _RC.corners(p.f)
            bends = len(_pts) + 2.5 * len(_gates)
            # crossings and wire trade against each other, so they share
            # one number: ranking crossings strictly above wire buys one
            # crossing with several hundred units of extra wire (measured).
            # measured over the 23-figure bench: 10 -> wire 1.31x but 24
            # crossings, 20 -> 1.35x/22, 40 -> 1.37x/22 and one more figure
            # fully clean.  Clean figures are the gate, so 40.
            # re-measured 2026-09-03, once flipping a transistor became a
            # move the search itself can make: 40 -> 21 crossings / wire
            # 1.13x, 80 -> 18 / 1.17x, 120 -> 17 / 1.21x.  Crossings are
            # what makes a drawing unreadable, so 80.
            xw = int(os.environ.get("AC_XW", "80"))
            # measured on the 21-figure bench: 0 -> bends 1.18x,
            # 10 -> 1.11x, 25 -> 1.01x, 60 -> 1.00x and place back to 39%.
            # 60 puts the corner count at the hand-drawn level for one
            # extra crossing across the whole library.
            bw = int(os.environ.get("AC_BW", "60"))
            # A crossing weighs MORE than a corner, but not infinitely
            # more (user, 2026-09-03: "交叉優化權重大於轉折優化").  Making
            # it a strict lexicographic key was tried and measured worse on
            # every count -- crossings 8 -> 13, bends 1.43x -> 1.46x, mirror
            # 92% -> 86%: a search that can only see crossings settles into
            # a worse corner of the space.
            out = (_audit_count(log),
                   _cross_from(log) * xw + bends * bw + wire // 10, wire)
        except Exception:                      # a style that cannot be drawn
            out = (999, 999, 10 ** 9)          # scores itself out
        tried[key] = out
        return out

    fast = os.environ.get("AC_FAST")
    os.environ["AC_FAST"] = "1"
    try:
        # gaterow moves every name in a mirror row, so it reshapes what
        # the trunks must dodge.  That makes it a STARTING POINT, not an
        # axis: swept inside the descent it is always judged against a
        # layout the other axes already tuned for the names' old spots,
        # and it loses every time (9.26(c): forced on 4 corners / 0
        # crossings, forced off 14.5 / 1, yet the descent chose off).
        def descend(gr, drop=(), start=None):
            style, grid = dict(STYLE0, gaterow=gr), (COL_PITCH, 60, 20)
            if start:
                style.update(start)
            formir = {}

            def sc_of(g, st, fm):
                st = dict(st)
                if fm:
                    st["formir"] = tuple(sorted(fm.items()))
                return score(g, st)

            def probe_cols(g, st, fm):
                st = dict(st)
                if fm:
                    st["formir"] = tuple(sorted(fm.items()))
                buf = io.StringIO()
                try:
                    pr = Placer(c, out_proj, out_svg, pitch=g[0], rowgap=g[1],
                                portstub=g[2], style=st)
                    with contextlib.redirect_stdout(buf):
                        pr.run(verbose=True)
                    return getattr(pr, "ncols", 0)
                except Exception:
                    return 0

            def probe_fb(g, st, fm):
                """Which lying-down parts ride a feedback track."""
                st = dict(st)
                if fm:
                    st["formir"] = tuple(sorted(fm.items()))
                buf = io.StringIO()
                try:
                    pr = Placer(c, out_proj, out_svg, pitch=g[0], rowgap=g[1],
                                portstub=g[2], style=st)
                    with contextlib.redirect_stdout(buf):
                        pr.run(verbose=True)
                    return sorted(getattr(pr, "fb_track", {}))
                except Exception:
                    return []

            def probe_laterals(g, st, fm):
                st = dict(st)
                if fm:
                    st["formir"] = tuple(sorted(fm.items()))
                buf = io.StringIO()
                try:
                    pr = Placer(c, out_proj, out_svg, pitch=g[0], rowgap=g[1],
                                portstub=g[2], style=st)
                    with contextlib.redirect_stdout(buf):
                        pr.run(verbose=True)
                    return [d.ref for d in pr.horiz]
                except Exception:
                    return []

            def transistors(g, st, fm):
                """Which parts can be turned over, and which way they face now."""
                st = dict(st)
                if fm:
                    st["formir"] = tuple(sorted(fm.items()))
                buf = io.StringIO()
                try:
                    pr = Placer(c, out_proj, out_svg, pitch=g[0], rowgap=g[1],
                                portstub=g[2], style=st)
                    with contextlib.redirect_stdout(buf):
                        pr.run(verbose=True)
                    return [(iid, pl[3]) for iid, pl in pr.f.placed.items()
                            if pl[0] in CTRL]
                except Exception:
                    return []

            best = sc_of(grid, style, formir)
            grids = _grids(tune)

            def wider(g):
                """The next few roomier grids -- SOP 3J's 「排不下就放寬」.

                One per COLUMN PITCH, not the first four in sort order: what a
                label that will not fit needs is horizontal room, and four grids
                that share a pitch and differ only in row gap are four ways of
                not fixing it.
                """
                out, seen = [], set()
                for x in sorted(grids, key=lambda x: (x[0], abs(x[1] - g[1]))):
                    if x[0] <= g[0] or x[1] < g[1] or x[0] in seen:
                        continue
                    seen.add(x[0])
                    out.append(x)
                # spread the four probes over the whole range instead of taking
                # the four narrowest: the next pitch up is rarely enough room
                # for a label that does not fit at all, and 90/100/110/120 are
                # four ways of asking the same question.
                if len(out) <= 4:
                    return out
                step = len(out) / 4.0
                return [out[int(i * step)] for i in range(4)]

            def probe(g, st, fm, force=False):
                """Score a move, and if it fails an AUDIT give it the widening
                retry the opening layout already gets.

                A move can be right and still not fit.  Labels have exactly one
                legal spot each (SOP 3A: the transistor's name beside its
                opening, the port's name beside its circle), so a layout that is
                better in every other way can still fail `labels` outright --
                and a move judged only at the current pitch is thrown away
                before anyone asks whether it would fit at a wider one.  That is
                how Fig 9.83 lost its only clean layout: `levels=alap` is clean
                at pitch 100 and up, dirty at 80, and 80 was where it was tried.
                """
                sc = sc_of(g, st, fm)
                gc = g
                # The trigger is "this candidate still has an audit error", not
                # "it is worse than the best so far": when the best so far is
                # ALSO dirty, comparing the two at one pitch just picks the
                # prettier wrong answer.  Fig 9.83 starts dirty, so `alap` --
                # the one style that can make it clean, and only from pitch 100
                # up -- was compared at pitch 80 and discarded.  A clean figure
                # never enters this branch, so the extra draws are only spent
                # where something is actually broken.
                # `force` is for an axis that RESHAPES the drawing (gaterow moves
                # every name in a mirror row): its better layout usually needs a
                # different pitch, and judging it only at the current one throws
                # it away before anyone asks.
                if force or sc[0] > 0:
                    for g2 in wider(g):
                        s2 = sc_of(g2, st, fm)
                        if s2 < sc:
                            sc, gc = s2, g2
                return sc, gc
            # descend until a whole pass changes nothing.  Every point is
            # memoised, so a pass that re-walks ground already covered is free.
            for _round in range(4):
                moved = False
                # room first, then style.  Sweeping style first lets a cheap
                # style win at the starting pitch and then the descent can never
                # reach "original style at a wider pitch", which was the better
                # point (Fig 5.43(a): freecol=share at 80 beat the start, and
                # freecol=own at 120 -- strictly better than both -- was never
                # visited).
                for g in grids:
                    if g == grid:
                        continue
                    sc = sc_of(g, style, formir)
                    if sc < best:
                        best, grid, moved = sc, g, True
                for axis, vals in STYLE_AXES:
                    if axis == "cost" and drop:
                        vals = tuple(v for v in vals if v not in drop)
                    for v in vals:
                        if v == style[axis]:
                            continue
                        cand = dict(style, **{axis: v})
                        sc, g2 = probe(grid, cand, formir)
                        if sc < best:
                            best, style, moved = sc, cand, True
                            grid = g2
                # Turning a transistor over is a LAYOUT MOVE like any other --
                # it is often the cheapest way to lose a bend or a crossing
                # (user, 2026-09-03: "我講很久了，你還是沒把鏡像電晶體視為一種
                # 方法去降低彎折、降低交叉").  So it is swept inside the descent,
                # against the real score, and repeated until no flip helps --
                # not once at the end.
                # neighbouring columns: swapping a pair is the move that takes
                # a crossing out.  Swaps accumulate, each kept only if the whole
                # score drops.
                ncols = probe_cols(grid, style, formir)
                swaps = list(style.get("colswap") or ())
                for _pass in range(2):
                    swapped = False
                    for i in range(max(0, ncols - 1)):
                        cand = dict(style)
                        cand["colswap"] = tuple(swaps + [(i, i + 1)])
                        sc = sc_of(grid, cand, formir)
                        if sc < best:
                            best, style = sc, cand
                            swaps = list(cand["colswap"])
                            swapped = True
                    if not swapped:
                        break
                    moved = True
                # a whole column may be lifted out and re-inserted anywhere
                moves = list(style.get("colmove") or ())
                if ncols <= 12:
                    for _pass in range(2):
                        hopped = False
                        for i in range(ncols):
                            for j in range(ncols):
                                if abs(i - j) < 2:
                                    continue        # colswap covers neighbours
                                cand = dict(style)
                                cand["colmove"] = tuple(moves + [(i, j)])
                                sc = sc_of(grid, cand, formir)
                                if sc < best:
                                    best, style = sc, cand
                                    moves = list(cand["colmove"])
                                    hopped = True
                                    break
                            if hopped:
                                break
                        if not hopped:
                            break
                        moved = True
                # a lying-down part may move up or down one row
                rows = list(style.get("latrow") or ())
                for _pass in range(2):
                    nudged = False
                    for ref in probe_laterals(grid, style, formir):
                        if any(r[0] == ref for r in rows):
                            continue
                        # rows are not always a whole 40 apart -- a pin row and
                        # a node row can sit 20 apart (Fig 3.57's C_1 at 200 and
                        # D_2 at 220), so the step has to be able to reach that
                        for dy in (-20, 20, -40, 40):
                            cand = dict(style)
                            cand["latrow"] = tuple(rows + [(ref, dy)])
                            sc = sc_of(grid, cand, formir)
                            if sc < best:
                                best, style = sc, cand
                                rows = list(cand["latrow"])
                                nudged = True
                                break
                    if not nudged:
                        break
                    moved = True
                # a feedback part may ride the track BELOW instead of above:
                # Razavi puts R_5 under 14.36(b) while R_3 and R_6 stay on
                # top, and he chooses per part (user, 2026-09-03)
                sides = list(style.get("fbside") or ())
                for _pass in range(2):
                    dropped = False
                    for ref in probe_fb(grid, style, formir):
                        if any(t[0] == ref for t in sides):
                            continue
                        cand = dict(style)
                        cand["fbside"] = tuple(sides + [(ref, -1)])
                        sc = sc_of(grid, cand, formir)
                        if sc < best:
                            best, style = sc, cand
                            sides = list(cand["fbside"])
                            dropped = True
                    if not dropped:
                        break
                    moved = True
                for _pass in range(3):
                    flipped = False
                    for ref, cur in transistors(grid, style, formir):
                        other = "x" if cur != "x" else "none"
                        if formir.get(ref) == other:
                            continue
                        cand = dict(formir)
                        cand[ref] = other
                        # a flip that loses a crossing but drops the label
                        # between two devices needs the room, not the veto
                        # (Fig 15.32(b)'s M_2, user 2026-09-03: "左下角那顆可以
                        # 鏡像去減少交叉點")
                        sc, gcand = probe(grid, style, cand)
                        if sc < best:
                            best, formir, flipped = sc, cand, True
                            grid = gcand
                    if not flipped:
                        break
                    moved = True
                if not moved:
                    break
            if formir:
                style = dict(style)
                style["formir"] = tuple(sorted(formir.items()))
            return best, style, grid

        _g = {}
        for _d in c.devices:
            if _d.sym in CTRL:
                _g.setdefault(_d.pins[CTRL[_d.sym]], []).append(_d.ref)
        # a shared gate row of two or more may want it; the second descent
        # only runs when such a row exists, and its result has to beat the
        # first outright, so an unhelpful figure simply keeps the first
        _starts = [0, 1] if any(len(v) >= 2 for v in _g.values()) else [0]
        # NB multi-start over `levels` was tried 2026-09-04 and reverted.
        # Both ways -- as an extra starting dimension while it stayed an
        # axis, and moved out of the axis list entirely -- gave the SAME
        # numbers as no multi-start at all, figure by figure, at twice the
        # search cost.  A descent that sweeps an axis anyway ends up in the
        # same place whichever value it starts from; `gaterow` is different
        # because it moves the labels, which changes what every trunk has to
        # dodge.  Do not re-try this without a mechanism that actually
        # reshapes the layout.
        # An L trunk is a STARTING POINT for the same reason `gaterow` is:
        # offering the search a shape it did not have before changes which
        # layout the descent settles on even where no L is finally used, and
        # then a figure can lose the straight-trunk layout it used to find
        # (HW2 went 16 -> 18 that way).  Run both and keep the better; each
        # figure gets whichever it wants.
        _res = None
        for _gr in _starts:
            for _lt in (1, 0):
                _r = descend(_gr, start={"ltrunk": _lt})
                if _res is None or _r[0] < _res[0]:
                    _res = _r
        # Still dirty?  Run the whole descent again without the newer cost
        # orders.  Coordinate descent is path-sensitive: adding "hnbRwo"
        # was enough to hide the clean layout 8.57 had been finding, and no
        # amount of sweeping from the drifted point gets it back -- the
        # clean one needs the colmove/latrow/compact moves that only the
        # other path accumulates.
        if _res[0][0] > 0:
            for _gr in _starts:
                _r = descend(_gr, drop=("hnbRwo", "hbRnwo"))
                if _r[0] < _res[0]:
                    _res = _r
        best, style, grid = _res
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
