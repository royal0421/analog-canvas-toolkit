# 「模型排位置、編輯器拉線」的畫圖腳本：讀一份位置表（plan）→ 上游本機 MCP 放元件、電源軌、接地、走線 → 出圖 → 跟 netlist 比對。
# 用法：python acdraw.py plans/<名稱>.json
# plan 格式見 plans/two-stage-miller.json。座標單位＝編輯器格點（10 的倍數）；y 向下。
import json, os, re, shutil, sys
from acsession import Session, save_render, HERE

SYMBOL = {"nmos": "nmos", "pmos": "pmos", "npn": "npn", "pnp": "pnp"}
# 訊號方塊圖：deck 寫 X<名稱> <net…> <類型>；類型 → (編輯器符號, 腳位順序)
BLOCK = {"adder": ("adder", ["A", "B", "Y"]), "multiplier": ("multiplier", ["A", "B", "Y"]),
         "block": ("integrator", ["A", "Y"]), "delay": ("unit-delay", ["A", "Y"]),
         "quantizer": ("quantizer", ["A", "Y"]), "adc": ("adc", ["IN", "OUT"]), "dac": ("dac", ["IN", "OUT"]),
         "amp": ("voltage-amplifier", ["IN", "OUT"]), "gm": ("transconductance", ["A", "Y"]),
         "comparator": ("comparator", ["IN+", "IN-", "OUT"])}
FLOW_IN = ("A", "B", "IN", "IN+", "IN-")          # 方塊的輸入腳：線接到這裡要畫箭頭
FLOW_OUT = ("Y", "OUT")
PASSIVE = {"R": "resistor", "C": "capacitor", "L": "inductor", "I": "current-source", "V": "voltage-source", "D": "diode"}


def parse_deck(path):
    """我們的 .cir → (devices, ports, names)。devices: [{ref, symbol, pins:{pin:net}, value}]"""
    devs, ports, names = [], [], {}
    formula, signs = {}, {}
    for ln in open(path, encoding="utf-8").read().splitlines():
        s = ln.strip()
        if not s or s.startswith("*"):
            continue
        tok = s.split()
        low = tok[0].lower()
        if low == ".subckt":
            ports = tok[2:]
        elif low in (".name", ".alias") and len(tok) >= 3:
            names[tok[1]] = tok[2]
        elif low == ".formula" and len(tok) >= 3:          # .formula XH1 A(s)　方框裡的字（可寫 K_VCO/s、1/(1+s/ω_p)）
            formula[tok[1]] = s.split(None, 2)[2]
        elif low == ".sign" and len(tok) >= 4:             # .sign XS1 + -　加法點 A、B 兩個輸入的正負號
            signs[tok[1]] = [tok[2], tok[3]]
        elif low.startswith("."):
            continue
        elif tok[0][0].upper() == "M":
            devs.append({"ref": tok[0], "symbol": SYMBOL[tok[5].lower()],
                         "pins": {"D": tok[1], "G": tok[2], "S": tok[3]}, "bulk": tok[4]})
        elif tok[0][0].upper() == "Q":
            devs.append({"ref": tok[0], "symbol": SYMBOL[tok[4].lower()],
                         "pins": {"C": tok[1], "B": tok[2], "E": tok[3]}})
        elif tok[0][0].upper() == "X" and tok[-1].lower() == "opamp":       # X <in+> <in-> <out> opamp
            devs.append({"ref": tok[0], "symbol": "opamp", "pins": {"IN+": tok[1], "IN-": tok[2], "OUT": tok[3]}})
        elif tok[0][0].upper() == "X" and tok[-1].lower() == "inverter":
            devs.append({"ref": tok[0], "symbol": "inverter", "pins": {"A": tok[1], "Y": tok[2]}})
        elif tok[0][0].upper() == "X" and tok[-1].lower() in BLOCK:
            sym, order = BLOCK[tok[-1].lower()]
            assert len(tok) == len(order) + 2, "%s：%s 要 %d 條 net（%s）" % (tok[0], tok[-1], len(order), " ".join(order))
            devs.append({"ref": tok[0], "symbol": sym, "block": tok[-1].lower(), "pins": dict(zip(order, tok[1:-1]))})
        elif tok[0][0].upper() in PASSIVE:
            sym = PASSIVE[tok[0][0].upper()]
            a, b = ("+", "-") if sym in ("current-source", "voltage-source") else (("A", "K") if sym == "diode" else ("1", "2"))
            devs.append({"ref": tok[0], "symbol": sym, "pins": {a: tok[1], b: tok[2]},
                         "value": tok[3] if len(tok) > 3 else None})
    for d in devs:
        if d["ref"] in formula:
            d["formula"] = formula[d["ref"]]
        if d["ref"] in signs:
            d["signs"] = signs[d["ref"]]
    return devs, ports, names


