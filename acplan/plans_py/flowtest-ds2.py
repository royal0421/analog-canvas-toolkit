# 二階 ΔΣ 調變器：X → 加法點 → 積分器 → 加法點 → 積分器 → 量化器 → Y；DAC 在下面回授到兩個加法點（−）
# 抄 delta-sigma-1st
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("flowtest-ds2", "../toolkit/decks/flow/flowtest-ds2.cir")
p.adder("XS1", 180, 200)
p.block("XINT1", 300, 200, w=60)
p.adder("XS2", 420, 200)
p.block("XINT2", 540, 200, w=60)
p.block("XQ", 670, 200)
p.block("XDAC", 560, 300, flip=True)
p.port("x", 100, 200, "L")
p.port("y", 810, 200, "R")
p.hline("y", 200, 700, 810)
p.wire("XDAC", "IN", [(760, 300)], (760, 200))
p.wire("XDAC", "OUT", [(180, 300)], ("XS1", "B"))
p.wire("XS2", "B", [], (420, 300))
p.draw()
