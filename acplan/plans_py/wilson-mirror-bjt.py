# Wilson 電流鏡（BJT）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("wilson-mirror-bjt", "../toolkit/decks/new/wilson-mirror-bjt.cir", vdd_name="VCC")
p.two("IREF", 200, 110)
p.pair("Q1", "Q2", cols=(200, 310), y=290, gates="in")
p.bjt("Q3", 310, 200, "L")                   # 輸出電晶體疊在 Q2 上面，基極朝左接參考節點
p.port("iout", 310, 150, "U")
p.rail(50, 170, 340)
p.draw()
