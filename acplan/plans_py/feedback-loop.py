# 負回授系統方塊圖：X → 加法點 → A(s) → Y；Y 經 β 回授到加法點下方（−）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("feedback-loop", "../toolkit/decks/flow/feedback-loop.cir")
p.adder("XS1", 180, 200)                    # 主路徑一列：y=200
p.block("XH1", 290, 200)
p.block("XB1", 290, 290, flip=True)         # 回授路徑在下面一列，訊號由右往左
p.port("x", 100, 200, "L")
p.port("y", 440, 200, "R")
p.hline("y", 200, 320, 440)                 # 輸出線；回授從線上 x=380 分出去
p.wire("XB1", "A", [(380, 290)], (380, 200))
p.wire("XB1", "Y", [(180, 290)], ("XS1", "B"))
p.draw()
