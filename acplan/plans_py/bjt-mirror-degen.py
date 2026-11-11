# BJT 電流鏡＋射極退化電阻
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("bjt-mirror-degen", "../toolkit/decks/new/bjt-mirror-degen.cir", vdd_name="VCC")
p.two("IREF", 200, 110)
p.pair("Q1", "Q2", cols=(200, 310), y=200, gates="in")
p.two("RE1", 200, 270)
p.two("RE2", 310, 270)
p.port("iout", 310, 150, "U")
p.rail(50, 170, 340)
p.draw()
