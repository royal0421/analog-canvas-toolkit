# analog-canvas-toolkit

離線產生 [Analog Canvas](https://analog-canvas.tokenzhang.com/editor) 的
`.icproj.json` 專案檔，畫出**課本級**的類比電路圖：寫一支 140 行的產生器 →
跑一個指令（六道稽核＋schema 驗證＋標籤比對＋PNG 渲染）→ 在編輯器 `File / Import Project File` 匯入。

不用滑鼠拖元件，也不靠肉眼判讀原圖——間距、標籤位置、密度都有可量的規則，
全部寫在 [`SOP.md`](SOP.md) 裡。**動手前先讀 SOP，不要憑印象畫。**

![Razavi Fig. 10.35(a)](examples/Razavi_Fig_10_35a_diffpair-diode-load.png)

## 環境需求

| 需要 | 用途 |
|---|---|
| Python 3.8+ | 產生器與截圖掃描器（`scan_figure.py` 需要 Pillow） |
| Node.js 18+ | `validate.mjs`、`check_labels.mjs`（用網站自己的 zod schema） |
| Chrome | 把預覽 SVG 轉成 PNG 親眼看一次 |

## 首次設定（約 10 秒）

符號資產與網站 schema 都是上游 [cascode-ai/analog-canvas](https://github.com/cascode-ai/analog-canvas)
的產物，**不進版控**，clone 後自己抓：

```bash
python toolkit/fetch_symbols.py    # -> toolkit/sym/*.json（48 個符號）
python toolkit/refresh_model.py    # -> toolkit/model.mjs（網站的 schema）
```

網站改版、或匯出的專案回報不同的 `schemaVersion` 時，重跑 `refresh_model.py`。

## 畫一張圖（目標 5~10 分鐘）

```bash
python toolkit/scan_figure.py path/to/screenshot.png   # ⓪ 拓樸／鏡射／GAP／密度基準
cp toolkit/gen_fig848.py toolkit/gen_myfig.py          # ① 抄範本，只改五段資料
python toolkit/gen_myfig.py                            # ② 這一步就是全部
```

第 ② 步做完六道稽核、用網站自己的 schema 驗證、用編輯器自己的產生器逐位元比對
標籤，最後渲染出 PNG。**六個計數全部要是 0** 才往下走：

```
audits: legs 0 | labels 0 | on-wire 0 | tees 0   (all must be 0)
  schema: VALID (v31)
  labels: OK (3 declared plain)
  png: preview_myfig.png (1770x895)
```

| 訊息 | 意思 |
|---|---|
| `self-check errors` | 非正交、零長度、腳位不存在、junction 壓在 terminal 上 |
| `legs` | 有一段超過 40 單位且不在 `long_haul` 白名單 |
| `labels` | 文字框壓到走線，或標籤離鄰居太近、讀者分不出屬於誰 |
| `on-wire` | 元件坐在別條 net 的走線上，或任何一條線穿過元件本體（同 net 也算） |
| `tees` | 三條線在同一點相會卻沒有 junction ⇒ 編輯器不畫圓點（電源軌除外） |
| `schema` | 對不上就是網站改版了 → 重跑 `refresh_model.py` |

最後親眼看那張 PNG（`toolkit/preview_*.png`），有原圖就並排比對。
`AC_VERBOSE=1` 印完整走線表，`AC_FAST=1` 只產檔不做驗證與渲染。

## 範本怎麼挑

| 圖裡有什麼 | 抄這支 |
|---|---|
| opamp、電阻、接地（最乾淨的範本） | `toolkit/gen_fig848.py` |
| 電阻／電容、旋轉 90 度、數值標籤 | `toolkit/gen_fig794.py` |
| 差動對、多顆尾電流源、差動輸出埠 | `toolkit/gen_fig1035.py` |
| BJT、電源軌 | `toolkit/gen_fig5170.py` |
| 方塊圖（沒有符號的功能方塊、虛線子系統框） | `toolkit/gen_cdr_blocks.py` |

`gen_fig934.py` 與 `gen_fig983_cg.py` 是舊式獨立骨架，只拿來查座標寫法，**不要複製**。

## 範例

`examples/` 有 26 張，全部通過上面六道稽核。

| | |
|---|---|
| ![](examples/Razavi_Fig_9_26c_BJT-mirror-combined-outputs.png) | ![](examples/Razavi_Fig_8_48_noninverting-T-feedback.png) |
| ![](examples/Razavi_Fig_12_57c_diffpair-mirror-load-Rx-test.png) | ![](examples/CDR_architecture.png) |

## 檔案位置

見 [`SOP.md` §10](SOP.md)。`out/` 是產生器的輸出目錄，裡面的 `.icproj.json` 不進版控。

## 來源

電路圖編輯器與符號資產屬於 [cascode-ai/analog-canvas](https://github.com/cascode-ai/analog-canvas)。
本 repo 只包含自己寫的產生器、稽核規則與 SOP；上游的 `sym/*.json` 與 `model.mjs`
由 `fetch_symbols.py` / `refresh_model.py` 在本機取得，不重新散布。
