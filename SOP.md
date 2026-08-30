# SOP — 用 Analog Canvas 畫課本級電路圖

> 建立 2026-08-28。基準成品：`Razavi_Fig_9_83_CG.icproj.json`（Razavi 習題 68 Fig. 9.83 共閘級）。
> 做法＝**離線產生 `.icproj.json` → 使用者在網站 File / Import Project File 匯入**。
> 網站正式站的 Agent／MCP 介面是關閉的（bundle 內 `jp({production:!0,configured:void 0})` → false），所以不要嘗試連線。

---

## 0. 一句話流程

1. `python scan_figure.py <截圖>` — 有原圖才跑。拓樸、鏡射、GAP、密度基準（§3C）。
2. 抄 `gen_fig848.py`，只改 placement / junctions / nets / routes / annotations **五段**（約 140 行）。
3. `python gen_xxx.py` — **這一步就是全部**：六道稽核＋schema 驗證＋標籤比對＋渲染 PNG。
   全部 0 就去看那張 PNG，對了就交付。

```
audits: legs 0 | labels 0 | on-wire 0 | tees 0   (all must be 0)
  schema: VALID (v31)
  labels: OK (3 declared plain)
  png: preview_xxx.png (1770x895)
```

**目標：一張圖 5~10 分鐘。** 省時間與省 token 的四條硬規則：
- **不要分開跑 `validate.mjs` / `check_labels.mjs` / Chrome**：`build()` 已經全包了。
  每一次工具呼叫都要重送整段對話，四次變一次是這裡最大的省法。
  （只想快速跑產物：`AC_FAST=1`；想看完整走線表：`AC_VERBOSE=1`。）
- **`scan_figure.py` 預設已經是精簡輸出**（只印 MOS 表、帶 `GAP` 的走線、junction 圓點、
  密度）。要逐條核對走線時才加 `--full`——那是上百行，別隨手加。
- **不要重讀本檔全文**：照本節走，需要哪節再翻哪節。
- **不要複製產生器骨架**：`from icproj import Schematic`，新圖只寫五段資料。

**絕不跳過稽核。** 每一道都抓到過我自己看不出來的錯。
**也不要用眼睛判讀原圖的鏡射與連接**——那是 §3C 那支腳本的工作。

---

## 1. 真相來源（不要憑印象）

| 要什麼 | 去哪裡拿 |
|---|---|
| 符號腳位座標、外觀 | `toolkit/sym/*.json`，**48 個已全數快取**（2026-08-29）。
Analog Canvas 是活的專案、上游會持續新增符號，所以把 `sym/` 當快取看：
**要用的符號不在裡面 → 跑 `python fetch_symbols.py`（約 4 秒），不要一個一個手動找** |
| 渲染／腳位變換的實作 | 同 repo 的 `apps/editor/src/canvas/canvas-geometry.ts`、`packages/derived/src/*.ts`；
幾何 ground truth 在 `fixtures/visual-reference/razavi-reference-v1/*.json`（**先查 fixture，不要逐檔翻原始碼**） |
| 專案檔 schema（**v31**，2026-08-30 實測） | `toolkit/model.mjs`。**網站會改版，chunk 檔名每次都不一樣**：不要手動找，跑 `python refresh_model.py`（它會走完 bundle、用「執行看看」挑出 model chunk，並告訴你新的 schemaVersion）。版本一落後，匯入就可能整張進不去。 |
| 標籤 RichText 產生器 | 同上，匯出名 `Ws`（`m.f`） |
| 樣式設定檔 | bundle `dist-DMiczVQI.js` 內 `razavi-textbook-v1` 的 typography |
| 別人怎麼畫的 | `GET /api/gallery` 列表 →`GET /api/gallery/{id}` 回傳完整 `projectText` |
| 內建範例 | bundle `library-examples-*.js`（電源軌、power-label 的正規寫法在這） |
| 官方文件 | github.com/cascode-ai/analog-canvas → `docs/`、`fixtures/projects/` |

---

## 2. 符號硬事實（rotation 0；`mirror:"x"` 把 x 取負）

| symbolId | 腳位（相對中心） | 備註 |
|---|---|---|
| `nmos` | D(+10,−20) G(−20,0) S(+10,+20) B(+20,0) | 閘極在**左**；mirror x → 閘極在右 |
| `pmos` | S(+10,−20) G(−20,0) D(+10,+20) B(+20,0) | 同上 |
| `resistor` | `1`(0,−20) `2`(0,+20) | 墨跡 x −4.99~+5.37 ⇒ **標籤 ±13**；本體 40 高 |
| `capacitor` | `1`(0,−20) `2`(0,+20) | 極板 y ∓3.23、半寬 8.05 ⇒ 直立時標籤 ±16 |
| `ground` | `0`(0,−10) | 本體向下延伸到 +17 |
| `port` / `port-filled` | `P`(+10,0) | 圈圈在 −7.09；輸出端要 `mirror:"x"` |
| `vdd-port` | `P`(0,+20) | 有電源軌就不要用它 |
| `current-source` | `+`(0,−20) `−`(0,+20) | 箭頭朝下 |
| `voltage-amplifier` | IN(−40,0) OUT(+40,0) | 三角形，`-23.63,±28.62 → 23.63,0` |

- **元件本體 48×48 單位；通道 bar 高 25 單位。**元件必須落在 10 單位格線上。
- MOS 一律加 `symbolVariantId: "textbook-3terminal"`（隱藏 B 腳）。

### 轉 90 度（橫放的電容／電阻）

`rotation` 的合法值是 **0 / 90 / 180 / 270**，`mirror` 只有 `none` / `x`。
腳位變換 = **先鏡射、再旋轉**，公式照 repo 自己的 `rotatePointByDegrees`：

```
x' = x·cos θ − y·sin θ        θ=90 ⇒ (x,y) → (−y, x)
y' = x·sin θ + y·cos θ
```

所以**橫放的被動元件（rotation 90）：腳位 `1` 在右、`2` 在左**。
`icproj.py` 的 `passive(iid, kind, x, y, label, rotation=90)` 已經處理好；
它的 `pin()` 與 `ink_box()` 都吃 rotation，預覽也會輸出 `rotate(θ)`。
（repo 的 `fixtures/visual-reference/razavi-reference-v1/capacitor-geometry.json`
就記著一個 `capacitor-horizontal / rotation 90`，可當佐證。）

### 符號庫怎麼同步（2026-08-29 建立）

> **鐵則（使用者裁示）：畫的電路出現 `sym/` 裡沒有的符號 → 先抓抓看；抓不到就回報。**
> 三步，不准跳、不准自己畫一個像的頂替：
> 1. `ls sym/` 沒有該符號
> 2. `python fetch_symbols.py`（約 4 秒；上游隨時會有新符號）
> 3. 還是沒有 → **停下來告訴使用者缺什麼**，不要用近似符號代替、也不要自繪幾何

```bash
python toolkit/fetch_symbols.py           # 只補缺的
python toolkit/fetch_symbols.py --force   # 上游改過符號時整批重抓
```

它做三件事：列上游 `packages/symbols/assets/razavi-v1/*.symbol.json`、
平行下載成 `sym/<id>.json`、再拿編輯器的 `razavi-catalog.generated.ts`
交叉比對「catalog 有引用但本地沒有檔案」的 id。

**上游 = repo `main`，且與正式站 bundle 一致**（2026-08-29 雙向 diff 為空，
逐檔位元相同），所以抓 repo 就等於抓正式站，不必碰站上的 Agent／MCP。

### ⚠️ 編輯器調色盤的 53 ≠ 可用符號數（2026-08-29 查清）

使用者看到的調色盤有 **53** 個項目，但符號資產只有 48 個。差額**不是缺檔**：

| 調色盤分組 | 數量 | 說明 |
|---|---|---|
| Transistors | 6 | nmos／pmos／npn／pnp ＋ **ndmos／pdmos** |
| Passives | 7 | resistor／capacitor／inductor 各含 variable-，另有 inductor-compact |
| Power and Ports | 5 | ground／vdd-port／**vdd**／port／port-filled |
| Sources | 2 | voltage-source／current-source（`pulse-voltage-source` 正式版隱藏） |
| Switches | 3 | ideal-／closed-／voltage-controlled- |
| Analog Blocks | 6 | opamp 系 3＋voltage-amplifier＋comparator 系 2 |
| Logic Gates | 10 | |
| Signal Flow | 5 | adder／multiplier／integrator／unit-delay／quantizer |
| **Annotations** | 7 | **不是元件**：annotation-arrow／line／rectangle／circle／polarity-both／text-plus／text-minus，屬 `drafting` 物件 |
| Extended Devices | 2 | diode／zener-diode |

