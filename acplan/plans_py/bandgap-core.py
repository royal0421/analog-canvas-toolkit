# Bandgap 核心：上面是 V_REF 橫線，兩支電阻往下掛，底下兩顆 PNP；運放在右邊比較兩個節點
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("bandgap-core", "../toolkit/decks/new/bandgap-core.cir")
p.two("R1", 200, 150)
p.two("R2", 300, 150)
p.two("R3", 300, 250)
p.bjt("Q1", 200, 330, "L")
p.bjt("Q2", 300, 330, "L")
p.opamp("XOA", 430, 200)
p.two("RO", 480, 150, first="D")           # g 在下、V_REF 在上
p.port("out", 520, 110, "R")
p.hline("out", 110)
p.hline("y", 190)
p.hline("x", 210)
p.draw()
