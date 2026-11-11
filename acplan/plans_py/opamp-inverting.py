# 反相放大器（運放＋兩顆電阻）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("opamp-inverting", "../toolkit/decks/new/opamp-inverting.cir")
p.place("XOA", 300, 200)                     # 運放：IN- 在左上 (260,190)、IN+ 在左下 (260,210)、OUT 在右 (330,200)
p.two("R1", 200, 190, horizontal=True)       # 輸入電阻：跟 IN- 同一條橫線
p.two("R2", 300, 130, horizontal=True)       # 回授電阻：在運放正上方
p.ground("XOA", "IN+", 240, 240)             # IN+ 接地：往左拉出再往下
p.port("in", 150, 190, "L")
p.port("out", 390, 200, "R")
p.vline("x", 240, 130, 190)                  # 虛接地節點：往上接回授電阻
p.vline("out", 350, 130, 200)                # 輸出：往上接回授電阻另一端
p.draw()
