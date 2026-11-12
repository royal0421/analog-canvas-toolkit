# Constant-gm 偏壓（beta multiplier）：上面 PMOS 鏡、下面 NMOS 對，M2 源極串 R_S
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("constant-gm-bias", "../toolkit/decks/new/constant-gm-bias.cir")
p.pair("M3", "M4", cols=(200, 310), y=110, gates="in")   # PMOS 鏡：M4 二極體接法
p.pair("M1", "M2", cols=(200, 310), y=200, gates="in")   # NMOS：M1 二極體接法
p.two("RS", 310, 260)
# 二極體接法的方形自己畫大一點（30×30）；埠接在方形的接點上，同一條線上只留一個點
p.vline("vbn", 200, 130, 180)
p.wire("M1", "G", [(230, 170)], (200, 170))
p.wire("M2", "G", [], ("M1", "G"))
p.vline("vbp", 310, 130, 180)
p.wire("M4", "G", [(280, 140)], (310, 140))
p.wire("M3", "G", [], ("M4", "G"))
p.port("vbn", 170, 170, "L")
p.port("vbp", 340, 140, "R")
p.rail(60)
p.draw()
