# PLL 線性模型＋VCO 相位雜訊：φ_in → 加法點 → K_PD → F(s) → K_VCO/s → 加法點（φ_n 從上面進）→ φ_out；1/N 在下面回授
# 抄 pll-linear-model＋loop-with-disturbance
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("flowtest-pll-noise", "../toolkit/decks/flow/flowtest-pll-noise.cir")
p.adder("XS1", 180, 200)
p.block("XPD", 280, 200)
p.block("XLF", 390, 200)
p.block("XVCO", 510, 200, w=60)
p.adder("XS2", 620, 200, b="U")
p.block("XDIV", 450, 300, flip=True)
p.port("pin", 100, 200, "L")
p.port("pn", 620, 130, "U")
p.port("pout", 770, 200, "R")
p.hline("pout", 200, 640, 770)
p.wire("XDIV", "A", [(710, 300)], (710, 200))
p.wire("XDIV", "Y", [(180, 300)], ("XS1", "B"))
p.draw()