換算：**48 資產 − 1（隱藏的 pulse-voltage-source）− 4（`*-inputs-swapped` 不進調色盤）
＋ 3（`vdd`／`ndmos`／`pdmos` 寫在程式碼裡）＋ 7（標註工具）= 53**。
⚠️ 這三個「寫在程式碼裡」的**都不能放進專案檔**，見下一小節。

本地 `sym/` 現有 **49** 個檔＝48 個資產 ＋ 從 bundle 抽出的 `vdd`。
**`ndmos`／`pdmos` 抽不出來**：整包部署程式與 repo 原始碼裡都只有字串引用
（預設變體表、排序表），沒有任何幾何定義——它們要靠 PDK 提供。真的需要時
再回頭查，不要以為是漏抓。

### 🚫 `vdd` 不可以用——**用 `vdd-port`**（2026-08-30 事故）

`sym/vdd.json` 存在**不代表可以放**。網站的符號 **catalog**（帶 `assetPath` 的那份清單）
裡沒有 `vdd` 這一筆，只有 `vdd-port`；`vdd` 的幾何躺在一個延後載入的 chunk
（`component-parameters-*.js`）裡，是遺留物。

後果：用了 `vdd` 的專案**通得過 zod schema、`validate.mjs` 全綠，但匯入網站就是進不去**
（畫布空白，沒有錯誤訊息）。`Diff-amp_shunt-peak_RC-degen` 為此卡了兩輪。
兩者的 `P` 腳都在 (0,+20)，直接替換即可。

`icproj.Schematic.UNPLACEABLE` 已把 `vdd`／`ndmos`／`pdmos` 列黑名單，
`f.place()` 用到就直接丟例外。

**通則：懷疑某個 symbolId 能不能用，去查 catalog，不是查 `sym/` 有沒有檔案。**

```bash
grep -c 'symbolId:`<要查的 id>`,' <bundle chunk>    # 0 = 不能用
```

`drafting.objects` 的合法 `kind` 是 **`arrow` / `text` / `rectangle` / `circle`**
（model.mjs 的 zod enum）；`icproj.py` 目前包了前兩種。

## 3A. 絕對排版規則（**優先用這個，不需要原圖**）

> 目標：沒有原圖也能直接畫出課本級的密度。以下常數是 Fig 9.83 / 9.34 多輪校正後的定案。
> 有原圖時只用它決定**拓樸與器件左右擺法**，間距一律照本節，不要照原圖比例縮放。

**基本盤**：格線 10 單位；所有元件座標必須是 10 的倍數。

```
GAP_MIN        = 20   兩個相鄰元素之間的走線下限
GAP_JUNCTION   = 20   junction 兩側各留 20（所以夾一個節點＝40）
STUB_GROUND    = 10   源極/射極 → 接地符號（接地符號自帶 10 引線）
STUB_PORT      = 20   節點 → 埠（埠符號自己還會畫約 15，看起來共約 35）
                      **接到 BJT 基極時用 10**：BJT 符號自帶 23 單位的基極引線
STUB_RAIL      = 20   電源軌 → 元件引線
OVERHANG_RAIL  = 20   電源軌兩端各外伸一格
LABEL_INK_GAP  = 8    標籤離「該側實際墨跡邊緣」的距離 ← 這才是規則本體
LABEL_PORT     = 14   埠標籤離埠中心（圈圈外緣 9.57 → 淨空 4.4）
```

**元件標籤怎麼擺（定案於 Fig 9.83，Fig 9.34 沿用）**

規則只有一句：**標籤錨點 = 該側實際墨跡邊緣 ＋ 8 單位**。
「實際墨跡」＝ primitive 的極值，**不是 viewBox，也不是元件中心**。
標籤一律放在**汲/源（D/S）或集/射（C/E）那一側**，不要放閘極／基極那側。

| 符號 | 該側墨跡到中心的距離 | ⇒ 標籤錨點（從中心算） |
|---|---|---|
| MOS `textbook-3terminal` | 10.6（source-arrow 尖端） | **±18** |
| BJT `npn` / `pnp` | **0**（C/E 引線就在中心線上） | **±8** |
| `current-source` | 10.76（圓半徑） | ±18 |
| `port` / `port-filled` | 9.5（圈圈外緣） | ±11 |

> **±14 為什麼不照課本**：課本的圈圈直徑 9.6 單位、我們只有 5，所以課本那個
> 1.1 單位的淨空搬過來會顯得擠（使用者 2026-08-29 反映並確認 ±14 合適）。
> 用 `icproj.LABEL_PORT`，不要寫死；在編輯器裡拖會跳整格 10（變 ±21，太遠）。
>
> ⚠️ **比對使用者存檔前先看時間戳**：他的匯出可能是從「改動之前」的專案存的，
> 差異不一定代表他改了什麼。本檔曾據此誤判一次。

方向：unmirrored 的 MOS/BJT 墨跡在中心右側 → 標籤放右（`alignment:"start"`, +值）；
`mirror:"x"` 的墨跡在左側 → 標籤放左（`alignment:"end"`, −值）。`dy` 一律 `+5`。

**要讓兩條埠引線「看起來一樣長」，比的是可見長度，不是 route 長度。**
可見長度 = route ＋ 埠符號自帶約 15 ＋（若接基極）BJT 自帶 23。
所以「埠接 BJT 基極」和「埠接節點」要湊等長時，前者的 route 用 10、後者用 30。
Fig 9.34 實例：v_in 可見 47.7、v_out 可見 44.6。

**列距（垂直）** = 上一個元件的下腳位 → 下一個元件的上腳位：

| 兩者之間 | 距離 |
|---|---|
| 沒有節點 | 20 |
| 夾一個 junction | 20 + 20 |

器件本身的腳位跨距：MOS 40（D↔S）、BJT 60（C↔E）、被動 40。

**欄距（水平）**：真正的約束是**下面自檢表的「任何一段直線 ≤ 40」**——照它排就對了。
具體：相鄰兩欄的**同類基準線**（MOS 的 D/S 欄、BJT 的 C/E 欄）相距 **40**，
就不必宣告長程。下限是 GAP_MIN 20（畫出來的邊緣之間）。
實測邊緣間距：Fig 9.34（BJT）50、70；Fig 10.35（MOS）39、20。
夾一個 bus junction 時，junction 距離兩側器件邊緣各 ≥ 20。

**⚠️ 欄距＝「太鬆」的真正量測值（2026-08-30 定案）**

「排太鬆」是老毛病，因為舊的密度指標（元件高 ÷ 圖高）在沒有 MOS 的圖上根本沒意義。
真正該看的是**相鄰元件欄的中心距**，`build()` 每次都會印：

```
  pitch: columns 40/60/60/70/70/60/20/40/70 | rows 40/10/10/20/50/30
```

- **上限 80**。超過會被標 `<-- N column gap(s) over 80`，必須有結構性理由
  （方塊圖的功能方塊、虛線子系統框、電源軌跨距）才留。
- **手繪線（§3I-b）實測值：50~70**——連續三次校正收斂到這裡，見 §3I-b。
- 列距不設上限（由 §3A 的列堆疊決定），但同樣印出來備查。

**⚠️ 對稱架構：中線上的東西一定要在正中央（使用者 2026-08-30 提醒）**

差動對、對稱負載、兩側鏡射的任何結構——**跨在中間的元件（退化網路、尾電流、
中央的 V_DD 埠、`V_out` 標籤）必須落在兩側欄的正中點**。
**若網格讓中點落不到 10 的倍數上，去調整兩端的欄位，不要把中間的東西挪開。**
例：左欄 320、右欄 460 → 中點 390 ✓。若左欄 320、右欄 450 → 中點 385 不在格線，
就把右欄改成 460，而不是把中間元件放 380 或 390。

同一張圖裡**所有**在中線上的物件共用同一個中心 x，包括 drafting text。

**⚠️ 匯流排列不可以跟腳位同一列。** junction 與 terminal 若落在同一座標，
就只能寫出零長度 route，第 5 節的自檢會直接擋下。正解：**匯流排列放在腳位列
上方（或下方）10 單位**，每個器件用一條 10 單位的 riser 接上去。原圖本來就是
這樣畫的（Fig 10.35 的節點圓點畫在汲極腳位上方 3 單位）。

**標準列堆疊（差動對／單端皆可直接抄，Fig 10.35 定案）**

