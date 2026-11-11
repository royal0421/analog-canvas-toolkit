# Charge pump：上下兩個電流源各經一顆開關接到輸出，一直線疊起來
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("charge-pump", "../toolkit/decks/new/charge-pump.cir")
p.two("I1", 200, 110)
p.stack(200, "L", [("MS1", 200), ("MS2", 300)])
p.two("I2", 200, 390)
p.two("CP", 270, 300)
p.port_pin("up", "MS1", "G")
p.port_pin("dn", "MS2", "G")
p.port("out", 310, 250, "R")
p.hline("out", 250)
p.rail(50)
p.draw()
