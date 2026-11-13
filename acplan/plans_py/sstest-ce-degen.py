# 射極退化共射級的小訊號等效電路（低頻、不含 r_o）：r_π 在基極與射極之間；β i_b 由集極流向射極；R_E 接地、R_C 接地
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("sstest-ce-degen", "../toolkit/decks/new/sstest-ce-degen.cir")
p.two("RPI", 150, 120)                       # b(150,100)、e(150,140)
p.source("F1", 220, 120)                     # c(220,100) 在上、e(220,140) 在下；箭頭朝下
p.two("RC", 290, 120)                        # 欄距 70 放得下 β i_b
p.two("RE", 220, 190)                        # 射極節點正下方
p.hline("b", 80, 90, 150)                    # 基極線跟集極線同高
p.port("b", 90, 80, "L")
p.hline("c", 80, 220, 320)
p.port("c", 320, 80, "R")
p.hline("e", 160, 150, 220)                  # 射極線比下端腳低 20
p.imark("i_b", 105, 70, 135, 70)             # 箭頭在基極線上方 10，指向 r_π
p.draw()
