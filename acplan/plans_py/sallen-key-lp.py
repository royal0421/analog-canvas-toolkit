# Sallen-Key 低通：兩顆電阻串在輸入路徑，C1 從中間節點跨到輸出，運放接成隨耦器
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("sallen-key-lp", "../toolkit/decks/new/sallen-key-lp.cir")
p.opamp("XOA", 400, 200, plus="top")
p.two("RR1", 190, 190, horizontal=True)
p.two("RR2", 290, 190, horizontal=True)
p.two("CC2", 310, 240)
p.two("CC1", 340, 120, horizontal=True)
p.port("in", 130, 190, "L")
p.port("out", 490, 200, "R")
p.vline("n1", 240, 120, 190)
p.vline("out", 450, 120, 270)
p.wire("XOA", "IN-", [(350, 210), (350, 270)], (450, 270))             # 隨耦器的回授：從運放下方繞到輸出
p.draw()
