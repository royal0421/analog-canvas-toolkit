# 差動放大器：上面是反相路徑＋回授，下面是非反相路徑＋接地電阻
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("difference-amp", "../toolkit/decks/new/difference-amp.cir")
p.opamp("XOA", 300, 200)
p.two("R1", 200, 190, horizontal=True)
p.two("R2", 300, 130, horizontal=True)
p.two("R3", 200, 250, horizontal=True)
p.two("R4", 240, 300)
p.port("in1", 150, 190, "L")
p.port("in2", 150, 250, "L")
p.port("out", 390, 200, "R")
p.vline("x", 240, 130, 190)
p.vline("p", 240, 210, 280)
p.vline("out", 350, 130, 200)
p.draw()
