# 三級環形振盪器：三個反相器並排，最後一級輸出從下方繞回第一級
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("ring-osc-3", "../toolkit/decks/new/ring-osc-3.cir")
p.stack(200, "L", [("MP1", 110), ("MN1", 210)])
p.stack(320, "L", [("MP2", 110), ("MN2", 210)])
p.stack(440, "L", [("MP3", 110), ("MN3", 210)])
p.hline("a", 160, 200, 290)
p.hline("b", 160, 320, 410)
p.hline("out", 160, 440, 500)
p.wire("MP1", "G", [], ("MN1", "G"))          # 第一級兩個閘極的連線
p.wire("MN1", "G", [(140, 210), (140, 290), (470, 290)], (470, 160))  # 回授線：往左、走最下面、接回輸出線
p.port("out", 500, 160, "R")
p.rail(50)
p.gnd_drop = 20
p.draw()
