# 共射級的小訊號等效電路（流控電流源 β i_b）：r_π 在基極與地之間，β i_b 並聯 r_o、R_C；i_b 標在基極線上方
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("ss-ce-beta", "../toolkit/decks/new/ss-ce-beta.cir")
p.two("RPI", 150, 120)
p.source("F1", 240, 120)
p.two("RO", 310, 120)
p.two("RC", 380, 120)
p.hline("b", 80, 90, 150)                    # 基極線跟集極線同高
p.port("b", 90, 80, "L")
p.hline("c", 80, 240, 410)
p.port("c", 410, 80, "R")
p.ground_bus(160, 150, 380, at=280)
p.imark("i_b", 105, 70, 135, 70)             # 箭頭在基極線上方 10，指向 r_π
p.draw()
