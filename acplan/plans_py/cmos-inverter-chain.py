# 兩級 CMOS 反相器串接
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("cmos-inverter-chain", "../toolkit/decks/new/cmos-inverter-chain.cir")
p.stack(200, "L", [("MMP1", 110), ("MMN1", 210)])
p.stack(320, "L", [("MMP2", 110), ("MMN2", 210)])
p.two("CCL", 390, 210)
p.vline("in", 170)
p.port("in", 140, 160, "L")
p.hline("mid", 160, 200, 290)             # 第一級輸出從中點拉一條橫線到第二級的閘極連線
p.hline("out", 160)
p.port("out", 430, 160, "R")
p.rail(50)
p.draw()
