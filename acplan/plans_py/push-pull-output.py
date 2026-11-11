# Class-B 推挽輸出級：NPN 在上、PNP 在下，兩個基極用直線相連
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("push-pull-output", "../toolkit/decks/new/push-pull-output.cir", vdd_name="VCC")
p.bjt("Q1", 250, 130, "L")
p.bjt("Q2", 250, 230, "L")
p.two("RL", 350, 230)
p.vline("in", 220)
p.port("in", 180, 180, "L")
p.hline("out", 180)
p.port("out", 390, 180, "R")
p.rail(50)
p.rail_low("VEE", 290, 220, 280)
p.draw()