def flow_arrows(ws, devs, plan):
    """方塊圖的箭頭：上游沒有對應的指令，直接改專案檔裡每條線的樣式。
    線的終點是方塊輸入腳或輸出埠 → 終點畫箭頭；線是「輸入腳→接點」的方向 → 先反過來。回傳 (箭頭數, 應有數)。"""
    path = os.path.join(ws, "project.icproj.json")
    doc = json.load(open(path, encoding="utf-8"))
    sym = dict((d["ref"], d) for d in devs)
    driven = set(n for d in devs for p_, n in d["pins"].items() if p_ in FLOW_OUT)
    pid = lambda key: "P_" + "".join(c if (c.isalnum() or c in "_-") else "_" for c in key)
    out_ports = set(pid(k) for k in plan.get("ports", {}) if k.split("@")[0] in driven)

    def sink(tm):
        return bool(tm) and ((tm[0] in sym and sym[tm[0]].get("block") and tm[1] in FLOW_IN) or tm[0] in out_ports)
    n = 0
    for r in doc["documents"][0]["routes"]:
        if "legs" in r:
            last = r["legs"][-1]
            if sink(r["start"].get("terminal")) and not sink(last.get("terminal")):
                new = [dict(l) for l in reversed(r["legs"][:-1])]
                tail = {"id": last["id"]}
                tail.update(r["start"])
                r["start"] = dict((k, v) for k, v in last.items() if k != "id")
                r["legs"] = new + [tail]
                last = tail
            end = last.get("terminal")
        else:
            if sink(r["start"].get("terminal")) and not sink(r["end"].get("terminal")):
                r["start"], r["end"] = r["end"], r["start"]
            end = r["end"].get("terminal")
        if sink(end):
            r["styleOverride"] = {"arrow": "end"}
            n += 1
    with open(path, "w", encoding="utf-8", newline=chr(10)) as f:
        json.dump(doc, f, ensure_ascii=False)
    want = sum(1 for d in devs if d.get("block") for p_ in d["pins"] if p_ in FLOW_IN) + len(out_ports)
    return n, want


def flow_connectivity(ws, devs, plan):
    """方塊符號沒有 netlist 定義，匯不出 netlist；改成直接讀專案檔的線，確認每條 net 接到的腳跟 deck 一樣。"""
    doc = json.load(open(os.path.join(ws, "project.icproj.json"), encoding="utf-8"))["documents"][0]
    par = {}

    def find(a):
        par.setdefault(a, a)
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    def key(e):
        return ("T",) + tuple(e["terminal"]) if "terminal" in e else ("J", e["junction"])
    for r in doc["routes"]:
        ends = [key(r["start"])] + ([key(l) for l in r["legs"] if "terminal" in l or "junction" in l] if "legs" in r else [key(r["end"])])
        for e in ends[1:]:
            par[find(e)] = find(ends[0])
    pid = lambda k: "P_" + "".join(c if (c.isalnum() or c in "_-") else "_" for c in k)
    want = {}
    for d in devs:
        for p_, n in d["pins"].items():
            want.setdefault(n, set()).add(("T", d["ref"], p_))
    for k in plan.get("ports", {}):
        want.setdefault(k.split("@")[0], set()).add(("T", pid(k), "P"))
    roots = {}
    for n, terms in want.items():
        rs = set(find(x) for x in terms)
        if len(rs) != 1 and len(terms) > 1:
            return False, "net %s 沒有全部接在一起" % n
        roots.setdefault(rs.pop(), []).append(n)
    dup = [v for v in roots.values() if len(v) > 1]
    return (not dup), ("不同的 net 被接在一起：%s" % dup if dup else "")


