# 三輸入 NAND：PMOS 三顆並聯在上、NMOS 三顆串聯在下；每個閘極各掛輸入標籤
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("nand3-cmos", "../toolkit/decks/new/nand3-cmos.cir")
for ref, col, net in [("MP1", 200, "a"), ("MP2", 300, "b"), ("MP3", 400, "c")]:
    p.mos(ref, col, 110, "L")
    p.label(net, ref, "G")
for ref, y, net in [("MN1", 220, "a"), ("MN2", 300, "b"), ("MN3", 380, "c")]:
    p.mos(ref, 300, y, "L")
    p.label(net, ref, "G")
p.hline("y", 160)
p.port("y", 440, 160, "R")
p.rail(50)
p.draw()
