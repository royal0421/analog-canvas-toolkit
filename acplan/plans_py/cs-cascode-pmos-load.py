# 疊接放大器＋疊接 PMOS 電流源負載（單邊一疊四顆）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("cs-cascode-pmos-load", "../toolkit/decks/new/cs-cascode-pmos-load.cir")
p.stack(200, "L", [("M4", 110), ("M3", 200), ("M2", 300), ("M1", 390)])
for net, ref in [("vb3", "M4"), ("vb2", "M3"), ("vb1", "M2"), ("in", "M1")]:
    p.port_pin(net, ref, "G")
p.port("out", 240, 250, "R")
p.rail(50)
p.draw()
