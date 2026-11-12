# 共源級（電阻負載）的小訊號等效電路：g_m v_gs 並聯 r_o、R_D；三顆都接地 → 共用地線
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("ss-cs", "../toolkit/decks/new/ss-cs.cir")
p.source("G1", 200, 120)                     # 箭頭朝下：汲極 → 地
p.two("RO", 270, 120)
p.two("RD", 340, 120)
p.hline("d", 80, 200, 370)
p.port("d", 370, 80, "R")
p.ground_bus(160, 150, 340, at=240)          # 地線往左拉到閘極線頭正下方
p.open_port("g", 90, 80, 150)                # 閘極開路：跟汲極線同高，引線 60
p.vmark("v_gs", 150, 95, 145)
p.draw()
