# BJT 差動對＋電阻負載，尾電流源接負電源 VEE（畫成最下面一條軌）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("bjt-diffpair-vee", "../toolkit/decks/new/bjt-diffpair-vee.cir", vdd_name="VCC")
p.two("RC1", 200, 110)
p.two("RC2", 300, 110)
p.pair("Q1", "Q2", cols=(200, 300), y=220, gates="out")
p.two("IEE", 250, 310)
p.port_pin("in1", "Q1", "B")
p.port_pin("in2", "Q2", "B")
p.port("out1", 160, 170, "L")
p.port("out2", 340, 170, "R")
p.hline("e", 260)
p.rail(50)
p.rail_low("VEE", 360, 170, 330)
p.draw()
