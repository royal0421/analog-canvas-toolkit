# 疊接共源級＋源極退化電阻：R_D、M2、M1、R_S 同一欄，C_L 掛在輸出右邊
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from acplan import Plan

p = Plan("cs-degen-cascode", "../toolkit/decks/new/cs-degen-cascode.cir")
p.two("RRD", 200, 110)                       # 腳在 90／130
p.stack(200, "L", [("MM2", 200), ("MM1", 280)])  # M2 汲極 180；M1 源極 300（列距 80，中間 x 節點的空線縮短）
p.two("RRS", 200, 340)                       # 腳在 320／360，下端接地
p.two("CCL", 270, 190)                       # 腳在 170／210（上腳低於輸出幹線，埠的分支才不會碰到 C_L）
p.port_pin("vb", "MM2", "G", name="V_b")   # deck 沒給 .name vb，不指定會顯示成小寫 v_b
p.port_pin("in", "MM1", "G")
p.port("out", 300, 160, "R")
p.hline("out", 160)
p.rail(50)
p.draw()
