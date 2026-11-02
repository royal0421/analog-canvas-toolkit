# cloud-optimize 紀錄

每輪一行：日期（UTC）｜改了什麼｜預期｜bench 前 → 後（28 張：clean／place／wire／bends／crossings／稽核錯誤／牆鐘）｜commit

基準（v58-migration 2d929be）：28 figures | 27 clean | place 33% | wire 1.07x | bends 1.30x | crossings 17 | labels=1 on-wire=3 shorts=3 | 牆鐘 ≈57 min（3 workers）

- 2026-11-01｜新增 SOP_QUICK.md 生圖速查（SOP 127 KB → 速查 6.9 KB，約 1/18），SOP §0 與 README 指向它｜預期：手寫一張圖要讀的規則 token 降到約 5%｜文件，不影響 bench｜2105d53
- 2026-11-01｜validate.mjs 改用 model-adapter 已驗證的 factory/schema，不再盲呼叫所有 export（v58 有一個會卡滿 1 s 逾時）｜預期：每次驗證 2.1 s → 0.3 s｜不影響 bench 產物；generate all --no-render 159 s → 40 s、單張 gen_fig848 含 PNG 5.0 s → 3.0 s；regress 36/36 逐位元相同｜b0242db
- 2026-11-01｜build() 新增 viewbox 稽核（零件墨跡與標籤框必須在預覽 viewBox 內，用 DejaVu 字寬量）；10 支 generator 的 viewbox 補到剛好容納｜預期：gallery 不再切字（Windows Arial 窄、Linux／網站 DejaVu 寬，2d929be 重渲染後 HW4 a/c、9.83、9.34 等 10 張被切）｜out/*.icproj.json 0 變動、regress 36/36；只換 10 張預覽 PNG；bench 不受影響（autoplace 自己算 viewbox）｜5b7522e
- 2026-11-01｜ink_box 快取（9805330）＋bench_par 用滿 4 核、chunksize=1（e5e86ce）＋_trunk_cost 內層迴圈等價改寫（da380b3）｜預期：bench 牆鐘下降、分數不變｜28 張每行與基準相同、auto/ 28 個輸出逐位元相同；牆鐘 ≈3420 s（基準，3 workers）→ 2673 s（−22%）｜9805330 e5e86ce da380b3
- 2026-11-01｜autoplace.orient：沒有輸入埠時，一端接地的獨立電壓源的另一端算訊號節點（srcsig）｜預期：串在電壓源與閘極間的 R_S 橫放，不再與 V_in 疊在同一欄｜HW4 Fig-a：clean ✗→✓（labels 1/on-wire 3/shorts 3 → 0）、place 0.00→0.60、wire 1.06→0.83x、bends 2.33→1.67x；Cgs3／8.48／8.69 輸出逐位元相同，其餘 24 張不走此路徑。28 張推算：27→28 clean、place 33→≈35%、wire 1.07→1.06x、bends 1.30→1.28x、crossings 17→17、稽核錯誤 7→0｜4afaa87

- 2026-11-01｜收尾：計費從 ccr_promotional 切到 seven_day（allowed_warning），依使用者指示停止｜最終推算：28 figures | 28 clean | place ≈35% | wire 1.06x | bends 1.28x | crossings 17 | 稽核錯誤 0｜—
- 2026-11-02｜開工：計費用 claude-code-remote `list_events`（kinds=rate_limit_event）讀 `rateLimitType`，每讀一次是一次模型工具呼叫（花 token）；純 bash 讀不到（本機 log／transcript 沒有這欄，curl session API 被 auto mode 擋），故未建 `scripts/billing_state.sh`，改為每項完成後查一次｜網站可連（setup 同步 v58）｜基準重跑：28 figures | 28 clean | place 35% | wire 1.06x | bends 1.28x | crossings 17 | 稽核錯誤 0 | 牆鐘 1678 s（4 workers）｜—
- 2026-11-02｜**撤回**：icproj 新增 `_part_clear_audit`（無共用 net 的兩零件 ink 距離 < CROWD_MIN 且正對 ≥ 5 單位就算錯）。起因：HW4 Fig-c 若讓 R_S 橫放（見下一項），C_L 的接地符號離 R_S 只有 4 單位，筆畫壓進鋸齒，現有稽核全抓不到｜預期：基準 28 張的最終輸出沒有一張觸發，分數不變｜28 張最終輸出確實沒有觸發，但它進了搜尋分數，descent 走了別條路：Midterm 折疊疊接 bends 36.5→46、X 6→10；Diff-amp wire 1.5→1.7x（bends 10→8）。合計 place 35→34%、wire 1.06→1.07x、bends 1.28→1.29x、crossings 17→21 → 依規則撤回｜—
- 2026-11-02｜autoplace.place_deck：最終勝出者若有零件互壓（icproj 新增 `_part_clear_audit`，不進 build 稽核、不進搜尋分數），改取已試過、稽核乾淨且不互壓的最佳版面；新增 2 個單元測試｜預期：現有 28 張最終輸出都沒互壓，分數與輸出不變；讓下一項（R_S 橫放）不會產出 C_L 接地壓 R_S 的圖｜28 張每行相同、auto/ 56 檔逐位元相同；牆鐘 1678→1671 s；regress 36/36、unittest 23/23｜62aede7
