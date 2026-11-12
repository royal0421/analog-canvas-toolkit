# 共閘級的小訊號等效電路（低頻、含 r_o）：閘極交流接地；v_in 接源極、R_S 接地；g_m v_gs 由汲極流向源極、並聯 r_o；R_D 接地
# v_gs = 0 - v_s：標在 R_S 左邊，+ 在下（地那側）、- 在上（源極線那側）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("sstest-cg", "../toolkit/decks/new/sstest-cg.cir")
p.source("G1", 220, 120)                     # 上(220,100)=汲極、下(220,140)=源極；箭頭朝下＝汲極→源極
p.two("RO", 290, 120)
p.two("RD", 360, 120)
p.two("RS", 150, 200)                        # 掛在源極線下方
p.hline("d", 80, 220, 390)
p.port("d", 390, 80, "R")
p.hline("s", 160, 90, 290)
p.port("s", 90, 160, "L")
p.vmark("v_gs", 120, 225, 175)               # + 在下（地）、- 在上（源極）
p.draw()
