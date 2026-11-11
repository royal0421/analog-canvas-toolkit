# 交叉耦合 LC 振盪器：電感從 VDD 往下接兩個輸出，電容各自接地，交叉耦合對＋尾電流源
# 抄 strongarm-latch（交叉耦合的兩條幹線錯開）＋ 5T-OTA（差動對＋尾）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("lc-oscillator-xcoupled", "../toolkit/decks/new/lc-oscillator-xcoupled.cir")
p.two("L1", 200, 140)
p.two("L2", 320, 140)
p.two("C1", 140, 240)
p.two("C2", 380, 240)
p.pair("M1", "M2", cols=(200, 320), y=280, gates="in")    # 交叉耦合對：閘極朝內，中間畫成 X
p.two("ISS", 260, 350)
# 兩條輸出橫線上下錯開 20：out1 在上，往右伸到 M2 的閘極；out2 在下，往左伸到 M1 的閘極
p.hline("outp", 190, x0=110, x1=290)
p.hline("outn", 210, x0=230, x1=410)
p.port("outp", 110, 190, "L")
p.port("outn", 410, 210, "R")
p.hline("tail", 320)
p.rail(80)
p.route_order("outn", "outp", "tail")
p.draw()
