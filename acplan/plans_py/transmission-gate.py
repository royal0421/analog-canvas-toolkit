# 傳輸閘：NMOS 在上（閘極朝上接 CK）、PMOS 在下（閘極朝下接 CKb），兩顆橫放並聯
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("transmission-gate", "../toolkit/decks/new/transmission-gate.cir")
p.place("MN", 300, 150, 90)                  # 轉 90 度：通道橫放，閘極在上
p.place("MP", 300, 220, 270)                 # 轉 270 度：閘極在下
p.two("CL", 380, 240)
p.port("clk", 300, 100, "U")
p.port("clkb", 300, 270, "D")
p.vline("a", 260)
p.port("a", 220, 190, "L")
p.hline("y", 190, 340, 380)
p.port("y", 410, 190, "R")
p.draw()
