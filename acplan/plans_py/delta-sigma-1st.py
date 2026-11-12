# 一階 ΔΣ 調變器：U → 加法點 → 積分器 → 量化器 → V；DAC 在下面回授
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("delta-sigma-1st", "../toolkit/decks/flow/delta-sigma-1st.cir")
p.adder("XS1", 180, 200)
p.block("XINT", 300, 200, w=60)
p.block("XQ", 430, 200)
p.block("XDAC", 300, 300, flip=True)
p.port("u", 100, 200, "L")
p.port("v", 570, 200, "R")
p.hline("v", 200, 460, 570)
p.wire("XDAC", "IN", [(510, 300)], (510, 200))
p.wire("XDAC", "OUT", [(180, 300)], ("XS1", "B"))
p.draw()
