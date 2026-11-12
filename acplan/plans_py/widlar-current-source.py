# Widlar 電流源（BJT）：參考電阻＋Q1 二極體接法在左，Q2 在右、射極串 R_E
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("widlar-current-source", "../toolkit/decks/new/widlar-current-source.cir", vdd_name="VCC")
p.two("RREF", 200, 130)
p.pair("Q1", "Q2", cols=(200, 300), y=200, gates="in")
p.two("RE", 300, 260)
p.port("iout", 300, 150, "U")
# 二極體接法的方形自己畫大一點（30×30）：基極往上 30 再接回集極那條直線
p.vline("a", 200, 150, 180)
p.wire("Q1", "B", [(230, 170)], (200, 170))
p.wire("Q2", "B", [], ("Q1", "B"))
p.rail(80, 170, 330)
p.draw()