| y | 內容 |
|---|---|
| 100 | 電源軌 |
| 140 | 上方電流源中心（+腳 120、−腳 160） |
| 180 | 輸出抽頭 junction |
| 200 | 上方匯流排列 |
| 210 | D 腳位 |
| **230** | **器件中心** |
| 250 | S 腳位（＝共源匯流排列） |
| 280 | 尾電流匯流排列（**離上一列 30**，才塞得下夾在中間的節點名，見下方規則 1） |
| 320 / 310 | 兩個尾電流源中心（**故意錯開 10**：靠外那顆低 10，課本就是這樣） |
| 360 / 350 | 對應的接地符號中心（墨跡底 377） |

圖高 100→377 ＝ 277，通道 bar 25 ÷ 277 ＝ **9.0%**（下限 9%）。
只有一個尾電流源時，尾匯流排可回到 270、整體再縮 10。

## 3D. 「擠」是什麼——三種可量的東西（2026-08-29 整理）

使用者說過三次「擠／鬆」，每次原因都不同。**不要憑感覺調，先看 generator 印出來的
三組數字，對應到下表哪一種。**

| 使用者的話 | 實際是哪個量 | 怎麼看 | 怎麼修 |
|---|---|---|---|
| 「太鬆」「密度不夠」 | **元件高 ÷ 圖高** 低於原圖 | `build()` 印的 `... / figure height = X% (original Y%)` | 把「端點→節點」壓到 10；腳位重合處直接省掉走線 |
| 「不知道標籤屬於哪顆」 | **標籤到鄰居的距離** | `! LABEL AMBIGUOUS` | 把那一側的**同型**鄰居往外拉一格 |
| 「整張圖看起來有點擠」 | **某兩個不相干的墨跡靠太近** | `tightest clearances:` 排序表 | 拉開排第一名的那一對 |
| 「中間反而顯得太空」 | **一條什麼都沒有的長線橫跨空白** | 自己看走線表：>60 且線上沒元件 | 把線末端那顆元件往內移（只有它位置自由時才適用） |

> 最後一列**沒有做成自動檢查**：電源軌、尾電流匯流排、全域回授這類結構性長線
> 兩端位置被拓樸釘死，本來就得跨過整張圖，自動報會全是誤報。
> 判準是「**線末端那顆元件能不能自由移動**」——訊號源、埠這種葉節點可以，
> 匯流排兩端的節點不行。Fig 8.48 的輸入線 80→60 就是這一條。

`icproj` 每次 build 都會印：

```
  ~ port VIN sits only 10 from its node (comfort 20)
  tightest clearances: ISS1/note-p 8.7, VOUTL/note-vout 11.1, ...
  ! 1 pair(s) closer than 8 units
```

規則：
- **埠引線 `STUB_PORT_COMFORT = 20`**。10 是格線下限，會讓「標籤＋圈圈」整團貼著電路
  ——Fig 8.57 的「擠」就是這個，使用者自己把埠往左移 10 修好的。
- **任兩個不相干墨跡的淨空 `CROWD_MIN = 6`**（程式裡的實值）。低於就會被列出來。
- 稽核會自動排除兩種**不算擠**的情況：①**同一個 net 的元件**（它們本來就該靠在一起，
  甚至腳位重合）②**標籤與它自己的元件**（那個間隙由 `LABEL_INK_GAP` 決定）。
  值標籤（`500 Ω` 這種 drafting text）要用 `f.text(..., owner="R500")` 宣告歸屬，
  否則會被當成無主標籤誤報。

**排序表怎麼用**：只看第一名。它就是這張圖最擠的地方；如果它 ≥ 8 而且使用者仍說擠，
那問題不在局部，去看密度那一列。

**⚠️ 三條「一定會被使用者退件」的規則（2026-08-29 裁示，已寫進自動稽核）**

> **已作廢**：曾有一條「走線必須沿腳位 `direction` 離開，否則編輯器標紅」的規則。
> 使用者 2026-08-29 裁示：**線變紅不影響匯出的圖片，可以無視**。該檢查已從
> `icproj` 移除，不要再為了消紅而改版面。

0. **節點名（X、Y、P）先用電路判斷它指哪個節點，不要用截圖上「離誰近」判斷。**
   課本標一個節點名，是因為那個節點在分析上重要：
   兩級放大器→**級間節點**（前級集/汲極＝次級基/閘極）、
   差動對→**尾節點**、串疊→**中間節點**。
   Fig 5.170 的 X 就是 Q_1 集極＝Q_2 基極那個級間節點（2026-08-29 使用者指正：
   我誤判成旁邊的射極節點）。判對之後，標籤擺在該節點附近的斜上方。
   **稽核只檢查「不重疊」，判斷指哪個節點要自己想。**

0b. **有標名字的節點就要有黑圓點**，圓點來自三個方向都碰得到的 junction。
   稽核 `tees` 會抓（§3H 規則 4）；它報 0 但畫面仍缺點，就是兩條線走同一欄
   （Fig 14.36(b) 的 R_3 改走 x=690 才讓 Y 有點）。


1. **文字絕不壓線。** 節點名（`P`、`Q` 這種）夾在兩條橫線之間時，
   **兩條線至少要隔 30 單位**（字高 14 ＋ 上下各 8），標籤垂直置中：
   `baseline = 兩線中點 + 7`。線距不夠就**把下面那條線往下移**，不要挪文字。
   Fig 10.35 就是把尾電流匯流排從 270 移到 280 才擺得下 `Q`。
2. **標籤歸屬不得有歧義。** 一顆被標籤的器件若**兩側都有同類器件**，
   標籤那一側的鄰居墨跡離**文字外緣**必須 **≥ 17 單位、且 ≥ 2 倍「文字到自己器件」的距離**。
   （只比**同型**元件：把 `R_5` 讀成 opamp 的名字不是真風險，`M_3` 夾在兩顆 NMOS 中間才是。）
   （Razavi 實測：`M_3` 離自己 3.9、離 M1 16.8；`M_4` 離自己 3.8、離 M2 17.2。）
   不夠就**把那個鄰居往外拉一格**，代價是該側 bus leg 變長 → 進 `long_haul` 並註明理由。

**成品自檢（源自這兩張的定案值）**

| 指標 | 目標 |
|---|---|
| 任何一段直線走線 | **≤ 40 單位**，除非是宣告的長程（電源軌、全域回授匯流排、參考電流下拉、鏡射匯流排） |
| **器件本體 ÷ 圖高** | MOS 圖 10% 上下；原圖更鬆就無視原圖，列數多（6~9 列）就達不到，別硬追（§3G） |
| 整圖長寬比 | 跟著拓樸走，不強求 |

**⚠️ 密度＝跟原圖比，不是套一個固定百分比（2026-08-29 使用者裁示）**

老毛病是「排太鬆」。判定方法固定成一句話：
**量原圖「某個元件的高度 ÷ 整張圖的高度」，自己的圖要做到同一個比例。**

> **⚠️ 那是下限，不是上限**（使用者 2026-08-29 再次裁示）。**原圖本身排得鬆時，不要照抄它的鬆。**
> Constant-g_m 那張原圖只有 8.5%，我照做出 7.6%，使用者退件說「太開了，密一點」——
> 壓到 **10.1%** 才通過。實務門檻：**MOS 圖做到 10% 上下**，原圖比這更鬆就無視原圖。
> 壓密度的手法見下方「壓密度的兩招」，先把「端點→節點」降到 10。

```python
f.build(..., density_ref=("OA1", 34.5))   # 34.5% 是從課本頁面量到的
```

`icproj` 會印 `OA1 height / figure height = 29.3%  (original 34.5%)`，
低於原圖的 85% 就標 `<-- TOO LOOSE`。實測值備查：

| 圖 | 參考元件 | 原圖比例 |
|---|---|---|
| Fig 10.35 / 9.83（MOS） | 通道 bar 25 單位 | ≈ 9.4% |
| Fig 14.36(b)（opamp） | 三角形 50 單位 | **34.5%** |

**壓密度的兩招**

1. **把「端點→節點」的間距降到格線下限 10**（§3A 預設的 20~30 只是舒適值）。
   Fig 14.36(b) 靠這招把級距從 220 壓到 170——這是格線 10 的物理下限：
   `OUT −10− 節點 −10− 電阻(40) −10− 節點 −10− IN ＝ 80`。
