# 取樣保持：NMOS 開關橫放（閘極朝上接 CK）→ C_H 接地 → 運放接成隨耦器（回授從上方繞回 IN-）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("sample-hold", "../toolkit/decks/new/sample-hold.cir")
p.place("M1", 200, 160, 90, "horizontal")    # 轉 90 度＋左右鏡像：D（in）在左、S（h）在右、閘極在上
p.opamp("XOA", 320, 160)                     # IN- 在上（接回授）、IN+ 在下（接 h）
p.two("CH", 250, 200)
p.port("in", 150, 170, "L")
p.port("clk", 200, 110, "U")
p.hline("h", 170)
p.wire("XOA", "IN-", [(270, 150), (270, 110)], (380, 110))   # 隨耦器回授：從運放上方繞到輸出
p.vline("out", 380, 110, 160)
p.port("out", 410, 160, "R")
p.draw()