def reference_spice(devs, ports, name):
    """給 verify 用的標準 SPICE（補元件值、模型宣告）。"""
    out = [".model nmos nmos", ".model pmos pmos", ".subckt %s %s" % (name, " ".join(ports))]
    for d in devs:
        p = d["pins"]
        if d["symbol"] in ("nmos", "pmos"):
            out.append("%s %s %s %s %s %s" % (d["ref"], p["D"], p["G"], p["S"], d["bulk"], d["symbol"]))
        elif d["symbol"] == "opamp":
            out.append("%s %s %s %s opamp" % (d["ref"], p["IN+"], p["IN-"], p["OUT"]))
        elif d["symbol"] == "inverter":
            out.append("%s %s %s inverter" % (d["ref"], p["A"], p["Y"]))
        elif d["symbol"] in ("npn", "pnp"):
            out.append("%s %s %s %s %s" % (d["ref"], p["C"], p["B"], p["E"], d["symbol"]))
        else:
            a, b = list(p.values())
            out.append("%s %s %s %s" % (d["ref"], a, b, d.get("value") or "1"))
    out.append(".ends")
    return "\n".join(out) + "\n"


def signature(spice):
    """SPICE 文字 → 與名稱無關的拓樸簽章（Weisfeiler-Lehman 顏色細化）。地（0/VSS/gnd）與 VDD 視為固定類別。
    簽章相同＝幾乎可確定同構（不是數學證明）；不同＝一定不同。"""
    FIX = {"0": "GND", "vss": "GND", "gnd": "GND", "vdd": "VDD", "vcc": "VDD", "vee": "VEE"}
    devs = []
    for ln in spice.splitlines():
        tok = ln.split()
        if tok and tok[0].lower() == ".subckt":
            devs = []                      # 只比最後一個 .subckt（頂層）；前面的是元件庫定義（如理想反相器）
        if not tok or tok[0][0] in "*.":
            continue
        k = tok[0][0].upper()
        if k == "M":
            devs.append((tok[5].lower()[:1] + "mos", [("D", tok[1]), ("G", tok[2]), ("S", tok[3]), ("B", tok[4])]))
        elif k == "Q":
            devs.append((tok[4].lower(), [("C", tok[1]), ("B", tok[2]), ("E", tok[3])]))
        elif k in "RCL":
            devs.append((k, [("x", tok[1]), ("x", tok[2])]))
        elif k == "X" and "opamp" in [x for x in tok if "=" not in x][-1].lower():
            tk = [x for x in tok if "=" not in x]      # 運放：型號前三個是 in+ in- out（編輯器匯出時前面多帶電源腳）
            devs.append(("opamp", list(zip("+-o", tk[-4:-1]))))
        elif k == "X":
            tk = [x for x in tok if "=" not in x]      # 去掉參數；電源腳不算（編輯器匯出會多帶 VDD VSS）
            devs.append((tk[-1].lower(), [(str(i), n) for i, n in enumerate(n for n in tk[1:-1] if n.lower() not in FIX)]))
        elif k in "IVD":
            devs.append((k, [("p", tok[1]), ("n", tok[2])]))
    col = {}
    for _t, pins in devs:
        for _r, n in pins:
            col[n] = FIX.get(n.lower(), "net")
    for _ in range(len(col) + 2):
        dc = [typ + "|" + ",".join(sorted("%s:%s" % (r, col[n]) for r, n in pins)) for typ, pins in devs]
        new = {}
        for n in col:
            around = sorted("%s@%s" % (r, dc[i]) for i, (_t, pins) in enumerate(devs) for r, m in pins if m == n)
            new[n] = FIX.get(n.lower()) or str(hash((col[n], tuple(around))))
        if len(set(new.values())) == len(set(col.values())):
            col = new
            break
        col = new
    return sorted(typ + "|" + ",".join(sorted("%s:%s" % (r, col[n]) for r, n in pins)) for typ, pins in devs)