2. **兩個腳位放同一座標，走線整條省掉**（使用者 2026-08-29 親手示範）。
   例：接地符號的 `0` 腳與電阻的 `2` 腳同點 → 不用 route，省 10 單位；
   `vdd-port` 的 `P` 腳與電阻的 `1` 腳同點亦然。Fig 8.69 用這招省了 20 單位、
   長寬比從 1.57 修正到 **1.47**（原圖 1.46）。
   `icproj` 的自檢認得這種接法（同一 net 內座標相同的兩個 terminal 視為已連）。
   ⚠️ 注意分辨：**junction 不可以壓在 terminal 上**（零長度 route），
   但 **terminal 壓 terminal 是合法且推薦的**。

**⚠️ 被動元件多的圖，密度天生達不到課本比例——不要硬追**

符號庫與課本印刷的比例並不一致（Fig 8.69 實測，以 opamp 三角形定尺）：

| | 課本 | 符號庫 | 比值 |
|---|---|---|---|
| opamp 三角形 | 50 單位 | 50 | **1.00×** |
| npn | 60 單位 | 60 | **1.00×** |
| **電阻（腳到腳）** | **12.8 單位** | **40** | **3.11×** |
| `vdd-port` 引線 | 21.9 單位 | 30 | 1.37× |

主動元件與課本完全一致，但**電阻是課本的 3.1 倍**。所以垂直鏈上串兩顆電阻的圖
（Fig 8.69）最多只能到 25.7%，課本是 35.6%——**這時看長寬比是否對上就好**，
`TOO LOOSE` 警告在這種圖是誤報。

`gen_fig934.py` 的 audit 就是這個絕對版：印出每一段 leg，超過 40 且不在 `LONG_HAUL` 白名單就標 `<-- LONG`，**不需要原圖**。

---

## 3B. 有原圖時的比例尺換算（輔助手段）

`scan_figure.py` 已經直接給你 `scale` px/unit（§3C），**不需要自己算比例尺**。
留這一節只為記住一件事：畫布符號的引線比課本長、本體比課本小，
**單一比例尺無法同時對上兩軸**（Fig 9.83：K_V = 0.430、K_H = 0.535）。
所以**截圖只決定拓樸與器件左右擺法，間距一律照 §3A 的絕對值**，不要照原圖比例縮放。

## 3C. 從截圖抽拓樸：**一個指令，不要用眼睛判讀**

```bash
python toolkit/scan_figure.py "path/to/screenshot.png"
```

這支取代舊 §8-2 的「放大 5–6 倍逐顆看」。它印的每一項都是量出來的，
不會像目視那樣看錯。**畫圖前先跑它，再開始排座標。**

**預設精簡**：走線表只印帶 `GAP` 的那幾筆、圓點只印判定為 junction 的，
其餘各印一行計數。`--full` 印全部——**只有在「目視判讀的每一條線都要能在線段表裡
找到對應」（§3E）時才需要**。

| 它印什麼 | 怎麼用 |
|---|---|
| `scale` px/unit | 由最高的實心 bar ÷ 25 單位得到（通道 bar 恆為 25） |
| MOS 表：centre / **mirror** / D/S 欄 / 閘極腳 | mirror 由「閘極 bar 在通道 bar 的左邊還是右邊」判定——**這是以前唯一會判錯、且一錯就要重畫的地方** |
| H / V wires，含 `<-- GAP` 標記 | **同一座標出現兩筆＝中間有斷口＝那兩塊沒有連在一起** |
| Solid blobs 依面積分三類 | 圓點偵測核依線寬自動縮放；低解析度截圖也抓得到 |
| **DENSITY REFERENCE** | 電路的 bbox、**aspect**、以及各標準元件高度佔圖高的百分比 |

**三個一秒定案的判讀**

1. **diode-connected 還是 cross-coupled**：看那條上方橫線有沒有 `GAP`。
   Fig 10.35 印出 `y=333.5 x 431..619` 與 `x 668..855  <-- GAP 49 px` →
   中間沒有跨接 → 兩顆各自 gate 接自己的 drain。有跨接才是交叉耦合。
2. **交叉還是節點**：交叉處**沒有圓點就是交叉**。Fig 10.35 有 (643,434)、
   (438,485) 兩個點，但 (643,485) 沒有 → I_SS2 的直立線只是穿過尾電流匯流排。
3. **鏡射**：直接讀 MOS 表的 mirror 欄。閘極朝外的差動對＝左 `none`、右 `x`；
   閘極朝內的負載對＝左 `x`、右 `none`。

**密度基準怎麼用（省掉一輪重排）**

它會把整頁依空白列切成數個區塊，**取最高的那個當電路**（題目文字很寬但矮、
圖說更矮，都會被排除；它會把所有區塊印出來讓你核對）。輸出長這樣：

```
  aspect (w/h)  1.46   <- match this
  scale 2.880 px/unit  ->  figure is 247 x 169 units
      MOS channel bar         14.8%
      opamp triangle          29.6%      <- 這張有 opamp，就用這行
      BJT                     35.6%
      resistor pin-to-pin     23.7%
```

挑「這張圖有的那顆元件」那一行，直接填進 `f.build(density_ref=("OA1", 29.6))`。
**沒有 MOS 的圖沒有自動 scale**：量一下 opamp 三角形（或 BJT）的像素高度，
用 `--ref=140:50`（opamp＝50 單位、BJT＝60、MOS 通道 bar＝25、電阻腳到腳＝40）。

換算到畫布座標：`單位 = (px − 基準px) / scale`，四捨五入到 10；
但**間距一律照 §3A 的絕對值**，截圖只決定拓樸與器件左右擺法。

## 3E. 路線 3a：**非 Razavi 風格的印刷圖**（Sedra、Gray、論文圖）

> 2026-08-29 以一張 19 顆電晶體的比較器定案。**輸入不同，輸出品質不變**：
> 排版（§3A）、字級（§4）、四道稽核（§5）一個字都不用改，分岔只在「怎麼拿到拓樸」。

**怎麼認得出是這條路線**：`scan_figure.py` 印

```
no filled bars -- generic style; 19 MOS found by paired strokes
scale: 2.680 px/unit  (body 67 px = channel bar 25 units)
```

掃描器**照樣給你完整的 MOS 表**（centre／mirror／D/S 欄／gate pin）與 scale。
它靠的是這類畫法的通則：**MOS ＝一對等高、相距 8~30 px 的平行豎線**（閘極板與通道），
汲/源引線從通道兩端離開。**不要用眼睛數電晶體**——19 顆手讀既慢又會錯。

| 掃描器給不給 | 怎麼補 |
|---|---|
| 位置、mirror、D/S 欄、scale | **給**，直接抄，19/19 實測與人工判讀吻合 |
| **PMOS／NMOS** | **不給**。看閘極上的**空心圈**（有＝PMOS）；再用「源極接 VDD 還是接地」交叉驗證一次 |
| 連線 | H/V 線段表＋圓點表＋GAP 都照常可用。**目視判讀的每一條線都要能在線段表裡找到對應**，找不到就是你看錯了 |

**密度基準照樣有**：body 高度就是課本的通道 bar（25 單位），所以
`原圖 MOS 佔比 = 25 ÷ (圖高 px ÷ scale)`。上例：25 ÷ 245 = 10.2%。

### ⚠️ 這條路線的五條規則（2026-08-29，19 顆那張定案，含使用者退件）

1. **原圖的斜線用 `f.construction(id, x0,y0, x1,y1)` 畫**。routes 一律正交
   （編輯器本身也是），所以交叉耦合那個 X 沒有可走線的形式。
   兩端的 junction 只被一條 route 碰到 → 放進 `rail_ends` 豁免。
   預覽器會照 wire 粗細畫出來。
   （*註：construction-line 不導電，匯出的網表少這條連接。當圖用無妨——
   使用者 2026-08-29 裁示只有出圖需求；哪天要餵模擬再回頭處理。*）
2. **長寬比對不上是正常的，不要硬追**（與 §3A「被動元件多的圖」同一個道理）。
   Razavi 的 MOS 連閘極引線寬 30 單位，這類圖只有 17.5 單位，**每顆寬 1.7 倍**；
   欄數一多就必然更寬。上例原圖 aspect 2.63、成品 3.61。**看密度（9.4% vs 10.2%）**。
3. **標籤擺不下時，用 `dx=43` ＋ `alignment "end"`，不要加寬欄距**（使用者 2026-08-29 校正）。
   多級鏈狀電路（反相器鏈、電流鏡陣列）每一級都會觸發 §3D 規則 2（標籤離鄰居 ≥17），
   照著加寬會愈追愈寬。正解是把標籤**貼著自己的器件**放（`dx=43`，右緣落在下一級之前），
   離自己 ≈0、離鄰居 17——歸屬反而更清楚。**放上下也可以，但欄距一緊就會壓到源極引線**。

