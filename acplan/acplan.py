# 位置表產生器＋慣例檢查器。
# 目的：畫圖的人（模型）只決定「哪一顆在哪一欄、哪一列、閘極朝哪邊」，腳位偏移、鏡射、線的端點都由這裡算。
# 用法見 plans_py/ 裡的範例；每份範例跑 `python plans_py/<名稱>.py` 就會出圖並印檢查結果。
#
# 座標：格點 10 的倍數，y 向下。「導通欄 col」＝電晶體 D/S（BJT 的 C/E）所在的那條直線的 x。
import json
import os

from acdraw import parse_deck, draw, world, HERE

PINS = json.load(open(os.path.join(HERE, "pins_table.json"), encoding="utf-8"))
SUPPLY = {"vdd", "vcc", "0", "gnd", "vss", "vee"}
MIRROR = "horizontal"

# 慣例的數值（他 2026-11-11 的裁示；改這裡要先問他）
LEAD_MAX = 50          # 埠到它接的腳位／線，最長（他核可的 Miller 輸出埠是 50；V_b 短引線他要 30）
LEAD = 30              # 預設引線長
STACK_MIN, STACK_MAX = 70, 140     # 上下相鄰兩顆電晶體的列距
AREA_PER_DEVICE = 22000            # 外框面積 ÷ 元件數 的上限（太鬆）


