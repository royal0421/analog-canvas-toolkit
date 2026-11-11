# 反相加法器：兩顆輸入電阻接到虛接地節點，回授電阻在運放上方
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("summing-amp", "../toolkit/decks/new/summing-amp.cir")
p.opamp("XOA", 300, 200)                     # IN- (260,190)、IN+ (260,210)、OUT (330,200)
p.two("R1", 200, 150, horizontal=True)       # V_1 路徑在上
p.two("R2", 200, 190, horizontal=True)       # V_2 路徑跟 IN- 同一條橫線
p.two("RF", 300, 110, horizontal=True)       # 回授電阻在運放正上方
p.ground("XOA", "IN+", 240, 240)
p.port("in1", 150, 150, "L")
p.port("in2", 150, 190, "L")
p.port("out", 390, 200, "R")
p.vline("x", 240)                            # 虛接地節點：直幹線串起 R1、R2、RF、IN-
p.vline("out", 350, 110, 200)
p.draw()
