# 接收機訊號鏈：RF → LNA（三角形）→ 混頻（乘法點，LO 從下面進）→ H(s) → ADC → D_out
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("receiver-chain", "../toolkit/decks/flow/receiver-chain.cir")
p.block("XLNA", 190, 200)
p.adder("XMIX", 290, 200)
p.block("XLPF", 390, 200)
p.block("XADC", 510, 200)
p.port("rf", 100, 200, "L")
p.port("lo", 290, 270, "D")
p.port("dout", 620, 200, "R")
p.draw()