class Plan(object):
    def __init__(self, name, deck, vdd_name="VDD"):
        self.name, self.deck, self.vdd_name = name, deck, vdd_name
        self.devs, self.deck_ports, self.names = parse_deck(os.path.join(HERE, deck))
        self.dev = dict((d["ref"], d) for d in self.devs)
        self.nets = {}
        for d in self.devs:
            for pin, net in d["pins"].items():
                self.nets.setdefault(net, []).append((d["ref"], pin))
        self.parts, self.col, self.ports, self.trunks = {}, {}, {}, {}
        self.free, self.label_at, self.order, self.through = [], {}, [], []
        self.rail_spec, self.gnd_drop, self.gnd_at = None, 20, {}
        self.extra_rails = []
        self.paths = []

    # ---------- 放元件 ----------
    def place(self, ref, x, y, rot=0, mirror="none"):
        assert ref in self.dev, "deck 裡沒有 %s" % ref
        self.parts[ref] = [x, y, rot, mirror]
        self.col.setdefault(ref, x)
        return self

    def mos(self, ref, col, y, gate="L"):
        """MOS：col＝D/S 那條直線的 x；gate＝閘極朝左 "L" 或朝右 "R"。"""
        assert self.dev[ref]["symbol"] in ("nmos", "pmos"), ref
        self.col[ref] = col
        return self.place(ref, col - 10, y) if gate == "L" else self.place(ref, col + 10, y, 0, MIRROR)

    def bjt(self, ref, col, y, base="L"):
        assert self.dev[ref]["symbol"] in ("npn", "pnp"), ref
        self.col[ref] = col
        return self.place(ref, col, y) if base == "L" else self.place(ref, col, y, 0, MIRROR)

    def tr(self, ref, col, y, gate="L"):
        return self.mos(ref, col, y, gate) if self.dev[ref]["symbol"] in ("nmos", "pmos") else self.bjt(ref, col, y, gate)

    def stack(self, col, gate, items):
        """同一欄由上到下一疊：items＝[(ref, y), ...]。"""
        for ref, y in items:
            self.tr(ref, col, y, gate)
        return self

    def pair(self, a, b, cols, y, gates="out"):
        """左右成對的兩顆。gates="out"＝閘極朝外（差動輸入對）；"in"＝閘極相對（共用閘極線的電流鏡、疊接對）。"""
        ga, gb = ("L", "R") if gates == "out" else ("R", "L")
        self.tr(a, cols[0], y, ga)
        self.tr(b, cols[1], y, gb)
        return self

    def opamp(self, ref, x, y, plus="bottom"):
        """運放：輸入在左 (x-40, y∓10)、輸出在右 (x+30, y)。plus＝IN+ 在下（預設）或在上 "top"。"""
        return self.place(ref, x, y, 0, "none" if plus == "bottom" else "vertical")

    def two(self, ref, x, y, horizontal=False, first=None):
        """兩端元件（R、C、L、電流源、電壓源、二極體；二極體的第 1 支腳是陽極 A）：直放時腳在 (x, y∓20)；horizontal＝橫放。
        first＝netlist 裡寫在前面的那支腳朝哪邊（U 上／D 下／L 左／R 右）；預設直放朝上、橫放朝左。
        線要從哪一端接出去，那一端就要朝那個方向，否則編輯器會說線跨過另一支腳。"""
        self.col[ref] = x
        first = first or ("L" if horizontal else "U")
        pin1 = list(self.dev[ref]["pins"])[0]
        for rot in (0, 90, 180, 270):          # 四個方向都試（二極體預設是橫的，電阻預設是直的）
            self.place(ref, x, y, rot)
            px, py = self.pin(ref, pin1)
            if (first == "L" and px < x) or (first == "R" and px > x) or (first == "U" and py < y) or (first == "D" and py > y):
                return self
        raise AssertionError("two(%s): 轉不出 first=%s" % (ref, first))

    # ---------- 腳位 ----------
    def pin(self, ref, pin):
        x, y, rot, mir = self.parts[ref]
        return world((x, y), tuple(PINS[self.dev[ref]["symbol"]][pin]), rot, mir)

    def net_pins(self, net):
        lab = set(k.split("@")[1] for k in self.ports if k.startswith(net + "@"))      # 掛了標籤的腳不算在走線裡
        lab |= set("%s.%s" % tuple(w["from"]) for w in self.paths)   # 自己指定路徑的腳也不算
        return [self.pin(r, p) for r, p in self.nets.get(net, []) if r in self.parts and "%s.%s" % (r, p) not in lab]

    # ---------- 埠 ----------
    def port(self, net, x, y, side="L", name=None):
        """side＝埠（小圓圈與名字）在接點的哪一側：L 左、R 右、U 上、D 下。(x, y) 是線接上埠的那一點。"""
        mir, rot = {"L": ("none", 0), "R": (MIRROR, 0), "U": ("none", 90), "D": ("none", 270)}[side]
        spec = [x, y, mir, rot]
        if name:
            spec.append(name)
        self.ports[net] = spec
        return self

    def port_pin(self, net, ref, pin, lead=LEAD, side=None, name=None):
        """埠放在某支腳的正外側（閘極朝哪邊就放哪邊），距離 lead。"""
        px, py = self.pin(ref, pin)
        if side is None:
            side = "L" if px < self.parts[ref][0] else "R"
        dx, dy = {"L": (-lead, 0), "R": (lead, 0), "U": (0, -lead), "D": (0, lead)}[side]
        return self.port(net, px + dx, py + dy, side, name)

    def label(self, net, ref, pin, lead=20, side=None):
        """只在某支腳旁掛一個同名標籤（不拉線）。邏輯閘每顆電晶體的閘極各標 A／B／C 就用這個；同名＝同一條 net。"""
        px, py = self.pin(ref, pin)
        if side is None:
            side = "L" if px < self.parts[ref][0] else "R"
        dx, dy = {"L": (-lead, 0), "R": (lead, 0), "U": (0, -lead), "D": (0, lead)}[side]
        mir, rot = {"L": ("none", 0), "R": (MIRROR, 0), "U": ("none", 90), "D": ("none", 270)}[side]
        self.ports["%s@%s.%s" % (net, ref, pin)] = [px + dx, py + dy, mir, rot]
        return self

    def port_tap(self, net, x, y, side="U", lead=LEAD, name=None):
        """埠掛在一條線上的 (x, y) 這一點，往 side 方向伸出 lead（例：V_b 掛在閘極線中點上方）。"""
        dx, dy = {"L": (-lead, 0), "R": (lead, 0), "U": (0, -lead), "D": (0, lead)}[side]
        return self.port(net, x + dx, y + dy, side, name)

    # ---------- 線 ----------
    def hline(self, net, y, x0=None, x1=None):
        """這條 net 的橫幹線。不給端點＝剛好涵蓋這條 net 所有元件腳位的 x 範圍（不會多出線頭）。"""
        xs = [p[0] for p in self.net_pins(net)]
        self.trunks[net] = [[min(xs) if x0 is None else x0, y], [max(xs) if x1 is None else x1, y]]
        return self

    def vline(self, net, x, y0=None, y1=None):
        ys = [p[1] for p in self.net_pins(net)]
        self.trunks[net] = [[x, min(ys) if y0 is None else y0], [x, max(ys) if y1 is None else y1]]
        return self

    def wire(self, ref, pin, via, to):
        """指定路徑的線：從 ref 的 pin 出發，依序經過 via 的轉折點，停在 to。
        to＝一個點 (x, y)（要落在同一條 net 的幹線上），或另一支腳 ("REF", "PIN")。編輯器自己繞不過去時才用。"""
        self.paths.append({"from": [ref, pin], "via": [list(v) for v in via], "to": list(to)})
        return self

    def gate_through(self, a, b, label_below=True):
        """偏壓線從 a 的閘極橫向貫穿 a，接到同一列 b 的閘極。這是唯一允許線穿過元件的情形。"""
        ax, ay = self.pin(a, "G")
        bx, by = self.pin(b, "G")
        assert ay == by, "%s 與 %s 的閘極要在同一列" % (a, b)
        self.free.append([[ax, ay], [bx - 10 if bx > ax else bx + 10, by]])
        self.through.append((a, b))
        if label_below:
            x, y, _rot, mir = self.parts[a]
            self.label_at[a] = [x - 15 if mir == "none" else x + 15, y + 32]
        return self

    def ground(self, ref, pin, x, y):
        """指定某支接地腳的接地符號位置（預設在腳正下方 20；腳朝側面時要自己指定，免得壓到元件）。"""
        self.gnd_at["%s.%s" % (ref, pin)] = [x, y]
        return self

    def rail(self, y, x0=None, x1=None, margin=30):
        xs = [p[0] for n in self.nets if n.lower() in ("vdd", "vcc") for p in self.net_pins(n)]
        self.rail_spec = {"y": y, "x": [min(xs) - margin if x0 is None else x0, max(xs) + margin if x1 is None else x1]}
        return self

    def rail_low(self, net, y, x0=None, x1=None, margin=30):
        """最下面的負電源軌（VEE／VSS）：接到這條 net 的腳都垂直往下接到軌上。"""
        xs = [p[0] for n in self.nets if n.lower() == net.lower() for p in self.net_pins(n)]
        self.extra_rails.append({"net": net, "y": y, "x": [min(xs) - margin if x0 is None else x0, max(xs) + margin if x1 is None else x1]})
        return self

    def route_order(self, *nets):
        self.order = list(nets)
        return self

    # ---------- 輸出 ----------
    def build(self):
        missing = [d["ref"] for d in self.devs if d["ref"] not in self.parts]
        assert not missing, "還沒放的元件：%s" % missing
        plan = {"name": self.name, "deck": self.deck, "vdd_name": self.vdd_name, "parts": self.parts, "ports": self.ports,
                "gnd_drop": self.gnd_drop, "trunks": self.trunks, "free_wires": self.free, "label_at": self.label_at, "gnd_at": self.gnd_at, "extra_rails": self.extra_rails, "paths": self.paths}
        if self.rail_spec:
            plan["vdd_rail"] = self.rail_spec
        if self.order:
            plan["order"] = self.order
        return plan

    def draw(self):
        path = os.path.join(HERE, "plans", self.name + ".json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline=chr(10)) as f:
            json.dump(self.build(), f, ensure_ascii=False, indent=1)
        log, diag, same = draw(path)
        bad = self.check()
        c = diag.get("counts", {})
        thr = sum(1 for x in diag.get("items", []) if x.get("code") == "VISUAL_WIRE_THROUGH_SYMBOL")
        fails = [l for l in log if l[1] is False]
        if fails:
            bad.append("走線失敗 %d 條：%s" % (len(fails), ", ".join(l[0] for l in fails)))
        if c.get("errors") or c.get("warnings"):
            bad.append("編輯器診斷：%s 個錯誤、%s 個警告" % (c.get("errors"), c.get("warnings")))
            for x in diag.get("items", []):
                if x.get("severity") != "info":
                    bad.append("  %s：%s" % (x.get("code"), x.get("message", "")[:200]))
        if thr > len(self.free):
            bad.append("有 %d 條線穿過元件，但只宣告了 %d 條貫穿閘極" % (thr, len(self.free)))
        if not same:
            bad.append("netlist 不等價")
        print("  CHECK: %s" % ("PASS" if not bad else "FAIL (%d)" % len(bad)))
        for b in bad:
            print("    - " + b)
        for n in self.notes:
            print("    提醒：" + n)
        return bad

    # ---------- 慣例檢查（只看位置表，不必出圖） ----------
    def check(self):
        bad = []
        self.notes = []
        tr = [d for d in self.devs if d["symbol"] in ("nmos", "pmos", "npn", "pnp")
              and self.parts[d["ref"]][2] == 0]          # 橫放（轉 90／270 度）的電晶體不套成對與列距規則

        def k(d, which):          # 腳位名：控制端 / 上端 / 下端
            mos = d["symbol"] in ("nmos", "pmos")
            if which == "g":
                return "G" if mos else "B"
            n_type = d["symbol"] in ("nmos", "npn")
            up, dn = (("D", "S") if n_type else ("S", "D")) if mos else (("C", "E") if n_type else ("E", "C"))
            return up if which == "up" else dn

        def facing(ref):          # 閘極朝哪邊
            return "L" if self.parts[ref][3] == "none" else "R"

        # 1. 成對的兩顆：同一列、左右鏡射
        seen = set()
        for i, a in enumerate(tr):
            for b in tr[i + 1:]:
                if a["symbol"] != b["symbol"]:
                    continue
                ga, gb = a["pins"][k(a, "g")], b["pins"][k(b, "g")]
                n_type = a["symbol"] in ("nmos", "npn")
                sa, sb = a["pins"][k(a, "dn" if n_type else "up")], b["pins"][k(b, "dn" if n_type else "up")]
                l, r = (a, b) if self.parts[a["ref"]][0] < self.parts[b["ref"]][0] else (b, a)
                same_row = self.parts[a["ref"]][1] == self.parts[b["ref"]][1]
                if sa == sb and sa.lower() not in SUPPLY and ga != gb:            # 差動對
                    seen.add((a["ref"], b["ref"]))
                    da, db = a["pins"][k(a, "up" if n_type else "dn")], b["pins"][k(b, "up" if n_type else "dn")]
                    cross = (ga == db and gb == da)          # 交叉耦合對：各自的閘極接對方的汲極 → 閘極朝內
                    if not same_row:
                        bad.append("差動對 %s/%s 不在同一列" % (a["ref"], b["ref"]))
                    elif cross:
                        if not (facing(l["ref"]) == "R" and facing(r["ref"]) == "L"):
                            bad.append("交叉耦合對 %s/%s 的閘極要朝內（左邊那顆朝右、右邊那顆朝左）" % (l["ref"], r["ref"]))
                    elif not (facing(l["ref"]) == "L" and facing(r["ref"]) == "R"):
                        bad.append("差動對 %s/%s 的閘極要朝外（左邊那顆朝左、右邊那顆朝右）" % (l["ref"], r["ref"]))
                    tails = [d for d in self.devs if d["ref"] not in (a["ref"], b["ref"])
                             and sa in d["pins"].values() and d["ref"] in self.col]
                    if len(tails) == 1:
                        mid = (self.col[a["ref"]] + self.col[b["ref"]]) / 2.0
                        if abs(self.col[tails[0]["ref"]] - mid) > 10:
                            bad.append("尾電流源 %s 沒有置中在 %s/%s 正下方（應在 x≈%d）" % (tails[0]["ref"], a["ref"], b["ref"], mid))
                elif ga == gb and ga.lower() not in SUPPLY:                       # 共用閘極
                    others = [d for d in tr if d["pins"][k(d, "g")] == ga]
                    if len(others) != 2:
                        continue
                    lx, rx, row = self.parts[l["ref"]][0], self.parts[r["ref"]][0], self.parts[l["ref"]][1]
                    if same_row and any(lx < self.parts[o["ref"]][0] < rx and self.parts[o["ref"]][1] == row for o in tr):
                        continue          # 中間隔著別的電晶體（例：Gilbert 外側兩顆），不要求相對
                    if not same_row:
                        bad.append("共用閘極的 %s/%s 不在同一列" % (a["ref"], b["ref"]))
                    elif (l["ref"], r["ref"]) in self.through or (r["ref"], l["ref"]) in self.through:
                        pass
                    elif not (facing(l["ref"]) == "R" and facing(r["ref"]) == "L"):
                        bad.append("共用閘極的 %s/%s 閘極要相對（或用 gate_through 貫穿）" % (l["ref"], r["ref"]))
        # 2. 上下相鄰的列距
        for a in tr:
            for b in tr:
                if a is b or abs(self.col[a["ref"]] - self.col[b["ref"]]) > 10:
                    continue
                if a["pins"][k(a, "dn")] == b["pins"][k(b, "up")] and a["pins"][k(a, "dn")].lower() not in SUPPLY:
                    dy = self.parts[b["ref"]][1] - self.parts[a["ref"]][1]
                    rows = lambda d: any(o is not d and self.parts[o["ref"]][1] == self.parts[d["ref"]][1]
                                         and abs(self.col[o["ref"]] - self.col[d["ref"]]) > 10 for o in tr)
                    if dy > STACK_MAX and rows(a) and rows(b):
                        continue          # 兩顆各自跟別欄的元件對齊成列（例：第二級對齊第一級），拉長是合理的
                    if not STACK_MIN <= dy <= STACK_MAX:
                        bad.append("%s 在 %s 正下方，列距 %d，應在 %d～%d" % (b["ref"], a["ref"], dy, STACK_MIN, STACK_MAX))
        # 3. 埠的引線長度；埠要跟同一條 net 的橫線同高
        for net, spec in self.ports.items():
            x, y = spec[0], spec[1]
            if "@" in net:
                continue
            if len(spec) < 5 and net not in self.names:
                bad.append("埠 %s 沒有顯示名（deck 加 .name，或 port(..., name=\"V_x\")），會顯示成小寫的 net 名" % net)
            pins = self.net_pins(net)
            ds = [abs(x - px) + abs(y - py) for px, py in pins]
            for i, (ax, ay) in enumerate(pins):          # 兩支對齊的腳之間視為有一條直線，埠可以掛在上面
                for bx, by in pins[i + 1:]:
                    if ax == bx or ay == by:
                        cx, cy = min(max(x, min(ax, bx)), max(ax, bx)), min(max(y, min(ay, by)), max(ay, by))
                        ds.append(abs(x - cx) + abs(y - cy))
            if net in self.trunks:
                (x0, y0), (x1, y1) = self.trunks[net]
                cx, cy = min(max(x, min(x0, x1)), max(x0, x1)), min(max(y, min(y0, y1)), max(y0, y1))
                ds.append(abs(x - cx) + abs(y - cy))
                if y0 == y1 and 0 < abs(y - y0) <= 20 and spec[3] == 0:
                    self.notes.append("埠 %s 離同一條 net 的橫線只差 %d；能同高就同高，合成一個十字點" % (net, abs(y - y0)))
            for w in self.paths:                       # 自己指定路徑的線也算這條 net 的線
                if tuple(w["from"]) in self.nets.get(net, []):
                    pts = [self.pin(*w["from"])] + [tuple(v) for v in w["via"]] + ([tuple(w["to"])] if not isinstance(w["to"][0], str) else [])
                    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                        cx, cy = min(max(x, min(ax, bx)), max(ax, bx)), min(max(y, min(ay, by)), max(ay, by))
                        ds.append(abs(x - cx) + abs(y - cy))
            for a, b in self.free:
                if net in [self.dev[r]["pins"].get("G") for r, _ in self.through]:
                    ds.append(abs(x - a[0]) + abs(y - a[1]))
            if ds and min(ds) > LEAD_MAX:
                bad.append("埠 %s 的引線長 %d，超過 %d" % (net, min(ds), LEAD_MAX))
        # 4. 整體鬆緊
        xs = [p[0] for p in self.parts.values()] + [p[0] for p in self.ports.values()]
        ys = [p[1] for p in self.parts.values()] + [p[1] for p in self.ports.values()]
        area = (max(xs) - min(xs)) * (max(ys) - min(ys))
        if area / float(len(self.parts)) > AREA_PER_DEVICE:
            bad.append("太鬆：外框 %d×%d，每顆元件佔 %d，上限 %d" % (max(xs) - min(xs), max(ys) - min(ys), area / len(self.parts), AREA_PER_DEVICE))
        return bad
