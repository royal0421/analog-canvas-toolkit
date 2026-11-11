# 三運放儀表放大器：左邊上下兩顆輸入運放＋中間一串 R_2／R_G／R_2，右邊差動放大器
# 抄 difference-amp（第三級）＋ opamp-noninverting（輸入級）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("instrumentation-amp", "../toolkit/decks/new/instrumentation-amp.cir")
# 輸入級：OA1 的 IN+ 在上、OA2 的 IN+ 在下，兩顆的 IN- 都朝中間那串電阻
p.opamp("XOA1", 200, 140, plus="top")
p.opamp("XOA2", 200, 380)
p.two("R1", 260, 190)
p.two("RG", 260, 260)
p.two("R2", 260, 330)
p.hline("a", 220)
p.hline("b", 300)
# 第三級：R_3／R_4 在上、R_3／R_4（接地）在下
p.opamp("XOA3", 400, 260)
p.two("R3", 320, 140, horizontal=True)
p.two("R4", 400, 140, horizontal=True)
p.two("R5", 320, 380, horizontal=True)
p.two("R6", 360, 420)
p.hline("x", 140)
p.hline("y", 380)
p.hline("c", 140)
p.vline("d", 360)
p.vline("out", 450, 140, 260)
p.port_pin("in1", "XOA1", "IN+")
p.port_pin("in2", "XOA2", "IN+")
p.port("out", 480, 260, "R")
p.draw()
