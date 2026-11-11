# 反相 Schmitt trigger：正回授分壓接到 IN+
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("schmitt-trigger", "../toolkit/decks/new/schmitt-trigger.cir")
p.opamp("XOA", 300, 200)
p.two("R1", 300, 270, horizontal=True, first="R")
p.two("R2", 240, 320)
p.port("in", 220, 190, "L")
p.port("out", 390, 200, "R")
p.vline("p", 240, 210, 300)
p.vline("out", 350, 200, 270)
p.draw()
