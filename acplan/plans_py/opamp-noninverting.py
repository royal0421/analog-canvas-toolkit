# 非反相放大器：輸入接 IN+（畫在上面），回授電阻在運放下方
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("opamp-noninverting", "../toolkit/decks/new/opamp-noninverting.cir")
p.opamp("XOA", 300, 200, plus="top")
p.two("R2", 300, 270, horizontal=True)       # 回授電阻
p.two("R1", 240, 320)                        # 接地電阻
p.port("in", 220, 190, "L")
p.port("out", 390, 200, "R")
p.vline("x", 240, 210, 300)
p.vline("out", 350, 200, 270)
p.draw()
