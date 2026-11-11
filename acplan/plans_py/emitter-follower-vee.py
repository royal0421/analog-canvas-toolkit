# 射極隨耦器，電流源接負電源 VEE
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("emitter-follower-vee", "../toolkit/decks/new/emitter-follower-vee.cir", vdd_name="VCC")
p.bjt("Q1", 200, 120, "L")
p.two("I1", 200, 230)
p.two("RL", 270, 220)
p.port_pin("in", "Q1", "B")
p.port("out", 310, 170, "R")
p.hline("out", 170)
p.rail(50)
p.rail_low("VEE", 300, 170, 300)
p.draw()
