# NMOS 差動對＋電阻負載＋理想尾電流源
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("nmos-diffpair-resistor", "../toolkit/decks/new/nmos-diffpair-resistor.cir")
p.two("RD1", 200, 110)
p.two("RD2", 300, 110)
p.pair("M1", "M2", cols=(200, 300), y=210, gates="out")
p.two("ISS", 250, 300)
p.port_pin("in1", "M1", "G")
p.port_pin("in2", "M2", "G")
p.port("out1", 160, 160, "L")
p.port("out2", 340, 160, "R")
p.hline("p", 250)
p.rail(50)
p.draw()
