# 共射級：分壓偏壓＋射極旁路電容＋輸入輸出耦合電容
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("ce-bypassed", "../toolkit/decks/new/ce-bypassed.cir", vdd_name="VCC")
p.two("R1", 200, 110)
p.two("R2", 200, 280)
p.bjt("Q1", 300, 200, "L")
p.two("RC", 300, 110)
p.two("RE", 300, 280)
p.two("CE", 360, 280)                        # 旁路電容與 R_E 並聯，畫在右邊
p.two("CIN", 150, 200, horizontal=True)
p.two("COUT", 360, 160, horizontal=True)
p.port("in", 100, 200, "L")
p.port("out", 410, 160, "R")
p.hline("b", 200)
p.hline("e", 240)
p.rail(50)
p.draw()
