# Class-AB 輸出級：左欄 R1-D1-D2-R2 一串產生兩個基極偏壓，右欄 NPN 在上、PNP 在下推挽
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("class-ab-diode-bias", "../toolkit/decks/new/class-ab-diode-bias.cir", vdd_name="VCC")
p.bjt("Q1", 300, 140, "L")
p.bjt("Q2", 300, 260, "L")
p.two("R1", 230, 110)
p.two("R2", 230, 290)
for ref, y in (("D1", 170), ("D2", 230)):     # 二極體直放，陽極朝上
    for rot in (90, 270):
        p.place(ref, 230, y, rot)
        if p.pin(ref, "A")[1] < p.pin(ref, "K")[1]:
            break
p.two("RL", 370, 230)
p.vline("b1", 230)
p.vline("b2", 230)
p.vline("in", 230)
p.port("in", 200, 200, "L")
p.hline("out", 200)
p.port("out", 400, 200, "R")
p.rail(60)
p.rail_low("VEE", 340)
p.draw()
