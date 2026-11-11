# 三輸入 NOR：PMOS 三顆串聯在上、NMOS 三顆並聯在下
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("nor3-cmos", "../toolkit/decks/new/nor3-cmos.cir")
for ref, y, net in [("MP1", 110, "a"), ("MP2", 190, "b"), ("MP3", 270, "c")]:
    p.mos(ref, 300, y, "L")
    p.label(net, ref, "G")
for ref, col, net in [("MN1", 200, "a"), ("MN2", 300, "b"), ("MN3", 400, "c")]:
    p.mos(ref, col, 380, "L")
    p.label(net, ref, "G")
p.hline("y", 330)
p.port("y", 440, 330, "R")
p.rail(50)
p.draw()