3b. **原圖沒有元件標籤時，欄距可以直接照原圖收緊**——§3D 規則 2 是標籤的約束，
   沒有標籤就沒有這個約束。（Constant-g_m 那張 7 顆、零標籤，欄距 80/110 一次過關。）
   但**器件名仍要寫成有底線的形式**（`P_1` 而不是 `P1`），即使不畫出來：
   沒有底線的字串編輯器的產生器會另外處理，`check_labels` 會整批報 DIFFER。
4. **接地符號一定要全部對齊在同一排**，包含負載電容那一顆（使用者退件）。
   不要因為某顆源極比較高就把它的地拉高——整排對齊是課本的視覺特徵。
5. **元件不可以坐在別的 net 的走線上**（使用者退件；當時四道稽核**全部沒抓到**）。
   V_IN− 埠的腳位正好落在 M5 閘極走線上、長偏壓線走 y=210 又貫穿 M7／M11 的源極腳，
   一張圖四處。→ `icproj` 已新增第五道檢查（見 §5），
   **長距離匯流排要挑一條沒有器件的列**（上例改走 y=190，在輸入對之上）。

## 3I-b. 路線 3b：手繪圖（2026-08-30 開張）

**`scan_figure.py` 不能用。** 筆跡照片上它把 `V_in` 的圈、下標、筆畫都判成 junction
圓點（實測 44 個），走線表也是雜訊。**手繪圖只能放大用眼睛讀。**

流程：
1. 原圖直接看一遍，抓出整體骨架（哪幾條匯流排、幾個節點）。
2. **讀不準的地方裁切放大 3~4 倍**（PIL crop + LANCZOS）——二極體／電流源方向、
   接地符號是不是橫躺的、標籤屬於哪個元件，都是這樣確認的。
3. **不要停下來問使用者**（使用者 2026-08-30 裁示）：**不確定就先照自己的判讀畫**，
   他看 PNG 再糾正。問一輪的成本比畫錯一次高。
4. 其餘完全照 §3A 的絕對間距排，不要模仿手繪的比例。

**手繪圖的專屬注意事項**
- **形狀清楚的地方就照著畫**（使用者 2026-08-30 第一次退件）。第 4 點的「間距照
  §3A」指的是**距離**，不是**位置**：頁面把 `R_E` 畫在射極匯流排的**正中間**，
  就不要因為省事把它掛在 `r_π1` 正下方。看得懂的骨架＝規格。
- **橫躺的接地擺在它所在那條帶的正中間**（使用者裁示）。例：上排 100、接地匯流排
  210 ⇒ 那根引線走 **150**（中點 155 取格線），不要貼著上排。
- **一條「超出兩端」的粗橫線＝電源軌，不是 `vdd-port`**（使用者 2026-08-30 指正）。
  判準就是它有沒有伸出最外側的分支點；有就照 §7 畫軌（`presentation:"power-rail"`
  ＋兩端外伸 20 ＋端點 power-label），**不要放一顆 `vdd-port` 符號充數**。
  ⚠️ 手繪圖常常不畫任何電源符號，只畫那條線——**要自己認出來**。
- **原樣重畫**：頁面上畫錯或多餘的東西（例：兩端都接地的受控源）**照畫**，
  不要自己「修好」——那是使用者的作業內容，不是我的判斷範圍。
- **沒有標籤的元件仍要有 netlist 名字**：`f.isrc(iid, x, y, "")` 會讓 schema 以
  `too_small` 退件（空字串）。給它 `I_1` 這種名字、然後**不要**下 `inst_label` 就好。
- **不要畫太寬**——這條有硬數字：**欄距 50~70**。被退三次才收斂，過程留著當標尺：

  | 版本 | 欄距 | 寬 | 使用者 |
  |---|---|---|---|
  | 第一張初稿 | 0/120/80/100/80/100/70 | 643 | 「太寬」，親手收成 40~70（寬 543） |
  | 第二張初稿 | 80/80/70/70/70/70 | 499 | 「密度還是太低」 |
  | 第二張再收 | 70/70/80/60/60/60 | 459 | 「再稍微拉進一點點」 |
  | **定案** | **60/60/70/50/50/50** | **399** | 長寬比也剛好對上原圖（1.43 vs 1.45） |

  **開畫前先決定欄距，不要排完才回頭壓。**
- **電壓標註（`V_1` 的 `+`／名稱／`−`）擺在「量測端口那一欄」**——不是端口外面，
  也不是縮到中間。使用者兩次校正才定案（2026-08-30）：**正上方是那顆探針、
  正下方是回流的匯流排**，這個電壓才有指涉。
  例：探針在 x=300 ⇒ `+`／`V_1`／`−` 全部放 x=300。
- **量測探針用空心 port**，不要 `port-filled`：`f.port(iid, x, y, mirror="x")`
  ——鏡射是為了讓圈圈落在引線的**遠端**，不是貼著節點那端。
- **接地不必對齊同一排**：§3E 規則 4 是印刷圖的視覺特徵；手繪圖各分支長度不同時
  照頁面走。

**這條路線要不要跟前面分家？不用**（2026-08-30 討論）。
會互相污染的只有共用引擎 `icproj.py`，而 `regress.py` 就是為此存在：
26 張逐位元比對，改壞哪一張當場現形。**規則本來就是分節管轄的**——
§3A 共用、§3E 管 3a、§3I-b 管 3b；衝突的條目（接地要不要對齊、要不要照原圖形狀）
各自寫在自己那節。**分開程式只會讓共用的修正要改兩份。**

## 3F. NAND／NOR 電晶體級電路的潛規則（2026-08-30 使用者裁示）

**只適用於 NAND／NOR 這類邏輯閘的電晶體級畫法**，其他電路照舊「同一個訊號的閘極接在一起」。

- **一個訊號驅動多個閘極時，每個閘極旁邊各放一個自己的埠**，埠的腳位與閘極腳位
  **重合（pin-on-pin），完全不畫線**。不要用「一個埠 ＋ 長豎線繞去餵兩處」。
  課本就是這樣印的（同一個 `A` 出現兩次），而且圖會窄很多：
  實測 NAND2 從 427 寬縮到 267、NOR2 從 407 縮到 257。
- 網表上這些埠仍宣告在**同一個 net**（`net-a` 含兩個 port 與兩個閘極），
  靠 pin-on-pin 成立連接，所以自檢與網表都是對的。
  每個埠各需要一個 cell terminal，名字可以同名。
- 串接的兩顆（NAND 的 M_N1/M_N2、NOR 的 M_P1/M_P2）**腳位間距 10~20 就夠**。
- 輸出埠貼著輸出節點放（離節點 100 以內），不要拉到圖的最右邊。

## 3G. 電感／可變元件／方塊圖／剖面圖（2026-08-30，四張論文圖定案）

**新增的繪圖能力**

- `f.rect(id, cx, cy, w, h, style="solid"|"dashed")` — drafting 矩形。
  用途：方塊圖的 FF／Latch／VCO 這種**沒有符號的功能方塊**，以及 ESD 論文
  常畫在電路旁邊的 P+/N-WELL/P-WELL/N+ 剖面圖。預覽器會照 wire 粗細畫出來。
- **方塊沒有腳位**，所以每一條接到方塊的線都要**在方塊邊緣放一個 junction 收尾**，
  那些 junction 只被一條 route 碰到 → 一律列進 `rail_ends` 豁免。
- 三角形要**兩個輸入**（V/I 轉換器那種）用 `comparator-unmarked`：
  `voltage-amplifier` 只有一支 IN。

### ⚠️ 四個會讓圖畫錯又不報錯的坑

1. **旋轉 90 度的被動元件：腳位 `1` 在右、`2` 在左**（§2 早就寫了，我還是接反）。
   **症狀很好認**：走線從左邊的節點直接畫到右邊那支腳，**整條線穿過線圈或極板**。
   自檢抓不到（電氣上是對的）。左邊的節點接 `2`、右邊接 `1`。
2. **symbolId 不等於 deviceClass**。`variable-resistor`／`variable-capacitor` 是
   符號名，網表的 `deviceClass` 只吃 `resistor`／`capacitor`——用 `f.passive()`
   會把符號名塞進 deviceClass，被 schema 擋下。這兩個要用 `f.place()` 自己寫 binding。
