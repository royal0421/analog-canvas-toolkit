# Contributing

感謝你改善 Analog Canvas Toolkit。這個專案最重要的原則是：輸出的電路拓樸要正確、產生器要可重現、任何硬性驗證失敗都不能覆蓋既有成品。

## 開發環境

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m toolkit setup
python -m toolkit doctor
```

## 送出變更前

```bash
python -m unittest discover -s tests -v
python -m toolkit regress
```

如果你刻意改變 generator 輸出，先重產並親眼檢查預覽：

```bash
python -m toolkit generate all --no-render
python -m toolkit regress
```

接著確認 `out/*.icproj.json` 的差異只包含預期變更。需要視覺驗證時，移除 `--no-render`，讓 Chrome／Chromium 產生 PNG。

## 新增 generator

1. 從 README 的範本表挑最接近的 `gen_*.py`，不要複製兩支 legacy generator。
2. 保留 placement、junctions、nets、routes、annotations 五段結構。
3. 使用 `Schematic` 的公開 interface；不要直接修改 `instances`、`routes`、`drafting` 或 `_text_owner`。
4. 正式輸出寫入 `out/<可辨識名稱>.icproj.json`，工作 SVG 寫入 `toolkit/preview_<name>.svg`。
5. 所有必要的長走線、單端 junction 與故意使用正體字的標籤都要在呼叫 `build()` 時明確宣告。
6. 直接執行 generator，確認 hard audits、schema 與 labels 全部成功。
7. 執行 `python -m toolkit list`，確認 CLI 能發現新 generator 與唯一輸出。
8. 加入對應 gallery PNG 時，提供具體的 alt text 與來源說明。

## 修改共用引擎

`toolkit/icproj.py` 是深 module：callers 只需要學習小型 interface，schema 組裝、稽核、外部驗證與預覽都留在 implementation。修改它時請遵守：

- 新的上游 schema 細節應藏在 `Schematic` 或 model adapter 內，不要散落到 generators。
- 測試應從公開行為或 validation seam 驗證結果，不要綁定無關的 implementation 細節。
- subprocess 必須檢查退出狀態與實際產物，不能只比對輸出文字。
- 寫正式成品必須維持暫存檔驗證後再 `os.replace` 的原子流程。
- 新增 correctness 修正時，請在 `tests/` 加最小重現案例。

## 上游同步

`python -m toolkit setup` 會下載並執行 Analog Canvas 正式站的 JavaScript 以辨識 schema。請勿把 `toolkit/model*.mjs` 或 `toolkit/sym/` 加入 Git；它們是可重建的第三方 cache。

schema 版本變更時，應一起提交：

- `toolkit/schema_version.py`
- 全部重新產生的 `out/*.icproj.json`
- 必要的相容性程式與測試

## Pull request 建議內容

- 說明問題與使用者可觀察到的影響。
- 列出執行過的測試與回歸結果。
- 視覺變更附 before／after PNG。
- 若尚有已知限制，明確寫出，不要讓 CI 綠燈暗示未驗證的事情。
