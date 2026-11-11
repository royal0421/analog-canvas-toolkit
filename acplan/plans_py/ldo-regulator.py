# LDO：誤差放大器推 PMOS 功率管，輸出經分壓回授到 IN+
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("ldo-regulator", "../toolkit/decks/new/ldo-regulator.cir")
p.opamp("XOA", 220, 130)
p.mos("MP", 300, 130, "L")
p.two("R1", 300, 210)
p.two("R2", 300, 290)
p.two("CL", 370, 220)
p.port("vref", 140, 120, "L")
p.port("out", 410, 170, "R")
p.hline("fb", 250, 180, 300)                # 回授節點在兩顆分壓電阻中間，往左拉出再往上回到 IN+
p.hline("out", 170)
p.rail(50, 270, 330)
p.draw()
