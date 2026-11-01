# cloud-optimize 紀錄

每輪一行：日期（UTC）｜改了什麼｜預期｜bench 前 → 後（28 張：clean／place／wire／bends／crossings／稽核錯誤／牆鐘）｜commit

基準（v58-migration 2d929be）：28 figures | 27 clean | place 33% | wire 1.07x | bends 1.30x | crossings 17 | labels=1 on-wire=3 shorts=3 | 牆鐘 ≈57 min（3 workers）

- 2026-11-01｜新增 SOP_QUICK.md 生圖速查（SOP 127 KB → 速查 6.9 KB，約 1/18），SOP §0 與 README 指向它｜預期：手寫一張圖要讀的規則 token 降到約 5%｜文件，不影響 bench｜(本 commit)
- 2026-11-01｜validate.mjs 改用 model-adapter 已驗證的 factory/schema，不再盲呼叫所有 export（v58 有一個會卡滿 1 s 逾時）｜預期：每次驗證 2.1 s → 0.3 s｜不影響 bench 產物；generate all --no-render 159 s → 40 s、單張 gen_fig848 含 PNG 5.0 s → 3.0 s；regress 36/36 逐位元相同｜(本 commit)
- 2026-11-01｜build() 新增 viewbox 稽核（零件墨跡與標籤框必須在預覽 viewBox 內，用 DejaVu 字寬量）；10 支 generator 的 viewbox 補到剛好容納｜預期：gallery 不再切字（Windows Arial 窄、Linux／網站 DejaVu 寬，2d929be 重渲染後 HW4 a/c、9.83、9.34 等 10 張被切）｜out/*.icproj.json 0 變動、regress 36/36；只換 10 張預覽 PNG；bench 不受影響（autoplace 自己算 viewbox）｜(本 commit)
- 2026-11-01｜ink_box 快取（9805330）＋bench_par 用滿 4 核、chunksize=1（e5e86ce）＋_trunk_cost 內層迴圈等價改寫（da380b3）｜預期：bench 牆鐘下降、分數不變｜28 張每行與基準相同、auto/ 28 個輸出逐位元相同；牆鐘 ≈3420 s（基準，3 workers）→ 2673 s（−22%）｜9805330 e5e86ce da380b3
- 2026-11-01｜autoplace.orient：沒有輸入埠時，一端接地的獨立電壓源的另一端算訊號節點（srcsig）｜預期：串在電壓源與閘極間的 R_S 橫放，不再與 V_in 疊在同一欄｜HW4 Fig-a：clean ✗→✓（labels 1/on-wire 3/shorts 3 → 0）、place 0.00→0.60、wire 1.06→0.83x、bends 2.33→1.67x；Cgs3／8.48／8.69 輸出逐位元相同，其餘 24 張不走此路徑。28 張推算：27→28 clean、place 33→≈35%、wire 1.07→1.06x、bends 1.30→1.28x、crossings 17→17、稽核錯誤 7→0｜(本 commit)
