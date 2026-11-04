# 生圖速查（SOP 精簡版）

> 手寫一支 `gen_*.py` 需要的規則都在這頁（約 1/10 篇幅）。細節與事故紀錄在 `SOP.md`，
> 這裡每條都標了出處 §，**只有卡住時才翻 SOP 對應那一節，不要讀全文**。
> 路線二（netlist 自動排版）的研發紀錄在 SOP §3J，畫圖用不到。

## 1. 流程（§0、§5）

1. 有原圖：`python toolkit/scan_figure.py <截圖>` 抽拓樸、鏡射、密度（§3C）。手繪圖不能用，放大眼讀（§3I-b）。
2. 抄 `toolkit/gen_fig848.py`，只改五段：placement／junctions／nets／routes／annotations。
3. `python toolkit/gen_xxx.py`（或 `python -m toolkit generate gen_xxx`）。`build()` 一次做完
   稽核＋schema＋標籤比對＋PNG。**不要另外跑 validate.mjs／check_labels.mjs／Chrome，也不要 `| grep` 輸出。**
4. 全部 0 → 親眼看 `toolkit/preview_xxx.png` → 交付。輸出寫進 `out/<來源>_<圖號>_<簡述>.icproj.json`（§9）。

```
self-check errors: 0
audits: legs 0 | labels 0 | on-wire 0 | tees 0   (all must be 0)
  schema: VALID (v58)
  labels: OK (N declared plain)
```

環境變數：`AC_NO_RENDER=1` 略過 PNG、`AC_VERBOSE=1` 完整走線表、`AC_FAST=1` 只跑內部稽核（不可交付）。

## 2. API（`from icproj import Schematic, name, plain, name_suffix, split_name, dy_above, dy_below, LABEL_PORT`）

| 呼叫 | 用途 |
|---|---|
| `f.place(iid, sym, x, y, mirror, extra=...)` | 任意符號；座標必須是 10 的倍數 |
| `f.passive(iid, "resistor"/"capacitor"/"inductor", x, y, "R_1", rotation=0/90)` | 被動元件（rotation 90：腳 1 在右、2 在左） |
| `f.mos(iid, "nmos"/"pmos", x, y, mirror, "M_1")`、`f.bjt(...)`、`f.isrc(...)` | 主動元件、電流源（自帶 3-terminal 變體） |
| `f.gnd(iid, x, y)`、`f.port(iid, x, y, mirror="x")` | 接地、埠（輸出端埠 `mirror="x"`） |
| `f.junction(jid, net, x, y)`、`f.net(net, [(iid, pin), ...])` | 節點、網表 |
| `f.route(rid, net, T(iid,pin) 或 J(jid), [("bend",x,y), ("to", ...)])` | 走線，只能正交；`T, J = f.term, f.jn` |
| `f.rail(net, y, xs)` | 電源軌：xs＝[左端, 分支…, 右端]，每個 x 要先有同 y 的 junction |
| `f.terminal(tid, "V_out", net, "output", [iid])` + `f.port_label(iid, tid, LABEL_PORT, 5, "start")` | 埠一定要有 cell terminal |
| `f.inst_label(iid, dx, dy, align)`、`f.text(tid, x, y, align, label, owner=iid)`、`f.power_label(...)` | 標籤；值標籤要給 `owner` |
| `f.arrow(...)`、`f.rect(...)`、`f.construction(...)` | 電流箭頭（§6B）、方塊、斜線（不導電） |
| `f.build(long_haul={...}, rail_ends={...}, viewbox=..., expect_differ={...}, density_ref=(iid, %))` | 收尾 |

## 3. 符號（§2、§2C；腳位相對中心，rotation 0）

| symbolId | 腳位 |
|---|---|
| `nmos` | D(+10,−20) G(−20,0) S(+10,+20)；閘極在左，`mirror:"x"` 放右 |
| `pmos` | S(+10,−20) G(−20,0) D(+10,+20) |
| `resistor`／`capacitor` | 1(0,−20) 2(0,+20) |
| `ground` | 0(0,−10) |
| `port`／`port-filled` | P(0,0) |
| `current-source` | +(0,−20) −(0,+20)，箭頭朝下 |

- 其他符號查 `toolkit/sym/<id>.json` 的 `pins`；**沒有就跑 `python toolkit/fetch_symbols.py`，還是沒有就回報使用者，不要自己畫**（§2）。
- 🚫 `vdd` 不能放（schema 會過但網站匯入失敗），一律用 `vdd-port`；禁用清單見 `Schematic.UNPLACEABLE`（§2）。
- `mirror` 在產生器裡只寫 `"none"`／`"x"`，寫檔時自動轉成 v58 enum（§2C）。

