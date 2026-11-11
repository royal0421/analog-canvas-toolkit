# 半波整流＋濾波電容＋負載
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("half-wave-rectifier", "../toolkit/decks/new/half-wave-rectifier.cir")
p.place("D1", 200, 150)
p.two("C1", 260, 200)
p.two("RL", 320, 200)
p.port("in", 150, 150, "L")
p.port("out", 360, 150, "R")
p.hline("out", 150)
p.draw()
