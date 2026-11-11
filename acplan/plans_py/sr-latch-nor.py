# NOR 式 SR latch：左右各一個 NOR2，鏡射擺放；交叉耦合用同名標籤（Q、Qb）表示，不拉線
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("sr-latch-nor", "../toolkit/decks/new/sr-latch-nor.cir")
# 左邊的 NOR（輸出 Q）：閘極朝左
for ref, col, y, net in [("MPA1", 230, 110, "r"), ("MPA2", 230, 190, "qb"), ("MNA1", 160, 320, "r"), ("MNA2", 300, 320, "qb")]:
    p.mos(ref, col, y, "L")
    p.label(net, ref, "G")
# 右邊的 NOR（輸出 Qb）：鏡射，閘極朝右
for ref, col, y, net in [("MPB1", 570, 110, "s"), ("MPB2", 570, 190, "q"), ("MNB1", 640, 320, "s"), ("MNB2", 500, 320, "q")]:
    p.mos(ref, col, y, "R")
    p.label(net, ref, "G")
p.hline("q", 270)
p.hline("qb", 270)
p.port("q", 340, 270, "R")
p.port("qb", 460, 270, "L")
p.rail(50)
p.draw()
