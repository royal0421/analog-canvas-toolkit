# PLL 線性相位模型：φ_in → 加法點 → K_PD → F(s) → K_VCO/s → φ_out；1/N 在下面回授
# 抄 feedback-loop；方框一多就用等距欄（這裡欄距 110）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("pll-linear-model", "../toolkit/decks/flow/pll-linear-model.cir")
p.adder("XS1", 180, 200)
p.block("XPD", 280, 200)
p.block("XLF", 390, 200)
p.block("XVCO", 510, 200, w=60)
p.block("XDIV", 390, 300, flip=True)
p.port("pin", 100, 200, "L")
p.port("pout", 660, 200, "R")
p.hline("pout", 200, 550, 660)
p.wire("XDIV", "A", [(600, 300)], (600, 200))
p.wire("XDIV", "Y", [(180, 300)], ("XS1", "B"))
p.draw()
