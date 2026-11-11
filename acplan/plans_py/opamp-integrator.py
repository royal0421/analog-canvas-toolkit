# 反相積分器：回授換成電容
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("opamp-integrator", "../toolkit/decks/new/opamp-integrator.cir")
p.opamp("XOA", 300, 200)
p.two("R1", 200, 190, horizontal=True)
p.two("C1", 300, 130, horizontal=True)
p.ground("XOA", "IN+", 240, 240)
p.port("in", 150, 190, "L")
p.port("out", 390, 200, "R")
p.vline("x", 240, 130, 190)
p.vline("out", 350, 130, 200)
p.draw()
