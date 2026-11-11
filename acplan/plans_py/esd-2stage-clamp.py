# RC 觸發的 ESD power clamp：RC 偵測 → 兩級反相器 → 大 NMOS；PAD 經二極體接到 VDD
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("esd-2stage-clamp", "../toolkit/decks/new/esd-2stage-clamp.cir")
p.two("RRC", 180, 110)
p.two("CCC", 180, 230)
p.stack(280, "L", [("MMP1", 110), ("MMN1", 230)])
p.stack(380, "L", [("MMP2", 110), ("MMN2", 230)])
p.mos("MMBIG", 480, 170, "L")
for rot in (90, 270):                        # 二極體直放，陰極朝上接 VDD
    p.place("DDESD", 560, 130, rot)
    if p.pin("DDESD", "K")[1] < p.pin("DDESD", "A")[1]:
        break
p.port("pad", 560, 180, "D")
p.hline("rc", 170)
p.hline("g1", 170)
p.hline("g2", 170)
p.rail(50, 150, 590)
p.route_order("rc", "g1", "g2")
p.draw()
