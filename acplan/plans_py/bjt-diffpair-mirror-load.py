# BJT 差動對＋PNP 電流鏡負載
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("bjt-diffpair-mirror-load", "../toolkit/decks/new/bjt-diffpair-mirror-load.cir", vdd_name="VCC")
p.pair("Q3", "Q4", cols=(200, 310), y=110, gates="in")
p.pair("Q1", "Q2", cols=(200, 310), y=220, gates="out")
p.two("IEE", 250, 310)
p.port_pin("in1", "Q1", "B")
p.port_pin("in2", "Q2", "B")
p.port("out", 350, 170, "R")
p.hline("e", 260)
p.rail(50)
p.draw()