3. **橫放的接地符號**：`rotation=90` → 腳位在右、本體朝左；`rotation=270` → 腳位在左、
   本體朝右。**本體一律朝離開電路的方向**，接錯會讓接地符號壓在元件上。
   **`rotation=180` 把接地翻過來**（腳位在下、本體在上）——掛在元件上方的接地用這個。

3b. **電流源的箭頭方向：`f.isrc(..., rotation=180)` 把箭頭轉成朝上**，同時 `+`／`−`
   上下對調（`+` 變成在下面）。「從地往節點灌電流」的源就是這樣畫。預設 0 是朝下。
4. **沒有電源網的圖要傳 `extra_evidence=[]`**（純邏輯圖、閘級圖）。
   預設的 connectivityEvidence 會引用 `net-power-vdd`，那個 net 不存在時 schema 直接退件。

### ⚠️ 密度不是尺度無關的指標

`MOS bar 25 ÷ 圖高` 隨電路的**列數**變化：列數越多、圖越高、百分比越低。
本輪四張在**間距已經壓到最小**的情況下仍只有 9.0%／8.4%／8.4%／6.1%——
因為它們有 6~9 層堆疊（軌→電感→電阻→汲極→MOS→源極→退化網路→電流源→地）。

**所以 10% 那條門檻只適用於 3~5 列的圖。**真正尺度無關的規則是 §3A 的間距常數：
端點→節點 10~20、串接兩顆 10~20、器件列間距 60~80、軌距 20、接地列 +10~20。
**先照常數排，再看密度；密度偏低但常數都到位 = 這張圖本來就高，不要再壓。**

## 3H. 方塊圖（block diagram）的七條規則

> 2026-08-30 定案。來源：使用者親手改過 `CDR_architecture` 之後的匯出檔
> （他的版本＝規格，我照抄座標再把編輯時斷掉的 net 補回）。
> 方塊圖跟電晶體級圖用的是**同一套**排版常數與稽核，分岔只在下面這幾條。

1. **方塊一律 100×50**，`f.rect(id, cx, cy, 100, 50)`；標題 `f.text(id, cx, cy + 5,
   "middle", ...)`。上下兩排的中心距 **80**（邊緣間距 30）。
2. **每一條碰到方塊的線都要終止在「方塊邊緣上的 junction」**。方塊沒有腳位，
   邊緣座標要自己算：`cx ± 50`。FF1 在 cx=170 ⇒ 入口 120、出口 220。
   這些 junction 只被一條 route 碰到 → 全部列進 `rail_ends`。
3. **兩個方塊之間要分支時，分支點放在空隙的正中央。**
   FF1 出口 220、FF2 入口 280 ⇒ 往 XOR 的抽頭放 **250**（使用者原話：
   「有的分支我希望在中間」）。
4. **三叉一定要有圓點**（使用者 2026-08-30 裁示，**電源軌除外**）。圓點由 junction 物件產生，
   「一條 route 的轉角 ＋ 另一條 route 從旁邊經過」在編輯器眼裡是兩個獨立幾何，
   **不會畫點**。→ `icproj` 已加自動稽核 `three-way nodes missing a junction`，
   **必須是 0**。**推論：同一條 net 的兩段線不可以重疊共線**——重疊本身就會製造
   一個沒有圓點的三叉（本輪在 NAND2／NOR2／19T 比較器／Fig 14.36(b) 各抓到一處）。
   **電源軌上的分支點不算**（軌上每個抽頭都是三叉，但課本與網站的正式渲染都不畫點，
   見 §8 第 8 條）——稽核已自動排除 `presentation:"power-rail"` 的線。
5. **一條 net 佔一個 x 欄；別條 net 要平行走就往外讓 20。**
   CDR 的 net-d 佔了 x=420，net-b 就繞到 x=440，而不是硬擠同一欄。
6. **回授線進入虛線方塊時，用 `f.arrow()` 疊在線上標方向**（箭頭長 35~45，
   壓在最後那一段上）。讀者才知道訊號往哪走。
7. **虛線子系統框**（`style="dashed"`）要**整個包住**屬於它的方塊與閘；
   標題文字放框內左上角：左緣 +30、上緣 +30。
   ⚠️ 預覽器 2026-08-30 才學會畫虛線，之前一律畫成實線。

**不適用的東西**：方塊圖沒有 MOS，`MOS bar 25 / height` 那個密度指標無意義
（CDR 是 7.6%），不要為了它去壓版面。

## 3I. 電源符號（VDD marker）不要硬連（2026-08-30 使用者裁示）

一張圖上出現**多個 VDD／接地符號**時：**它們同屬一個 net，但畫面上各自獨立，
不要為了「看起來有連上」去補一條線**。符號本身就是連接的宣告。
（ESD／LNA 那張有四個 VDD marker、四個接地，全部不互連。）

**另一句同時定案的**：**有整齊的參考圖時，形狀照它排就好**——不必為了湊長寬比
或密度去改變它的骨架。判斷順序是：拓樸與形狀跟原圖，間距跟 §3A。

## 4. 樣式與文字

```jsonc
"presentation": {
  "styleProfileId": "razavi-textbook-v1",
  "grid": 10,
  "compactness": "compact",          // loose | normal | compact
  "styleOverrides": {                // 每項 0.5 ~ 2.0
    "symbolStrokeScale": 1.5,
    "wireStrokeScale": 1.3,
    "annotationStrokeScale": 1.3,
    "junctionRadiusScale": 1.3,
    "fontScale": 2.0
  }
}
```

### ⚠️ 線寬：symbolStrokeScale 必須等於 wireStrokeScale

`razavi-textbook-v1` 的基準線寬（bundle `dist-DMiczVQI.js`）：

```js
strokes: { wire:1.6, symbol:1.6, normal:1.6, emphasis:2.4,
           ground:…, supply:1.8, powerRail:3.24, annotation:1.6 }
```

**`wire` 與 `symbol` 本來就相同（都 1.6）。**
所以只要 `wireStrokeScale ≠ symbolStrokeScale`，元件與走線的粗細就會差一點點——
放大看得出來，使用者實際抓到過（我曾設 1.5 / 1.3 → 2.4 vs 2.08）。
**三個 scale（symbol／wire／annotation）一律設同一個值。**

- 標籤大小 = `fontScale`（文件層）× `sizeScale`（單一標籤）。
  **編輯器的 A− / A+ 按鈕就是 `sizeScale ∓ 0.1`（夾在 0.5~3.0）**，使用者說「按 N 次 A−」就減 N×0.1。
- 字型是 **sans**：`'DejaVu Sans',Arial,'Helvetica Neue',Helvetica,sans-serif`；
  基準 15.116 px、下標 0.76 倍、基線下移 0.28 em；math 700/italic、plain 400。

### 標籤一律用它自己的產生器，不要手寫 RichText

```python
Rs(t)  = italic(bold(t))                                  # 主字母
Vs(t)  = subscript(italic(bold(t)))  if t.lower() in {dd,ss,cc,ee,bb}
         subscript(bold(t))          otherwise
name(base, sub) = {"runs": [Rs(base)] + [Vs(sub)]}
```

**為什麼**：SVG 渲染器進到 subscript 時硬寫 `{italic:false, bold:繼承}`，只吃**下標內部**的 italic span。
所以 `italic(bold([V, subscript(DD)]))`（italic 在外）會讓 DD 變正體 —— 這是實際踩過的坑。
`V_DD` 在特例清單內 → 整個斜體；`M_REF`／`V_out`／`V_b`／`M_1` 不在 → 下標正體粗（與課本一致）。

### 🚫 顏色：**文字上不了色，所以整張圖不要用顏色**（2026-08-30 實測到底）

手繪頁面常用紅筆標「這一項是分析加上去的」。**照不出來**，別試：

| 對象 | 網站實際行為 |
|---|---|
| **元件本體** | ✅ `styleOverride.foreground` 有效（`f.passive(..., extra_style=...)`） |
| **arrow／rectangle／construction-line** | ✅ `styleOverride.color` 有效 |
| **走線** | ❌ route 只有 `presentation`，沒有顏色欄位 |
| **instance-label** | ❌ schema 的 annotation 沒有 `styleOverride`，整份專案被退（`annotations.N \| unrecognized_keys`） |
| **drafting text** | ❌ **schema 收，渲染器不理**——只有「公式路徑」與「極性標記」會吃 `color`，一般的 runs 走 `re()`，輸出的 `<text>` 根本沒有 `fill`（bundle `dist-CE3Pi34B.js` 的 `De()`），所以永遠是黑的 |

