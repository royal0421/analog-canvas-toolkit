# 望遠鏡式疊接運放：左右兩疊閘極相對，輸入對在疊的最下面、閘極朝外
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("telescopic-cascode", "../toolkit/decks/new/telescopic-cascode.cir")
for a, b, y in [("M7", "M8", 120), ("M5", "M6", 220), ("M3", "M4", 330)]:
    p.pair(a, b, cols=(200, 340), y=y, gates="in")
p.pair("M1", "M2", cols=(200, 340), y=430, gates="out")
p.mos("M9", 270, 520)
for net, y in [("vb4", 120), ("vb3", 220), ("vb2", 330)]:
    p.port_tap(net, 270, y, "U")
p.port_pin("vb1", "M9", "G")
p.port_pin("inp", "M1", "G")
p.port_pin("inn", "M2", "G")
p.port("outl", 160, 270, "L")                # 輸出埠朝外（兩疊之間要留給 V_b 埠）
p.port("outr", 380, 270, "R")
p.hline("tail", 470)
p.rail(40, 160, 380)
p.draw()