## 4. 排版常數（§3A、§3D）

```
格線 10；相鄰元素走線下限 20；junction 兩側各 20
源極/射極→接地 10；節點→埠 20（接 BJT 基極 10）；電源軌→元件 20；軌兩端外伸 20
單段走線 ≤ 40，超過要列進 long_haul 並註明理由
欄中心距 ≤ 80（手繪圖 50~70）；匯流排列放在腳位列外側 10，用 10 的 riser 接
```

- **junction 不可壓在 terminal 上**（零長走線）；**terminal 壓 terminal 合法且推薦**（省走線、提高密度）。
- 對稱結構：中線上的元件、標籤共用同一個中心 x；中點不在格線就調兩側欄（§3A）。
- 密度：MOS 圖「通道 bar 25 ÷ 圖高」做到約 10%；`density_ref` 會標 `TOO LOOSE`（§3A）。
- 元件不可坐在別的 net 的走線上；線不可穿過任何元件本體（on-wire）；兩條不同 net 不可共線（shorts）。
- 三向接點一定要 junction（tees），電源軌除外。
- 接地符號全部對齊同一排（§3E 規則 4）。

## 5. 標籤（§3A、§4、§2C）

- 名稱一律 `name("M_1")`：v58 的編輯器 builder（Kd）＝**第一個字元斜體、其餘下標**，
  底線只是我們的切點記號，不會進檔案。`FF_1` 會印成 F＋下標 F1（要原樣用 `split_name()`）。
- 錨點＝該側實際墨跡邊緣 ＋ 8：MOS ±18、BJT ±8、電流源 ±18、埠 `LABEL_PORT`(14)。標在 D/S、C/E 那側，`dy=+5`。
- 上方／下方用 `dy_above(ink_half, gap)`／`dy_below(...)`：電容 gap 1.5、電阻 gap 6。
- 標籤離同型鄰居 ≥ 17 且 ≥ 2 倍離自己的距離；夾在兩條線間時兩線距 ≥ 30（§3D）。
- **`expect_differ` 只能放三類**（其餘必須和 builder 一致）：
  1. 埠名是整字（IN／OUT／CK）——`port_label` 自動處理（§2A）
  2. 數值與合成字（`50 Ω`、`V_DD = 1.8 V`、`C_1/2`、`2L_1`）——`plain()`／`name_suffix()`／`split_name()`（§4）
  3. 方塊標題、層名（VCO、Latch、P+）——`plain()`（§5）
- 文字上不了色，整張圖維持全黑（§4）。

## 6. 電源軌（§7）

- 有軌就不放 `vdd-port`；用 `f.rail()`，兩端外伸 20，端點 junction 進 `rail_ends`。
- 標籤用 `power_label` 掛在端點 junction；軌上不畫圓點（網站也不畫）。
- 接地軌要變粗：`powerDomain` 寫 `"vdd"`、`name` 寫 `"VSS"`。

## 7. schema 會擋的（§6）

| 錯誤 | 解法 |
|---|---|
| 埠沒有 cell terminal | `f.terminal()` 宣告，標籤用 `port_label` |
| `reference` 重複 | 第二顆會自動走 drafting text（`unbound`） |
| 電源符號帶 `reference` | `gnd()`／`vdd-port` 不給名字 |
| 元件不在格線 | 座標一律 10 的倍數 |
| 空字串名稱 `too_small` | 沒標籤的元件仍要給名字（如 `I_1`），只是不下 `inst_label` |

## 8. 稽核失敗時看哪裡

| 訊息 | 意思 | 先看 |
|---|---|---|
| `legs N` | 有段 >40 沒列進 long_haul | 明細印在上面；真的需要就加進 long_haul |
| `labels N` | 標籤壓線或歸屬不清 | §3D 規則 1、2 |
| `on-wire N` | 元件坐在別 net 線上／線穿元件 | §3I 規則 5 |
| `tees N` | 三向接點缺 junction | §3H 規則 4 |
| `shorts N` | 兩 net 共線 | §5 |
| `schema: FAILED` | 網站改版 | `python -m toolkit setup`，再看 §2C |
| `label X differs` | 標籤不是 builder 格式 | §2C 三類才可進 expect_differ |
| `X sticks out of the viewbox` | 零件或標籤超出預覽範圍（字寬照 DejaVu 量） | 依印出的超出量放大 `viewbox` |
| `~ X has both pins on net-…` | 兩端元件兩腳同一條 net＝網表把它短路（畫面看不出來） | 通常是串聯元件兩端該分兩條 net；照原稿刻意如此才保留 |
