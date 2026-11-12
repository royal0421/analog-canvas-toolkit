# 慣例檢查器的自測：對已核可的 Miller 故意弄壞四種，每種都要被抓到；原版要 0 條。
from acplan import Plan

def miller(pair_gates="out", tail=230, row2=210, lead=30, mirror_y=110):
    p = Plan("t", "../toolkit/decks/new/two-stage-miller.cir")
    p.pair("M3", "M4", cols=(180, 290), y=mirror_y, gates="in")
    p.pair("M1", "M2", cols=(180, 290), y=row2, gates=pair_gates)
    p.mos("M5", tail, 290); p.mos("M6", 410, 110); p.mos("M7", 410, 290)
    p.two("CC", 350, 160, horizontal=True); p.two("CL", 460, 210)
    p.port_pin("inn", "M1", "G", lead=lead); p.port_pin("inp", "M2", "G"); p.port_pin("vb", "M5", "G", lead=40)
    p.port("out", 510, 160, "R"); p.gate_through("M5", "M7"); p.hline("tail", 250); p.hline("out", 160); p.rail(50)
    return p.check()

cases = [("原版", {}, 0), ("輸入對閘極朝內", {"pair_gates": "in"}, 1), ("尾電流源偏一邊", {"tail": 200}, 1),
         ("輸入對離負載太近", {"row2": 160}, 1), ("輸入埠引線 90", {"lead": 90}, 1)]
ok = True
for name, kw, want in cases:
    bad = miller(**kw)
    good = (len(bad) == 0) if want == 0 else (len(bad) >= 1)
    ok &= good
    print("%s %s -> %s" % ("OK  " if good else "MISS", name, bad))
def lc(gates):
    p = Plan("t2", "../toolkit/decks/new/lc-oscillator-xcoupled.cir")
    p.two("L1", 200, 140); p.two("L2", 320, 140); p.two("C1", 120, 240); p.two("C2", 400, 240)
    p.pair("M1", "M2", cols=(200, 320), y=280, gates=gates); p.two("ISS", 260, 350)
    p.port("outp", 90, 190, "L"); p.port("outn", 430, 210, "R"); p.hline("outp", 190, 90, 290); p.hline("outn", 210, 230, 430)
    return p.check()
for name, g, want in [("交叉耦合對閘極朝內", "in", 0), ("交叉耦合對閘極朝外", "out", 1)]:
    bad = lc(g)
    good = (len(bad) == 0) if want == 0 else (len(bad) >= 1)
    ok &= good
    print("%s %s -> %s" % ("OK  " if good else "MISS", name, bad))
def loop(h_y=200, flip=True):
    p = Plan("t3", "../toolkit/decks/flow/feedback-loop.cir")
    p.adder("XS1", 180, 200); p.block("XH1", 290, h_y); p.block("XB1", 290, 290, flip=flip)
    p.port("x", 100, 200, "L"); p.port("y", 440, h_y, "R"); p.hline("y", h_y, 320, 440)
    p.wire("XB1", "A", [(380, 290)], (380, h_y)); p.wire("XB1", "Y", [(180, 290)], ("XS1", "B"))
    return p.check()
def chain(order=(190, 290)):
    p = Plan("t4", "../toolkit/decks/flow/receiver-chain.cir")
    p.block("XLNA", order[0], 200); p.adder("XMIX", order[1], 200); p.block("XLPF", 390, 200); p.block("XADC", 510, 200)
    p.port("rf", order[0] - 90, 200, "L"); p.port("lo", order[1], 270, "D"); p.port("dout", 620, 200, "R")
    return p.check()
for name, bad, want in [("方塊圖原版", loop(), 0), ("方塊圖：方框差 10 沒對齊", loop(h_y=210), 1),
                        ("訊號鏈原版", chain(), 0), ("訊號鏈：主路徑由右往左", chain(order=(290, 190)), 1)]:
    good = (len(bad) == 0) if want == 0 else (len(bad) >= 1)
    ok &= good
    print("%s %s -> %s" % ("OK  " if good else "MISS", name, bad))
print("SELFTEST", "PASS" if ok else "FAIL")
