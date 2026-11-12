# 傳輸閘式 D latch：D → TG1 → X → 反相器 1 → Qb → 反相器 2 → Q；Q 經 TG2（在兩顆反相器正下方）回授到 X
# 抄 transmission-gate（TG 的擺法）＋ cmos-inverter-chain（兩級反相器、級間橫線）
# CK／CKb 在 TG1 拉埠，TG2 的閘極掛同名標籤（SOP §4 label 那一列）
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("d-latch-tg", "../toolkit/decks/new/d-latch-tg.cir")
# TG1：NMOS 在上（閘極朝上接 CK）、PMOS 在下（閘極朝下接 CKb）
p.place("MN1", 200, 100, 90)                 # G (200,80)、D (220,110)、S (180,110)：D 跟反相器 1 的上閘極同高
p.place("MP1", 200, 220, 270)                # G (200,240)、D (220,210)、S (180,210)：D 跟下閘極同高
p.port("ck", 200, 50, "U")
p.port("ckb", 200, 270, "D")
p.vline("d", 160)
p.port("d", 120, 160, "L")
# 兩級反相器
p.stack(330, "L", [("MPA", 110), ("MNA", 210)])
p.stack(450, "L", [("MPB", 110), ("MNB", 210)])
p.hline("qb", 160)
p.hline("q", 160, 450, 490)
p.port("q", 520, 160, "R")
# TG2：在兩顆反相器正下方，左邊接 X、右邊接 Q
p.place("MN2", 380, 300, 90)                 # G (380,280)、D (400,310)、S (360,310)
p.place("MP2", 380, 380, 270)                # G (380,400)、D (400,370)、S (360,370)
p.label("ckb", "MN2", "G", side="U")
p.label("ck", "MP2", "G", side="D")
# 左右兩條線從兩顆 MOS 的中間高度（y=340）接進來，接點落在兩顆中間
p.wire("MN2", "D", [(400, 340), (490, 340)], (490, 160))
p.wire("MP2", "D", [], (400, 340))
p.wire("MN2", "S", [(360, 340)], (260, 340))
p.wire("MP2", "S", [], (360, 340))
p.vline("x", 260, 110, 340)
p.rail(50)
p.draw()
