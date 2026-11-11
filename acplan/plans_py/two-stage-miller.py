# 兩級 Miller 補償運放（他 2026-11-11 核可的 v3 擺法）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("two-stage-miller", "../toolkit/decks/new/two-stage-miller.cir")
p.pair("M3", "M4", cols=(180, 290), y=110, gates="in")     # 電流鏡負載：閘極相對
p.pair("M1", "M2", cols=(180, 290), y=210, gates="out")    # 差動輸入對：閘極朝外
p.mos("M5", 230, 290)                                      # 尾電流源：置中在輸入對正下方
p.mos("M6", 410, 110)                                      # 第二級
p.mos("M7", 410, 290)
p.two("CC", 350, 160, horizontal=True)
p.two("CL", 460, 210)
p.port_pin("inp", "M1", "G")
p.port_pin("inn", "M2", "G")
p.port_pin("vb", "M5", "G", lead=40)
p.port("out", 510, 160, "R")
p.gate_through("M5", "M7")                                 # V_b 貫穿 M5 接到 M7
p.hline("tail", 250)
p.hline("out", 160)
p.rail(50)
p.route_order("tail", "d1", "vb", "x", "out")
p.draw()
