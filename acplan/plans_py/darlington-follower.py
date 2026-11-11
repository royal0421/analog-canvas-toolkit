# Darlington 射極隨耦器：Q1 射極直接接 Q2 基極，R_E 接地
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("darlington-follower", "../toolkit/decks/new/darlington-follower.cir", vdd_name="VCC")
p.bjt("Q1", 200, 120, "L")                   # E 在 (200,140)
p.bjt("Q2", 290, 140, "L")                   # B 在 (260,140)，跟 Q1 射極同高
p.two("RE", 290, 210)
p.port_pin("in", "Q1", "B")
p.port("out", 320, 170, "R")
p.vline("out", 290)                          # Q2.E 和 R_E 同欄，幹線用直的
p.rail(50)
p.draw()
