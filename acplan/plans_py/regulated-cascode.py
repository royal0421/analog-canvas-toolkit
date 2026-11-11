# Regulated cascode：主支路在右一疊，輔助放大器 M3 在左，閘極朝右接節點 s
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("regulated-cascode", "../toolkit/decks/new/regulated-cascode.cir")
p.two("RD", 300, 110)
p.stack(300, "L", [("M2", 200), ("M1", 340)])
p.two("I1", 190, 130)
p.mos("M3", 190, 250, "R")
p.port_pin("in", "M1", "G")
p.port("out", 340, 160, "R")
p.rail(50, 160, 330)
p.draw()
