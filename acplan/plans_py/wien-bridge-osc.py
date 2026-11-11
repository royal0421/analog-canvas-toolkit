# Wien 橋振盪器：負回授（R_F、R_G）在上，正回授的 RC 網路在下
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("wien-bridge-osc", "../toolkit/decks/new/wien-bridge-osc.cir")
p.opamp("XOA", 300, 200)
p.two("RF", 300, 130, horizontal=True)
p.two("RG", 160, 240)
p.two("RS", 320, 320, horizontal=True, first="R")
p.two("CS", 270, 320, horizontal=True, first="R")
p.two("RP", 240, 390)
p.two("CP", 190, 390)
p.port("out", 410, 200, "R")
p.vline("x", 240, 130, 190)
p.vline("p", 240, 210, 350)
p.vline("out", 370, 130, 320)
p.wire("CP", "1", [(190, 350)], (240, 350))    # C_P 上端：往上再往右接到 p 的直線（直接橫接會碰到 R_P）
p.wire("RG", "1", [(160, 190)], (240, 190))    # R_G 上端：往上再往右接到 x 的直線
p.route_order("p", "x", "a", "out")
p.draw()
