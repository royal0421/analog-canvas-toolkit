# cloud-optimize 紀錄

每輪一行：日期（UTC）｜改了什麼｜預期｜bench 前 → 後（28 張：clean／place／wire／bends／crossings／稽核錯誤／牆鐘）｜commit

基準（v58-migration 2d929be）：28 figures | 27 clean | place 33% | wire 1.07x | bends 1.30x | crossings 17 | labels=1 on-wire=3 shorts=3 | 牆鐘 ≈57 min（3 workers）

- 2026-11-01｜新增 SOP_QUICK.md 生圖速查（SOP 127 KB → 速查 6.9 KB，約 1/18），SOP §0 與 README 指向它｜預期：手寫一張圖要讀的規則 token 降到約 5%｜文件，不影響 bench｜(本 commit)
- 2026-11-01｜validate.mjs 改用 model-adapter 已驗證的 factory/schema，不再盲呼叫所有 export（v58 有一個會卡滿 1 s 逾時）｜預期：每次驗證 2.1 s → 0.3 s｜不影響 bench 產物；generate all --no-render 159 s → 40 s、單張 gen_fig848 含 PNG 5.0 s → 3.0 s；regress 36/36 逐位元相同｜(本 commit)
