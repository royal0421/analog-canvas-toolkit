# 兩級運放（PMOS 輸入對、NMOS 鏡負載、NMOS 共源第二級、R_z 串 C_c 補償）
# 抄 two-stage-miller 上下翻轉：尾電流源在上、輸入對中間、鏡負載在下
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("two-stage-pmos-in-rz", "../toolkit/decks/new/two-stage-pmos-in-rz.cir")
p.mos("M5", 230, 110)                                      # 尾電流源：置中在輸入對正上方
p.pair("M1", "M2", cols=(180, 290), y=200, gates="out")    # PMOS 輸入對：閘極朝外
p.pair("M3", "M4", cols=(180, 290), y=290, gates="in")     # NMOS 鏡負載：閘極相對
p.mos("M7", 450, 110)                                      # 第二級電流源
p.mos("M6", 450, 290)                                      # 第二級共源
p.two("RZ", 340, 240, horizontal=True)
p.two("CC", 410, 240, horizontal=True)
p.two("CL", 500, 290)
p.port_pin("inn", "M1", "G")
p.port_pin("inp", "M2", "G")
p.port_pin("vb", "M5", "G", lead=40)
p.port("out", 550, 240, "R")
p.gate_through("M5", "M7")
p.hline("tail", 160)
p.hline("out", 240)
p.rail(50)
p.route_order("tail", "d1", "vb", "x", "n1", "out")
p.draw()
