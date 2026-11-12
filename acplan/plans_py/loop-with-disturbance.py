# 有干擾的回授系統：R → 加法點 → C(s) → P(s) → 加法點（干擾 D 從上面進）→ Y；H(s) 在下面回授
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("loop-with-disturbance", "../toolkit/decks/flow/loop-with-disturbance.cir")
p.adder("XS1", 180, 200)
p.block("XC", 280, 200)
p.block("XP", 390, 200)
p.adder("XS2", 490, 200, b="U")             # 干擾從上面進
p.block("XH", 340, 300, flip=True)
p.port("r", 100, 200, "L")
p.port("d", 490, 130, "U")
p.port("y", 640, 200, "R")
p.hline("y", 200, 510, 640)
p.wire("XH", "A", [(570, 300)], (570, 200))
p.wire("XH", "Y", [(180, 300)], ("XS1", "B"))
p.draw()
