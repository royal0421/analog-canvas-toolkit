# BJT 疊接電流鏡
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("bjt-cascode-mirror", "../toolkit/decks/new/bjt-cascode-mirror.cir", vdd_name="VCC")
p.two("IREF", 200, 110)
p.pair("Q3", "Q4", cols=(200, 310), y=200, gates="in")
p.pair("Q1", "Q2", cols=(200, 310), y=290, gates="in")
p.port("iout", 310, 150, "U")
p.rail(50, 170, 340)
p.draw()
