# 折疊疊接、PMOS 輸入對（期中那張上下顛倒）；抄 midterm-folded-cascode
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("folded-cascode-pmos-in", "../toolkit/decks/new/folded-cascode-pmos-in.cir")
# 右邊兩疊：閘極相對，每一列共用一條閘極線
for a, b, y in [("M7", "M8", 160), ("M5", "M6", 240), ("M3", "M4", 340), ("M9", "M10", 440)]:
    p.pair(a, b, cols=(440, 580), y=y, gates="in")
# 左邊 PMOS 輸入對：放在 NMOS 疊接（M3）那一列，尾電流源置中在正上方
p.pair("M1", "M2", cols=(200, 280), y=340, gates="out")
p.mos("M11", 240, 240)
for net, y, side in [("vb4", 160, "U"), ("vb3", 240, "U"), ("vb2", 340, "D"), ("vb1", 440, "D")]:
    p.port_tap(net, 510, y, side)
p.port_pin("vb5", "M11", "G")
p.port_pin("inp", "M1", "G")
p.port_pin("inn", "M2", "G")
p.port("outl", 410, 290, "L")
p.port("outr", 610, 290, "R")
p.hline("tail", 280)
p.hline("fl", 390)
p.hline("fr", 410)
p.rail(80)
p.route_order("vb4", "vb3", "vb2", "vb1", "xl", "xr", "tail", "outl", "outr", "fl", "fr", "inp", "inn", "vb5")
p.draw()
