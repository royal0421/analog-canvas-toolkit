# Colpitts 振盪器：電感在集極上方，C1／C2 分壓在右邊，基極分壓偏壓在左邊
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("colpitts-osc", "../toolkit/decks/new/colpitts-osc.cir", vdd_name="VCC")
p.two("L1", 300, 120)
p.bjt("Q1", 300, 220, "L")
p.two("RE", 300, 310)
p.two("C1", 380, 210)
p.two("C2", 380, 290)
p.two("R1", 200, 120)
p.two("R2", 200, 300)
p.two("CB", 140, 300)
p.port("out", 420, 170, "R")
p.hline("out", 170)
p.hline("e", 250)
p.hline("b", 220)
p.rail(50)
p.draw()
