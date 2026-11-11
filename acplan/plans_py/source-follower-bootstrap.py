# 自舉（bootstrap）源極隨耦器：C_B 從閘極跨到源極，畫在電晶體左邊；R_S 在源極下方接地
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("source-follower-bootstrap", "../toolkit/decks/new/source-follower-bootstrap.cir")
p.mos("M1", 250, 120, "L")
p.two("CB", 180, 150)                        # 上端接閘極（in）、下端接源極（out）
p.two("RS", 250, 210)
p.hline("in", 120)
p.port("in", 150, 120, "L")
p.hline("out", 170)
p.port("out", 280, 170, "R")
p.rail(50)
p.draw()
