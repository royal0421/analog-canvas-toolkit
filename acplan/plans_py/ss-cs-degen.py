# 源極退化共源級的小訊號等效電路（低頻、含 r_o）：g_m v_gs 由汲極流向源極、並聯 r_o；R_S 接地、R_D 接地（VDD 交流接地）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("ss-cs-degen", "../toolkit/decks/new/ss-cs-degen.cir")
p.source("G1", 200, 120)                     # ＋(200,100)＝汲極、−(200,140)＝源極；箭頭朝下
p.two("RO", 270, 120)                        # 與受控源並聯；欄距 70 放得下 g_m v_gs
p.two("RD", 340, 120)
p.two("RS", 200, 190)                        # 源極節點正下方
p.hline("d", 80, 200, 370)                   # 幹線比上端腳高 20
p.hline("s", 160, 150, 270)                  # 往左拉到閘極線頭正下方，給 v_gs 的「−」當參考
p.port("d", 370, 80, "R")
p.open_port("g", 90, 80, 150)               # 閘極開路：端子跟汲極線同高，引線 60
p.vmark("v_gs", 150, 95, 145)
p.draw()
