# 共源級＋電流源負載
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("cs-active-load", "../toolkit/decks/new/cs-active-load.cir")
p.stack(200, "L", [("M2", 110), ("M1", 210)])
p.port_pin("vb", "M2", "G")
p.port_pin("in", "M1", "G")
p.port("out", 240, 160, "R")
p.rail(50)
p.draw()
