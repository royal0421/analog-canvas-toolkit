# BJT 電流鏡＋β helper：Q3 夾在兩顆中間上方，射極接到基極連線
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("beta-helper-mirror", "../toolkit/decks/new/beta-helper-mirror.cir", vdd_name="VCC")
p.two("IREF", 200, 110)
p.pair("Q1", "Q2", cols=(200, 340), y=260, gates="in")
p.bjt("Q3", 270, 190, "L")                   # 基極朝左接參考節點 a，射極往下落在基極連線上
p.port("iout", 340, 210, "U")
p.rail(50, 170, 370)
p.draw()
