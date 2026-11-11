# 精密整流（superdiode）：二極體接在運放輸出，回授從二極體後面拉回 IN-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("precision-rectifier", "../toolkit/decks/new/precision-rectifier.cir")
p.opamp("XOA", 300, 200, plus="top")
p.place("D1", 370, 200)                      # 二極體橫放：陽極在左
p.two("RL", 450, 250)
p.port("in", 220, 190, "L")
p.port("out", 490, 200, "R")
p.hline("out", 200, 390, 450)
p.wire("XOA", "IN-", [(240, 210), (240, 260), (410, 260)], (410, 200))   # 回授線：從運放下方繞回 IN-
p.draw()
