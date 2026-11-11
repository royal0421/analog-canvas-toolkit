# Gilbert cell 混頻器（他 2026-11-11 核可的 v4 擺法）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("gilbert-cell", "../toolkit/decks/new/gilbert-cell.cir", vdd_name="VCC")
p.two("RL1", 200, 110)
p.two("RL2", 480, 110)
p.pair("Q3", "Q4", cols=(200, 290), y=210, gates="out")    # 上面四顆：兩組差動對
p.pair("Q5", "Q6", cols=(390, 480), y=210, gates="out")
p.pair("Q1", "Q2", cols=(240, 440), y=340, gates="out")    # 下面的 RF 差動對
p.two("IEE", 340, 410)
p.port_tap("lo2", 340, 210, "D", lead=40)                  # LO2：中間兩個基極的連線往下掛
p.port("lo1", 130, 300, "L")                               # LO1：外側兩個基極，用下方一條橫線相連
p.port_pin("rf1", "Q1", "B", lead=40)
p.port_pin("rf2", "Q2", "B", lead=40)
p.port("out1", 160, 150, "L")                              # 輸出埠與交叉線同高 → 一個十字點
p.port("out2", 520, 150, "R")
p.hline("a", 240)
p.hline("b", 240)
p.hline("e", 370)
p.hline("out1", 150)
p.hline("out2", 170)
p.hline("lo1", 300)
p.rail(60, 160, 520)
p.route_order("a", "b", "e", "lo2", "out1", "out2", "lo1", "rf1", "rf2")
p.draw()
