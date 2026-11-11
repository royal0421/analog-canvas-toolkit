# 五顆電晶體 OTA：電流鏡負載＋差動對＋尾電流源
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("5T-OTA", "../toolkit/decks/new/5T-OTA.cir")
p.pair("MM3", "MM4", cols=(180, 290), y=110, gates="in")
p.pair("MM1", "MM2", cols=(180, 290), y=210, gates="out")
p.mos("MM5", 230, 290)
p.port_pin("inp", "MM1", "G")
p.port_pin("inn", "MM2", "G")
p.port_pin("vb", "MM5", "G")
p.port("out", 330, 160, "R")                 # 輸出：掛在 M4／M2 汲極那條直線上
p.hline("tail", 250)
p.rail(50)
p.draw()
