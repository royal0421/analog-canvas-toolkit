# CMOS 反相器：兩個閘極用一條直線相連，輸入埠掛在直線中點
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("cmos-inverter", "../toolkit/decks/new/cmos-inverter.cir")
p.stack(200, "L", [("M2", 110), ("M1", 210)])
p.two("CL", 270, 210)
p.vline("in", 170)
p.port("in", 140, 160, "L")
p.hline("out", 160)
p.port("out", 310, 160, "R")
p.rail(50)
p.draw()
