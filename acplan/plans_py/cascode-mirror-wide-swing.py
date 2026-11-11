# 寬擺幅疊接電流鏡：偏壓支路在最左，V_b 貫穿 M3 接到 M4；下排電流鏡閘極相對，接回參考節點 a
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("cascode-mirror-wide-swing", "../toolkit/decks/new/cascode-mirror-wide-swing.cir")
p.two("IB", 180, 110)
p.two("IREF", 300, 110)
p.mos("M5", 180, 200, "R")                   # 偏壓的二極體接法
p.mos("M3", 300, 200, "L")
p.mos("M4", 410, 200, "L")
p.pair("M1", "M2", cols=(300, 410), y=290, gates="in")
p.gate_through("M3", "M4")                   # 偏壓線貫穿 M3
p.port("iout", 410, 150, "U")
p.vline("a", 350, 150, 290)                  # 參考節點 a 往下接到下排的閘極連線
p.rail(50, 150, 440)
p.route_order("vb", "x", "y", "a")
p.draw()
