# 共閘級＋電流源負載，輸入從源極進
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("cg-stage-current-load", "../toolkit/decks/new/cg-stage-current-load.cir")
p.two("I1", 200, 110)
p.mos("M1", 200, 210, "L")
p.two("RS", 200, 300)
p.port_pin("vb", "M1", "G")
p.port("in", 160, 250, "L")
p.port("out", 240, 160, "R")
p.rail(50)
p.draw()