結論：**元件紅、字黑＝看起來像沒做完**（使用者原話）。`f.text(color=)` 與
`f.inst_label(color=)` 現在都會丟例外並說明原因。**要顏色就整張都別上，維持全黑。**

> 這條是三步查出來的：①schema 收了 → ②使用者匯入回報字還是黑的 →
> ③去 bundle 讀 `De()` 才看到 `re()` 那條路徑沒有 `fill`。
> **「schema 過」不等於「畫得出來」**——又一次。

### ⚠️ 數值文字用正體，不要用 `name()`

課本**不把數值斜體化**（`50 Ω`、`= 1.8 V` 都是正體粗）。用 `icproj.plain()`；
電源軌那種「名稱＋數值」用 `icproj.name_suffix("V_DD", " = 1.8 V")`。

**這兩種標籤會被 `check_labels.mjs` 報 `DIFFER`，那是預期的、不要去「修好」**——
編輯器的 `Ws()` 一律把整串斜體化，而我們跟的是課本頁面。已知的固定兩筆：
`V_DD = 1.8 V`（Fig 9.83、7.94）與 `50 Ω`（Fig 7.94）。
`check_labels.mjs` 對**器件名稱**才是權威。

### 標籤放在元件「上方」時的 dy

**縱向的淨空是 1.5，不是橫向那個 8**（2026-08-29 使用者三輪校正定案：
22 → 19 → 17 → 15 才通過；課本頁面實測 5.45 也還是太遠）。
另外要多扣下標往下伸出的量：

```
dy = −( 該側墨跡半高 + 1.5 + 0.28 × BASE )     有下標時；BASE = 19.65 ⇒ 多扣 5.5
                                                無下標就不扣那 5.5
```

例：橫放電容半高 8.05 ⇒ `C_1` 的 `dy = −15`、`alignment:"middle"`、`dx = 0`。

### 字級＝課本字級（2026-08-29 使用者裁示，已定案）

`BASE = 15.116 × fontScale × sizeScale`；現行 `2.0 × **0.58**` → **BASE = 17.53 單位**。
實測 Razavi 頁面的字級就是 17.5 單位（Fig 10.35 的 `M` cap 高 12.28 單位 ÷ 0.70）。

> **既然字級與課本相同，凡是從課本頁面量到的間距都可以直接照抄，不必再乘任何修正係數。**
> （舊制 `sizeScale 0.65` 比課本大 12%，SOP 曾要求所有標籤相關淨空 ×1.2；該規則已作廢。）

寬度**必須查 DejaVu Sans Bold 的真實 advance 表**（`icproj.text_width()`）：
粗估「每字 0.65 em」會低估 40%（`M` 是 1.005 em，`i` 只有 0.343 em）。

| 量 | 值（sizeScale 0.58） |
|---|---|
| 字高 cap height ＝ 0.70 × BASE | **12.3** |
| 下標往下伸出 ＝ 0.28 × BASE | **4.9** |
| `M_3` / `V_out` / `I_SS1` 寬 | 26.9 / 38.6 / 35.0 |

### 標籤放在元件上方／下方的 dy——**用 `icproj.dy_above()` / `dy_below()`**

```python
dy_above(ink_half, gap=1.5)   # 盒底離墨跡 gap；有下標要多扣 4.9
dy_below(ink_half, gap=1.5)   # 盒頂離墨跡 gap；盒頂 = baseline − 12.3
```

`gap` 的定案值：**電容 1.5**（使用者三輪校正）、**電阻 6**（使用者：「R 都離電阻再遠一點」）。
橫向的對應常數是 `LABEL_INK_GAP = 8`。不要再自己手算 dy。

### 差動輸出（兩個圈圈夾一個 V_out）的正規畫法

課本把差動輸出畫成**兩個對放的空心圈，中間印一個 `V_out`**。做法：

1. 兩個 `port`：左邊 `mirror:"x"`（圈在右）、右邊不鏡射（圈在左），同一列。
2. **各自宣告一個 cell terminal**（schema 硬性要求，見 §6），名稱取
   `V_out1`／`V_out2`——它們不會被畫出來，只是網表名。
3. **不要給這兩個埠下 instance-label**；中間那個 `V_out` 用 **drafting text
   ＋ `alignment:"middle"`**，錨在兩圈的正中央、`dy` +5。
4. 兩圈的圈心離中線 ≥（標籤半寬 + 8 + 圈半徑 2.48）。`V_out` 算出來是 ±34。

`alignment` 的合法值是 **`start` / `middle` / `end`**（schema enum，`middle` 可用）。

## 5. 驗證：一個指令（2026-08-30 起）

```bash
python scan_figure.py <截圖.png>   # ⓪ 有原圖才跑：抽拓樸與鏡射，見 §3C
python gen_xxx.py                  # ① 以下全部一次做完
```

`gen_xxx.py` 呼叫的 `f.build()` 依序做六道稽核 → 寫檔 → 用**網站自己的 zod schema**
驗證 → 用**編輯器自己的產生器**逐位元比對標籤 → 渲染 PNG。**六個計數全部要 0：**

| 訊息 | 意思 |
|---|---|
| `self-check errors` | 非正交、零長度、腳位不存在、terminal 沒接線、junction 只被碰 1 次、junction 壓在 terminal 上 |
| `legs` | 有一段超過 40 單位且不在 `long_haul` 白名單（明細會印在上面） |
| `labels` | 文字壓到走線，或標籤離鄰居太近讀者分不出屬於誰（§3A 規則 1、2） |
| `on-wire` | 兩件事：①元件坐在**別條 net** 的走線上＝畫出一個不存在的連接；②任何一條線**穿過元件本體**（進一邊、出另一邊）——**同一條 net 也算**。②是 2026-08-30 補的：串疊閘極回授線從一顆 CDM 二極體正中間穿過去，四道稽核全放行，因為兩者同屬 `net-vdd` 被當成「自己的接線」豁免了 |
| `tees` | 三條線在同一點相會卻沒有 junction ⇒ 不畫圓點（§3H 規則 4，電源軌除外） |
| `schema: VALID` | 對不上就是網站改版了 → 跑 `refresh_model.py`（§1） |

**標籤比對**：故意不照編輯器格式的（數值、方塊標題這類正體字）寫進
`f.build(expect_differ={"v-c1", ...})`，稽核就會變成
`labels: OK (N declared plain)`；**沒宣告的差異才會報**。
不要再人工判讀 `DIFFER` 清單。

最後**親眼看那張 PNG**（`preview_xxx.png`，就在 toolkit 夾），有原圖就並排比對。

> ⚠️ 跑 generator **不要 `| grep` 濾輸出**——例外會被吞掉，然後你會拿舊的 PNG 一直比對。

## 6. schema 會擋你的地方（都實際被擋過）

| 規則 | 正解 |
|---|---|
| `port`／`port-filled` 必須擁有**恰好一個 Cell terminal** | 在 `documents[].netlist.terminals` 宣告，標籤用 `binding.kind = "cell-terminal-name"` + `formatOverride` |
| `mosBulkBinding.origin` 只有兩個值 | NMOS → `"cell-default"`（netId = `mosBulkDefaults.nmosNetId`）；PMOS → `"supply-default"`（netId = 電源網） |
| bulk binding 必須「materialized」 | 該 net 的 `terminals` 要含 `{instanceId, pinName:"B"}` |
| 標註 `content` 與 `binding` **恰好擇一** | power-label／drafting text 用 `content`；instance-label 用 `binding` |
| 元件座標必須對齊 `presentation.grid` | 一律 10 的倍數；annotation／drafting 可用 1 |
| **junction 不可與 terminal 同座標**（否則只寫得出零長度 route，自檢會擋） | 匯流排列放在腳位列外側 10 單位，每顆器件拉一條 10 單位 riser（見 §3A） |
| 兩條**不同 net** 的線交叉 | 不必宣告、schema 不擋：不放 junction 就是交叉。課本的尾電流直立線穿過尾匯流排就是這樣 |

## 6B. 電流箭頭（I_C,M 那種）——**用 drafting，不要用 route-marker**

**擺法**：

- **方向 = 電流流動方向**。這條是硬規則。
- **放哪一段：跟著原圖擺**。垂直、水平都可以，沒有「一定要鉛直」這回事
  （Fig 9.34 是垂直，只因為課本畫在集極引線上）。沒有原圖時就挑
  「該電流真正流過、且長度夠的那一段」。
- 標籤放在箭頭**旁邊、與箭頭同高／同側**，緊貼但不壓線；
  放左邊用 `alignment:"end"`，放右邊用 `"start"`。