def world(at, local, rot, mirror):
    x, y = local
    for _ in range((rot // 90) % 4):
        x, y = -y, x
    if mirror in ("horizontal", "both"):
        x = -x
    if mirror in ("vertical", "both"):
        y = -y
    return at[0] + x, at[1] + y


def J(r, n=700):
    return json.dumps(r, ensure_ascii=False)[:n]


def must(r, what):
    if isinstance(r, dict) and r.get("ok") is False:
        raise RuntimeError("%s: %s" % (what, J(r.get("error", r), 1500)))
    return r


def draw(plan_path):
    plan = json.load(open(plan_path, encoding="utf-8"))
    name = plan["name"]
    deck = os.path.join(HERE, plan["deck"])
    devs, ports, names = parse_deck(deck)
    ws = os.path.join(HERE, "ws", name)
    if os.path.isdir(ws):
        shutil.rmtree(ws)          # 每次從空白重畫，結果只由 plan 決定
    out = os.path.join(HERE, "out")
    os.makedirs(out, exist_ok=True)
    gnd_nets = set(plan.get("gnd_nets", ["0", "gnd", "vss"]))
    vdd_nets = set(plan.get("vdd_nets", ["VDD", "vdd", "VCC", "vcc"]))
    with Session(ws, new=True) as s:
        # 1. 放元件與埠
        acts = []
        for d in devs:
            spec = plan["parts"][d["ref"]]
            x, y = spec[0], spec[1]
            rot = spec[2] if len(spec) > 2 else 0
            mir = spec[3] if len(spec) > 3 else "none"
            a = {"kind": "place-component", "symbol": d["symbol"], "id": d["ref"], "reference": d["ref"],
                 "position": {"x": x, "y": y}, "rotation": rot, "mirror": mir}
            if d.get("signs"):
                a["parameters"] = {"signA": d["signs"][0], "signB": d["signs"][1]}
            acts.append(a)
        pid = lambda key: "P_" + "".join(c if (c.isalnum() or c in "_-") else "_" for c in key)
        for key, spec in plan.get("ports", {}).items():
            net = key.split("@")[0]
            x, y = spec[0], spec[1]
            mir = spec[2] if len(spec) > 2 else "none"
            rot = spec[3] if len(spec) > 3 else 0      # 90＝引線朝下、270＝朝上
            if len(spec) > 4:
                names[net] = spec[4]
            acts.append({"kind": "place-component", "symbol": "port", "id": pid(key),
                         "reference": re.sub(r"\W", "_", names.get(net, net)),
                         "position": {"x": x, "y": y}, "mirror": mir, "rotation": rot})
        must(s.call("circuit_place", {"actions": acts}), "place")
        flow = any(d.get("block") for d in devs)
        for d in devs:
            if not d.get("block"):
                continue
            sf = {}
            if d.get("formula"):
                sf["formula"] = d["formula"]
            if d["ref"] in plan.get("body", {}):
                sf["bodyWidth"], sf["bodyHeight"] = plan["body"][d["ref"]]
            if sf:
                sf.update({"kind": "set-signal-flow", "target": {"kind": "instance", "id": d["ref"]}})
                must(s.call("apply_actions", {"actions": [sf]}), "formula " + d["ref"])
        hide = [d["ref"] for d in devs if d.get("block") and d["ref"] not in names]
        if hide:
            must(s.call("apply_actions", {"actions": [{"kind": "set-instance-display", "instanceIds": hide, "showReference": False}]}), "hide refs")
        # 2. 讀腳位（絕對座標自己算：localPosition 轉向後加原點）
        ids = [d["ref"] for d in devs] + [pid(n) for n in plan.get("ports", {})]
        info = must(s.call("inspect", {"target": {"kind": "pins", "instanceIds": ids}}), "pins")
        pinpos = {}
        for inst in info["instances"]:
            pl = inst["placement"]
            for p in inst["pins"]:
                lp = p["localPosition"]
                pinpos[(inst["id"], p["name"])] = world((pl["position"]["x"], pl["position"]["y"]),
                                                        (lp["x"], lp["y"]), pl["rotation"], pl["mirror"])
        for d in devs:                       # 方框會被字撐大，腳位以編輯器回報的實際接點為準
            if d.get("block"):
                o = must(s.call("inspect", {"target": {"kind": "object", "id": d["ref"]}}), "object " + d["ref"])
                for p in o["pins"]:
                    cp = p["connection"]["contactPoint"]
                    pinpos[(d["ref"], p["name"])] = (cp["x"], cp["y"])
        for k_, want_ in plan.get("expect_pins", {}).items():      # 方框被字撐大時，腳位會跟位置表算的不一樣
            ref_, pin_ = k_.split(".")
            got = pinpos[(ref_, pin_)]
            if tuple(want_) != tuple(got):
                raise RuntimeError("%s 的方框比位置表設定的寬：%s 腳實際在 %s、位置表以為在 %s。把 p.block(..., w=) 設成 %d"
                                   % (ref_, pin_, list(got), want_, 2 * (abs(got[0] - plan["parts"][ref_][0]) - 10)))
        # 3. 整理每條 net 的腳位
        nets = {}
        for d in devs:
            for pin, net in d["pins"].items():
                nets.setdefault(net, []).append((d["ref"], pin))
        label_conns = []
        for key in plan.get("ports", {}):
            if "@" in key:                       # 標籤埠：只接指定的那支腳，並把那支腳從走線名單拿掉
                net, att = key.split("@")
                ref_, pin_ = att.split(".")
                nets[net].remove((ref_, pin_))
                label_conns.append((pid(key), ref_, pin_))
            else:
                nets.setdefault(key, []).append((pid(key), "P"))
        # 4. 電源軌：軌在 y=rail_y，每個 VDD 腳垂直接上去
        log = []
        rail = plan.get("vdd_rail")
        vdd_pins = [pp for n in nets if n in vdd_nets for pp in nets[n]]
        if rail and vdd_pins:
            must(s.call("apply_actions", {"actions": [{"kind": "add-power-rail", "name": plan.get("vdd_name", "VDD"),
                        "start": {"x": rail["x"][0], "y": rail["y"]}, "end": {"x": rail["x"][1], "y": rail["y"]}}]}), "rail")
            acts = [{"kind": "connect", "from": {"kind": "pin", "instance": {"kind": "instance", "id": i}, "pin": p},
                     "to": {"kind": "wire-at", "point": {"x": pinpos[(i, p)][0], "y": rail["y"]}}} for i, p in vdd_pins]
            r = s.call("circuit_wire", {"actions": acts})
            log.append(("vdd taps", r.get("ok"), J(r, 600)))
        # 4.5 其他電源軌（例：負電源 VEE 畫在最下面）：plan["extra_rails"] = [{"net": "VEE", "y": .., "x": [x0, x1]}]
        for er in plan.get("extra_rails", []):
            pins_ = [pp for n in nets if n.lower() == er["net"].lower() for pp in nets[n]]
            must(s.call("apply_actions", {"actions": [{"kind": "add-power-rail", "name": er["net"],
                        "start": {"x": er["x"][0], "y": er["y"]}, "end": {"x": er["x"][1], "y": er["y"]}}]}), "rail " + er["net"])
            acts = [{"kind": "connect", "from": {"kind": "pin", "instance": {"kind": "instance", "id": i}, "pin": p},
                     "to": {"kind": "wire-at", "point": {"x": pinpos[(i, p)][0], "y": er["y"]}}} for i, p in pins_]
            r = s.call("circuit_wire", {"actions": acts})
            log.append(("rail " + er["net"], r.get("ok"), J(r, 600)))
            vdd_nets |= set(n for n in nets if n.lower() == er["net"].lower())      # 之後不再當訊號網走線
        # 5. 接地符號：每個接地腳下方放一個（drop＝往下幾格）
        drop = plan.get("gnd_drop", 20)
        gnd_pins = [pp for n in nets if n in gnd_nets for pp in nets[n]]
        if gnd_pins:
            acts = []
            for k, (i, p) in enumerate(gnd_pins):
                x, y = pinpos[(i, p)]
                gx, gy = plan.get("gnd_at", {}).get("%s.%s" % (i, p), [x, y + drop])   # 預設在腳正下方；可指定位置
                acts.append({"kind": "place-component", "symbol": "ground", "id": "G%d" % k,
                             "pinAnchor": {"pinName": "0", "position": {"x": gx, "y": gy}}})
            must(s.call("circuit_place", {"actions": acts}), "ground")
            acts = [{"kind": "connect", "from": {"kind": "pin", "instance": {"kind": "instance", "id": i}, "pin": p},
                     "to": {"kind": "pin", "instance": {"kind": "instance", "id": "G%d" % k}, "pin": "0"}}
                    for k, (i, p) in enumerate(gnd_pins)]
            r = s.call("circuit_wire", {"actions": acts})
            log.append(("gnd leads", r.get("ok"), J(r, 600)))
        # 5.5 自由畫線（兩個自由點之間，編輯器照畫不檢查）：只給「貫穿閘極」這類他明講允許的例外用
        for seg in plan.get("free_wires", []):
            (x0, y0), (x1, y1) = seg
            r = s.call("circuit_wire", {"actions": [{"kind": "connect", "from": {"kind": "point", "x": x0, "y": y0},
                                                     "to": {"kind": "point", "x": x1, "y": y1}}]})
            log.append(("free wire", r.get("ok"), J(r, 600)))
        # 5.7 指定路徑的線：從某支腳出發，照 via 轉折，停在一個點（之後 route-net 的幹線或別的線會接上它）。
        #     用在編輯器自己繞不過去的地方（例：回授線要從運放下方繞回 IN-）。
        late_paths = [p_ for p_ in plan.get("paths", []) if not isinstance(p_["to"][0], str)]
        for p_ in plan.get("paths", []):          # 自己指定路徑的腳一律不交給 route-net
            for n in nets:
                if tuple(p_["from"]) in nets[n]:
                    nets[n].remove(tuple(p_["from"]))
        for pth in [p_ for p_ in plan.get("paths", []) if isinstance(p_["to"][0], str)]:
            ref_, pin_ = pth["from"]
            end = pth["to"]
            to = ({"kind": "pin", "instance": {"kind": "instance", "id": end[0]}, "pin": end[1]} if isinstance(end[0], str)
                  else {"kind": "point", "x": end[0], "y": end[1]})
            a = {"kind": "connect", "from": {"kind": "pin", "instance": {"kind": "instance", "id": ref_}, "pin": pin_}, "to": to}
            if pth.get("via"):
                a["via"] = [{"x": x, "y": y} for x, y in pth["via"]]
            r = s.call("circuit_wire", {"actions": [a]})
            log.append(("path %s.%s" % (ref_, pin_), r.get("ok"), J(r, 600)))
        if label_conns:
            acts = [{"kind": "connect", "from": {"kind": "pin", "instance": {"kind": "instance", "id": a}, "pin": "P"},
                     "to": {"kind": "pin", "instance": {"kind": "instance", "id": r_}, "pin": p_}} for a, r_, p_ in label_conns]
            r = s.call("circuit_wire", {"actions": acts})
            log.append(("labels->pins", r.get("ok"), J(r, 600)))
        # 6. 訊號網：照 plan["order"]（沒給就照腳位數少的先）讓編輯器 route-net
        sig = [n for n in nets if n not in gnd_nets and n not in vdd_nets and len(nets[n]) >= 2]
        order = plan.get("order") or sorted(sig, key=lambda n: len(nets[n]))
        order += [n for n in sig if n not in order]
        trunks = plan.get("trunks", {})
        for n in order:
            a = {"kind": "route-net", "target": {"kind": "pins", "pins": [{"instanceId": i, "pinName": p} for i, p in nets[n]]}}
            if n in trunks:
                (x0, y0), (x1, y1) = trunks[n]
                a["trunk"] = {"start": {"x": x0, "y": y0}, "end": {"x": x1, "y": y1}}
            r = s.call("apply_actions", {"actions": [a]})
            log.append(("net " + n, r.get("ok"), J(r, 700)))
        for pth in late_paths:
            ref_, pin_ = pth["from"]
            a = {"kind": "connect", "from": {"kind": "pin", "instance": {"kind": "instance", "id": ref_}, "pin": pin_},
                 "to": {"kind": "wire-at", "point": {"x": pth["to"][0], "y": pth["to"][1]}}}
            if pth.get("via"):
                a["via"] = [{"x": x, "y": y} for x, y in pth["via"]]
            r = s.call("circuit_wire", {"actions": [a]})
            log.append(("path %s.%s" % (ref_, pin_), r.get("ok"), J(r, 600)))
        # 7. 顯示名（.name）
        def plain(ref):                      # M7 預設就畫成 M_7，不必再設
            m = re.match(r"^([A-Za-z])(\w+)$", ref)
            return "%s_%s" % (m.group(1), m.group(2)) if m else ref
        acts = [{"kind": "set-display-alias", "target": {"kind": "instance", "id": d["ref"]}, "text": names[d["ref"]]}
                for d in devs if d["ref"] in names and names[d["ref"]] != plain(d["ref"])]
        if acts:
            r = s.call("apply_actions", {"actions": acts})
            log.append(("aliases", r.get("ok"), J(r.get("error", ""), 400)))
        # 8. 出圖、驗證
        svg = os.path.join(out, name + ".svg")
        # 7.5 標籤避開線與元件（plan["label_side"]：{"M5": "bottom"} 指定某顆的標籤先試哪一側）
        r = s.call("apply_actions", {"actions": [{"kind": "arrange-labels", "instanceIds": [d["ref"] for d in devs]}]})
        log.append(("labels", r.get("ok"), J(r, 400)))
        for ref_, side in plan.get("label_side", {}).items():
            r = s.call("apply_actions", {"actions": [{"kind": "arrange-labels", "instanceIds": [ref_], "side": side}]})
            log.append(("label " + ref_, r.get("ok"), J(r, 400)))
        for ref_, (lx, ly) in plan.get("label_at", {}).items():      # 指定某顆標籤的中心位置
            r = s.call("apply_actions", {"actions": [{"kind": "move-annotation", "annotationId": "instance-label-" + ref_,
                                                      "position": {"x": lx, "y": ly}, "alignment": "middle"}]})
            log.append(("label@ " + ref_, r.get("ok"), J(r, 400)))
        if not flow:
            rr = save_render(s, svg, os.path.join(out, name + ".png"))
            ref = reference_spice(devs, ports, re.sub(r"\W", "_", name))
            open(os.path.join(ws, "reference.sp"), "w", encoding="utf-8", newline="\n").write(ref)
            v = s.call("verify", {"expectedNetlist": {"text": ref, "compare": {"parameters": False, "portOrder": False, "declarations": False, "bindings": False}}})
            diag = s.call("inspect", {"target": {"kind": "diagnostics"}})
            exported = (s.call("netlist_code", {"action": "read"}).get("netlist") or {}).get("text") or ""
            open(os.path.join(out, name + ".exported.sp"), "w", encoding="utf-8", newline=chr(10)).write(exported)
            merged, seen = ref, {}
            for net in plan.get("ports", {}):       # 同顯示名＝同一條 net
                if "@" in net:
                    continue
                disp = names.get(net, net)
                if disp in seen:
                    merged = re.sub(r"(?<![\w-])%s(?![\w-])" % re.escape(net), seen[disp], merged)
                else:
                    seen[disp] = net
            same = signature(exported) == signature(merged)
            shutil.copy2(os.path.join(ws, "project.icproj.json"), os.path.join(out, name + ".icproj.json"))
    if flow:
        n_arrow, n_want = flow_arrows(ws, devs, plan)
        log.append(("arrows", n_arrow == n_want, "箭頭 %d 個，輸入端共 %d 個（有輸入端的線不是停在腳上：那支腳改用 p.wire 從來源接過去）" % (n_arrow, n_want)))
        same, why = flow_connectivity(ws, devs, plan)
        if why:
            log.append(("connectivity", False, why))
        with Session(ws) as s:
            rr = save_render(s, svg, os.path.join(out, name + ".png"))
            diag = s.call("inspect", {"target": {"kind": "diagnostics"}})
        skip = ("MISSING_DEVICE_DEFINITION", "GENERATED_NET_NAME")      # 方塊符號本來就沒有 netlist 定義
        items = [it for it in diag.get("items", []) if it["code"] not in skip]
        diag = {"items": items, "counts": {"errors": sum(1 for it in items if it.get("severity") == "error"),
                                           "warnings": sum(1 for it in items if it.get("severity") == "warning")}}
        v = {"comparison": {"summary": "（方塊圖不匯出 netlist，改比對專案檔的接線）"}}
        shutil.copy2(os.path.join(ws, "project.icproj.json"), os.path.join(out, name + ".icproj.json"))
    print("== %s" % name)
    for what, ok, err in log:
        print("  %-12s %s %s" % (what, "ok" if ok else "FAIL", err if not ok else ""))
    codes = {}
    for it in diag.get("items", []):
        codes[it["code"]] = codes.get(it["code"], 0) + 1
    print("  diagnostics:", diag.get("counts"), codes)
    print("  upstream verify:", (v.get("comparison") or {}).get("summary"))
    print("  NETLIST EQUIVALENT (own check):", same)
    print("  png:", os.path.join(out, name + ".png"))
    return log, diag, same


if __name__ == "__main__":
    draw(sys.argv[1])
