# 期中折疊疊接運放（他 2026-11-11 核可的 v4 擺法）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("midterm-folded-cascode", "../toolkit/decks/AIC-intro_Midterm-2026_Fig1_folded-cascode.cir")
# 右邊兩疊：閘極相對，每一列共用一條閘極線
for a, b, y in [("M7", "M8", 120), ("M5", "M6", 250), ("M3", "M4", 360), ("M9", "M10", 440)]:
    p.pair(a, b, cols=(380, 520), y=y, gates="in")
# 左邊輸入對：放在疊接 PMOS（M5）那一列的高度，尾電流源置中在正下方
p.pair("M1", "M2", cols=(200, 280), y=250, gates="out")
p.mos("M11", 240, 350)
# V_b 埠掛在各條閘極線中點上方 30
for net, y in [("b4", 120), ("b3", 250), ("b2", 360), ("b1", 440)]:
    p.port_tap(net, 450, y, "U")
p.port_pin("b5", "M11", "G")
p.port_pin("in1", "M1", "G")
p.port("in2", 140, 310, "L")                 # 第二個輸入從輸入對下方繞到 M2 的閘極
p.port("ol", 410, 300, "R")                  # 輸出埠朝內
p.port("or", 490, 300, "L")
p.hline("fl", 160)                           # 折疊線：M1 汲極 → 左疊的折疊點
p.hline("fr", 180)
p.hline("tail", 290)
p.hline("in2", 310, x0=150, x1=310)
p.rail(40, 340, 560)
p.route_order("b4", "b3", "b2", "b1", "xl", "xr", "tail", "ol", "or", "fl", "fr", "in1", "in2", "b5")
p.draw()
