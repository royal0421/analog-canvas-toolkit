# 帶前饋的回授系統：X → 加法點（−β）→ A(s) → 加法點 → Y；X 另經 F(s) 從上方前饋到第二個加法點；Y 經 β 回授
# 抄 feedback-loop＋loop-with-disturbance（第二個加法點 B 從上面進）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("flowtest-ff", "../toolkit/decks/flow/flowtest-ff.cir")
p.adder("XS1", 180, 200)
p.block("XA", 290, 200)
p.adder("XS2", 400, 200, b="U")
p.block("XF", 290, 110)                      # 前饋路徑在上面一列，訊號由左往右
p.block("XB", 290, 290, flip=True)           # 回授路徑在下面一列
p.port("x", 100, 200, "L")
p.port("y", 570, 200, "R")
p.hline("x", 200, 100, 160)
p.wire("XF", "A", [(130, 110)], (130, 200))
p.wire("XF", "Y", [(400, 110)], ("XS2", "B"))
p.hline("y", 200, 420, 570)
p.wire("XB", "A", [(500, 290)], (500, 200))
p.wire("XB", "Y", [(180, 290)], ("XS1", "B"))
p.draw()
