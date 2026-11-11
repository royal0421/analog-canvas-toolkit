# AOI21：上面 PMOS（A、B 並聯後串 C），下面 NMOS（A、B 串聯，再與 C 並聯）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("aoi21-cmos", "../toolkit/decks/new/aoi21-cmos.cir")
for ref, col, y, net in [("MP1", 250, 110, "a"), ("MP2", 350, 110, "b"), ("MP3", 300, 210, "c"),
                         ("MN1", 250, 330, "a"), ("MN2", 250, 410, "b"), ("MN3", 350, 330, "c")]:
    p.mos(ref, col, y, "L")
    p.label(net, ref, "G")
p.hline("p", 150)
p.hline("y", 280)
p.port("y", 390, 280, "R")
p.rail(50)
p.draw()
