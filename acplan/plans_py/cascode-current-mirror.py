# 疊接電流鏡：參考支路在左（二極體接法兩顆），輸出支路在右，閘極相對
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("cascode-current-mirror", "../toolkit/decks/new/cascode-current-mirror.cir")
p.two("IIREF", 200, 110)
p.pair("MM1", "MM3", cols=(200, 310), y=200, gates="in")
p.pair("MM2", "MM4", cols=(200, 310), y=290, gates="in")
p.port("out", 310, 150, "U")                 # 輸出電流：從 M3 汲極往上
p.rail(50, 170, 340)
p.draw()
