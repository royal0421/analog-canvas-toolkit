# Tow-Thomas biquad：OA1 有損積分器（C_1 // R_Q）、OA2 積分器、OA3 反相器，R_F 從 OA3 輸出繞上方回到 OA1 的 IN-
# 抄 opamp-integrator（每一級）＋ summing-amp（OA1 的虛接地節點直幹線串起多顆元件）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("tow-thomas-biquad", "../toolkit/decks/new/tow-thomas-biquad.cir")
# 第一級：有損積分器
p.opamp("XOA1", 300, 250)                    # IN- (260,240)、IN+ (260,260)、OUT (330,250)
p.two("R1", 200, 240, horizontal=True)
p.two("C1", 300, 190, horizontal=True)
p.two("RQ", 300, 140, horizontal=True)
p.ground("XOA1", "IN+", 240, 290)
# 第二級：積分器
p.opamp("XOA2", 500, 260)                    # 往下 10：IN- (460,250) 跟 OA1 的 OUT 同高，接點不擠
p.two("R2", 400, 250, horizontal=True)
p.two("C2", 500, 200, horizontal=True)
p.ground("XOA2", "IN+", 440, 300)
# 第三級：反相器
p.opamp("XOA3", 700, 270)                    # 同理再往下 10
p.two("R3", 600, 260, horizontal=True)
p.two("R4", 700, 210, horizontal=True)
p.ground("XOA3", "IN+", 640, 310)
# 整體回授：R_F 在最上方
p.two("RF", 500, 90, horizontal=True)
p.vline("x1", 240, 90, 240)
p.vline("bp", 350, 140, 250)
p.vline("x2", 440, 200, 250)
p.vline("lp", 550, 200, 260)
p.vline("x3", 640, 210, 260)
p.vline("v3", 750, 90, 270)
p.port("in", 150, 240, "L")
p.port_tap("bp", 350, 250, "D")
p.port_tap("lp", 550, 260, "D")
p.draw()
