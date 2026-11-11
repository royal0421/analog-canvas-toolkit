# StrongARM latch：上面一列 PMOS（外側兩顆是 CLK 重置），中間交叉耦合 NMOS，下面差動輸入對＋CLK 尾開關
# 抄 hw2-double-tail-comparator（交叉耦合）＋ 5T-OTA（差動對＋尾）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("strongarm-latch", "../toolkit/decks/new/strongarm-latch.cir")
p.mos("M7", 140, 120, "L")
p.pair("M5", "M6", cols=(240, 340), y=120, gates="in")
p.mos("M8", 440, 120, "R")
p.pair("M3", "M4", cols=(240, 340), y=220, gates="in")
p.pair("M1", "M2", cols=(240, 340), y=300, gates="out")
p.mos("M9", 290, 380)
# 交叉耦合：兩條輸出的橫幹線錯開 20
p.hline("outp", 160)
p.hline("outn", 180)
p.port("outp", 470, 160, "R")
p.port("outn", 110, 180, "L")
p.hline("tail", 340)
p.port_pin("inp", "M1", "G")
p.port_pin("inn", "M2", "G")
p.port_pin("clk", "M9", "G")
p.label("clk", "M7", "G")
p.label("clk", "M8", "G")
p.rail(80)
p.route_order("outp", "outn", "p", "q", "tail")
p.draw()
