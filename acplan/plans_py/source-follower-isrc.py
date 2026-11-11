# 源極隨耦器＋理想電流源＋負載電容
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("source-follower-isrc", "../toolkit/decks/new/source-follower-isrc.cir")
p.mos("M1", 200, 120, "L")
p.two("I1", 200, 220)
p.two("CL", 270, 220)
p.port_pin("in", "M1", "G")
p.port("out", 310, 170, "R")
p.hline("out", 170)
p.rail(50)
p.draw()