- 走線只有 20 單位也沒關係——箭頭幾乎填滿它，就是課本那個實心三角形壓在線上的樣子。

```jsonc
// 箭頭：Q_M 集極引線 (300,200)→(300,220)，電流由上往下流進集極
{ "kind": "arrow", "id": "arrow-icm", "locked": false, "zIndex": 0,
  "anchor": { "kind": "free", "position": { "x": 300, "y": 200 } },
  "from":   { "kind": "free", "position": { "x": 300, "y": 200 } },
  "to":     { "kind": "free", "position": { "x": 300, "y": 220 } },
  "styleOverride": { "arrowHead": "filled", "arrowHeadScale": 1.0 } }

// 標籤：靠左、與箭頭同高
{ "kind": "text", "alignment": "end",
  "anchor": { "kind": "free", "position": { "x": 287, "y": 224 } },
  "content": …RichText… }
```

**⚠️ 箭頭的三角形是「尖的」，長寬比 2.1:1。** 網站的實際尺寸（bundle
`dist-BrjFK9L9.js`）是 `arrowHeadLength 16.569767`、`arrowHeadWidth 7.906977`，
乘上 `arrowHeadScale`。預覽器原本自己畫 14 長 × 12 寬（幾乎正三角形），
出來是鈍的，使用者一眼看出「末端沒有尖尖的」。**預覽已改成照抄這兩個數字**——
自己編的形狀＝拿假圖跟原圖比對（§8 規則 3）。

**⚠️ 不要在 arrow 的 `styleOverride` 加 `strokeScale`。**
`annotationStrokeScale`（1.5）已經把標註筆畫拉到 `1.6 × 1.5 = 2.4`，**正好等於走線**；
再乘一次 1.5 會變 3.6，箭頭桿明顯比走線粗（使用者一眼看出來）。
`arrowHeadScale` 用 **1.0**，箭頭長度 **20 單位**即可——只要看得出是箭頭，不要壓過線。

**為什麼不用 `route-marker`**（實際做過、被使用者退兩次）：

- 漏掉 `markerKind:"current"`（enum 只有 `current` / `voltage`）→ **只有文字、沒有箭頭**。
- `orientation:"follow"` ＋ `direction:"reverse"` → 整個標籤轉 180°，**文字倒過來**。
- 補上之後 `normalOffset` 仍把文字壓在走線上；而 **route-marker 的實際落點離線渲染不出來**，
  只能靠使用者匯入回報，一輪一輪試。drafting 幾何是絕對座標，本機預覽就能驗。

route-marker 留給「真的需要跟著走線自動重排」的情況；靜態課本圖一律用 drafting。

## 7. 電源軌的正規畫法（Razavi 那條粗橫線）

**不要用 `vdd-port`**。照內建範例：

1. 一條 global 電源網 `net-power-vdd`。
2. 軌上放 junction：`jvdd-start`（左端外伸）→ 各分支點 → `jvdd-end`（右端外伸）。
3. 相鄰 junction 之間的 route 加 **`"presentation": "power-rail"`**（渲染成粗橫線）；
   往元件的下引線是普通 route，不加。
4. `connectivityEvidence` 兩筆 name-claim：
   `owner:{kind:"explicit-net-property"}` 與 `owner:{kind:"power-marker", objectId:"jvdd-end"}`，
   兩筆都 `scope:"global"`、`powerDomain:"vdd"`、`name:"VDD"`。
5. 標籤：`kind:"power-label"` + `netId` + `content`，anchor 掛在 `jvdd-end`。
6. **不要在電源軌上再放一個 `vdd-port`**（§2 已寫過，但實際會犯的地方在這裡）：
   有軌就只要「軌本身 ＋ 端點 junction 上的 power-label」，多放一個埠會在軌上
   翹出一截多餘的短線（2026-08-29 Fig 5.170 實犯）。
7. **兩端都要外伸**（超出最外側的分支點，各 20 單位）——這是課本的視覺特徵。
8. **⚠️ 接地軌（V_SS）要畫成跟 V_DD 一樣粗，`powerDomain` 必須寫 `"vdd"`，不能寫 `"ground"`。**
   網站渲染器的判斷式是（bundle `dist-CE3Pi34B.js`）：

   ```js
   presentation === "power-rail" && byBaseNetId.get(netId)?.powerDomain === "vdd"
   ```

   `ground` 不在條件內 ⇒ 畫成一般細線。`name` 照樣寫 `"VSS"`，所以標籤與網表不受影響。
   （2026-08-30：先寫 `"ground"`，使用者回報「VSS 沒有變粗」，才去 bundle 查到這條。
   **這就是「不要憑語意猜，去讀渲染器」的實例。**）

> 端點 junction 只會被一條 route 碰到，自檢要放行。

## 8. 常見錯誤清單（只留別處沒寫的）

1. **書的版本不一樣** → 圖號會撞。畫之前要使用者給截圖，或用 PyMuPDF 在 PDF 裡搜
   `Figure N.NN` 定位後裁圖親眼看。
2. **本機預覽會把每個 junction 都畫成圓點，正式渲染不會在電源軌端點畫點**——
   那是預覽的近似，不是產物的問題，不要去追。
3. **預覽渲染器要跟著真實樣式走**（字型、字重、下標正斜、power-rail 粗細、虛線框），
   否則比對是自欺。改了樣式就要同步改預覽。
4. **改 `icproj.py`／產生器的 patch 腳本一律先 Write 成 `.py` 再跑**，
   不要塞進 Bash heredoc——含反斜線或引號時 shell 會直接 parse error。
5. **不要用 node import 網站的 bundle chunk**：相依鏈會把 React 整包拉進來，
   在 node 裡執行到 `document is not defined` 就炸，整份 React 原始碼噴進對話。
   只有 `model.mjs`（＋`model-dep-0.mjs`）驗證過可以跑；其餘一律只用 `grep` 讀。

## 9. 產物位置與命名（使用者裁示，不要放別的地方）

- `.icproj.json` 一律寫進 repo 的 `out/`（產生器已經指好，不要改回絕對路徑）。
- 檔名要**一眼看得出是哪張圖**：`<來源>_<圖號>_<內容簡述>.icproj.json`
  - `Razavi_Fig_9_83_CG.icproj.json`
  - `Razavi_Fig_3_21_CS_supply-sens.icproj.json`
  - `GaN-ESD-paper_Fig4_clamp.icproj.json`
  - 沒有圖號就用主題：`5T-OTA.icproj.json`
- 要刪舊版或畫錯的檔，**先問使用者**。

## 10. 檔案位置

成品 `.icproj.json` 在 repo 的 `out/`；工具全在 `toolkit/`；`examples/` 是從網站匯出的 PNG。

> 首次 clone 先跑 `python toolkit/refresh_model.py` 與 `python toolkit/fetch_symbols.py`：`model.mjs` 與 `sym/*.json` 是產物，**不進版控**。

| 檔 | 用途 |
|---|---|
| `icproj.py` | **共用引擎**：schema 組裝、六道稽核、SVG 預覽、schema／標籤驗證、PNG 渲染 |
| `scan_figure.py` | ⓪ 截圖 → 拓樸／鏡射／scale／密度基準（§3C） |
| `fetch_symbols.py` | 同步符號庫（缺符號時先跑這支） |
| `refresh_model.py` | 網站改版時重抓 schema（會告訴你新的 schemaVersion） |
| `regress.py` | 改共用程式後必跑：23 張逐位元比對（`--accept` 換基準） |
| `publish_to_repo.py` | 發佈到私有 repo（`--dry-run` 只檢查） |
| `validate.mjs` / `check_labels.mjs` / `model.mjs` | 網站自己的 schema 與標籤產生器，`build()` 會自動呼叫 |
| `sym\*.json` | 符號腳位與外觀（**有檔案 ≠ 可以放，見 §2**） |

產生器 23 支，`ls gen_*.py`。挑範本：

| 要畫的東西 | 抄哪支 |
|---|---|
| 最乾淨的骨架（opamp＋電阻） | `gen_fig848.py`（141 行） |
| 被動元件／旋轉 90／數值標籤 | `gen_fig794.py` |
| 差動對／多尾電流／差動輸出埠 | `gen_fig1035.py` |
| BJT ＋ 電源軌 | `gen_fig5170.py` |
| 方塊圖 | `gen_cdr_blocks.py` |

`gen_fig934.py`／`gen_fig983_cg.py` 是舊式獨立骨架，**不要複製**，只拿來查座標寫法。
