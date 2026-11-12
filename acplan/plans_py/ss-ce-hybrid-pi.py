# 共射級的 hybrid-π 小訊號等效電路：r_π 在基極與地之間，g_m v_π 並聯 r_o、R_C；共用地線
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("ss-ce-hybrid-pi", "../toolkit/decks/new/ss-ce-hybrid-pi.cir")
p.two("RPI", 150, 120)
p.source("G1", 240, 120)
p.two("RO", 310, 120)
p.two("RC", 380, 120)
p.hline("b", 80, 90, 150)                    # 基極線跟集極線同高
p.port("b", 90, 80, "L")
p.hline("c", 80, 240, 410)
p.port("c", 410, 80, "R")
p.ground_bus(160, 150, 380, at=280)
p.vmark("v_π", 125, 95, 145)                 # 標在 r_π 左邊
p.draw()
