# SOP — 用 Analog Canvas 畫課本級電路圖

> 建立 2026-08-28。基準成品：`Razavi_Fig_9_83_CG.icproj.json`（Razavi 習題 68 Fig. 9.83 共閘級）。
> 做法＝**離線產生 `.icproj.json` → 使用者在網站 File / Import Project File 匯入**。
> 網站正式站的 Agent／MCP 介面是關閉的（bundle 內 `jp({production:!0,configured:void 0})` → false），所以不要嘗試連線。

---

## 0. 一句話流程

1. `python scan_figure.py <截圖> [--ref=<px>:<單位>]`
   → 拓樸、鏡射、GAP、**以及密度基準**（§3C）。
   **先看它印的 `aspect` 與百分比再排版**，不要排完才回頭壓。
2. 抄 `gen_fig1035.py`，只改 placement / junctions / nets / routes / annotations **五段**
   （其餘全部 `from icproj import Schematic`，不要再複製骨架）
3. `python gen_xxx.py` → 一次跑完自檢＋走線 audit＋**標籤 audit**＋密度
4. `node validate.mjs` → `node check_labels.mjs`
5. 渲染 PNG 看**一次**（不是每輪）→ 交付

**目標：一張圖 5~10 分鐘。** 省時間與省 token 的四條硬規則：
- **不要把 `scan_figure.py` 的完整輸出讀進對話**：只看 MOS 表與帶 `GAP` 的那幾行。
- **不要每改一次就渲染 PNG**：壓線與標籤歧義由第 3 步的標籤 audit 自動抓，PNG 只是最後確認。
- **不要重讀本檔全文**：照本節走，需要哪節再翻哪節。
- **不要複製產生器骨架**：新圖只寫五段資料，約 140 行。

**絕不跳過第 5 節的驗證。** 每一道都抓到過我自己看不出來的錯。
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
| 專案檔 schema（v29） | `toolkit/model.mjs`（＝網站 bundle 的 `dist-BxeW5Key.js`，含 zod schema） |
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

本地 `sym/` 現有 **49** 個檔＝48 個資產 ＋ 從 bundle 抽出的 `vdd`。
**`ndmos`／`pdmos` 抽不出來**：整包部署程式與 repo 原始碼裡都只有字串引用
（預設變體表、排序表），沒有任何幾何定義——它們要靠 PDK 提供。真的需要時
再回頭查，不要以為是漏抓。

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
- **任兩個不相干墨跡的淨空 `CROWD_MIN = 8`**。低於就會被列出來。
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

0b. **有標名字的節點就要有黑圓點。** 圓點來自 junction，而 junction 要有
   **三個不同方向**的線才會被畫成節點。若兩條線走同一欄（例如電容下引線與
   回授匯流排上引線都在 x=740），編輯器只看到一個轉角、不畫點——
   把其中一條移到節點的另一側（Fig 14.36(b) 的 R_3 改走 x=690 才讓 Y 有點）。


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
| **器件本體 ÷ 圖高** | **量原圖，照抄它的比例**（見下） |
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

畫布符號的引線比課本長、本體比課本小，**單一比例尺無法同時對上兩軸**，要分軸：

```
K_V = 圖高(單位) / 書上圖高(px)      Fig.9.83：250 / 582 = 0.430
K_H = 圖寬(單位) / 書上圖寬(px)      Fig.9.83：320 / 598 = 0.535
```

實務作法：
1. 用 PIL 掃描原圖，抓**最長連續黑像素**的行／列 → 得到所有導線座標；再用 9×9 全黑區塊偵測 → 得到所有 junction 圓點。
2. 節點座標乘 K，四捨五入到 10。
3. **MOS 佔比自檢**：`通道 bar 25 單位 ÷ 圖高` 應該 ≈ 課本的 `bar px ÷ 圖高 px`（Razavi ≈ 11%）。低於 9% 就是太鬆，壓縮列距。

**已校準的最小間距（Fig.9.83 實測可用）**

| 情境 | 單位 |
|---|---|
| 源極 → 接地符號 | **10**（接地符號自帶 10 的引線，視覺共 20） |
| 電源軌 → 元件引線 | 20 |
| 節點 → 埠（Vin／Vout／Vb） | **20**（埠符號自己還會畫約 15 的引線） |
| 節點間有一個 junction | 20 + 20 |
| 節點間無 junction | 20~30 |
| 電源軌兩端外伸 | 20（一格，最小值） |
| MOS／I_REF 標籤離元件中心 | **±18** |
| 埠標籤離圈圈 | 15~16（圈圈邊緣在中心 ∓9.5） |

> **標籤為什麼是 ±18 而不是 ±26**：viewBox 是 48×48，但 `textbook-3terminal`
> 隱藏了 bulk lead，**實際畫出來的 MOS 只佔 x = −20 ~ +10.6**。
> 用 viewBox 半寬 24 去推會多留 8 單位空隙，看起來標籤離元件太遠。
> 一律用「實際 primitive 的極值」算間距，不要用 viewBox。

## 3C. 從截圖抽拓樸：**一個指令，不要用眼睛判讀**

```bash
python toolkit/scan_figure.py "path/to/screenshot.png"
```

這支取代舊 §8-2 的「放大 5–6 倍逐顆看」。它印的每一項都是量出來的，
不會像目視那樣看錯。**畫圖前先跑它，再開始排座標。**

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

## 5. 三道驗證（每次交付前全跑）

```bash
python scan_figure.py <截圖.png>   # ⓪ 有原圖才跑：抽拓樸與鏡射，見 §3C
python gen_xxx.py            # ① 自檢＋走線 audit＋標籤 audit＋密度，全在 icproj.py 裡
node validate.mjs <proj>     # ② 用網站自己的 zod schema 驗（不是我自寫的）
node check_labels.mjs <proj> # ③ 標籤與編輯器產生器逐位元比對
```

第 ① 步（`icproj.Schematic.build`）現在會自動報這五類問題，**全部要是 0 才往下走**：

| 訊息 | 意思 |
|---|---|
| `self-check errors` | 非正交、零長度、腳位不存在、terminal 沒接線、junction 只被碰 1 次、**junction 壓在 terminal 上** |
| `<-- LONG` | 該段超過 40 單位且不在 `long_haul` 白名單 |
| `! LABEL OVERLAPS WIRE` | 文字框壓到走線（§3A 規則 1） |
| `! LABEL AMBIGUOUS` | 標籤離鄰居太近，讀者分不出屬於誰（§3A 規則 2） |
| `components sitting on another net's wire` | 元件坐在別條 net 的走線上＝畫出一個不存在的連接。**必須是 0**（2026-08-29 新增，見 §3E） |
| `MOS bar 25 / height` | 低於 9% ＝ 排太鬆，壓列距 |

再加第四道：**自畫 SVG → headless Chrome 轉 PNG → 親眼看**，並與原圖並排比對。

```powershell
Start-Process -FilePath 'C:\Program Files\Google\Chrome\Application\chrome.exe' `
  -ArgumentList '--headless=new',"--screenshot=<絕對路徑>.png",'--window-size=W,H',
  '--default-background-color=FFFFFFFF',"file:///<絕對路徑>.svg" -Wait -NoNewWindow
```

> ⚠️ `--screenshot` 一定要給**絕對路徑**，相對路徑會 `存取被拒`。
> ⚠️ 跑 generator 時**不要 `| grep` 濾掉 stderr** —— 曾因此讓預覽腳本的例外被吞掉，比對了兩輪舊圖。

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

> 端點 junction 只會被一條 route 碰到，自檢要放行。

## 8. 常見錯誤清單

1. **書的版本不一樣** → 圖號會撞。畫之前要使用者給截圖，或用 PyMuPDF 在 PDF 裡搜 `Figure N.NN` 定位後裁圖親眼看。
2. **鏡射判讀** → **跑 §3C 的 `scan_figure.py` 讀 mirror 欄**，不要用眼睛看。（規則本身：閘極板在左＝`mirror:"none"`，在右＝`"x"`。）
3. **走線畫太長** → 用第 3 節的 audit 表逐條比，任何一條 > 1.25 倍就縮。
4. **自寫檢查器全綠不代表對** → 一定要跑第 5 節的 ② ③。
5. **預覽渲染器要跟著真實樣式走**（字型、字重、下標正斜、power-rail 粗細），否則比對是自欺。
6. **間距一律用實際 primitive 的極值算，不要用 viewBox**（見第 3 節的 ±18 說明）。
7. **元件與走線的線寬要一致** → 三個 strokeScale 設同值（見第 4 節）。
8. **本機預覽會把每個 junction 都畫成圓點，但正式渲染不會在電源軌端點畫點**——
   看到這個差異不要去追，那是預覽的近似，不是產物的問題。
9. **改 `icproj.py`／產生器的 patch 腳本一律先 Write 成 `.py` 再跑**，
   不要塞進 Bash heredoc——含反斜線或引號時 shell 會直接 parse error
   （environment.md 已有這條通則，這裡再犯過一次）。
10. **跑 generator 不要用 `| grep` 濾輸出**：預覽段的例外會被吞掉，然後你會拿舊的
   PNG 一直比對。這個坑在本次已經連踩三次。

## 9. 產物位置與命名（使用者裁示，不要放別的地方）

- `.icproj.json` 一律寫進 repo 的 `out/`（產生器已經指好，不要改回絕對路徑）。
- 檔名要**一眼看得出是哪張圖**：`<來源>_<圖號>_<內容簡述>.icproj.json`
  - `Razavi_Fig_9_83_CG.icproj.json`
  - `Razavi_Fig_3_21_CS_supply-sens.icproj.json`
  - `GaN-ESD-paper_Fig4_clamp.icproj.json`
  - 沒有圖號就用主題：`5T-OTA.icproj.json`
- 要刪舊版或畫錯的檔，**先問使用者**。

## 10. 檔案位置

```
analog-canvas-toolkit/
├─ SOP.md                       ← 本檔
├─ examples/*.png               ← 已完成的圖，交付前拿來對比密度
├─ out/*.icproj.json            ← 成品專案檔，匯入網站用
└─ toolkit/
   ├─ fetch_symbols.py          ← 同步符號庫（缺符號時先跑這支）
   ├─ refresh_model.py          ← 重抓網站 schema（首次 clone 必跑）
   ├─ scan_figure.py            ← ⓪ 截圖 → 拓樸／鏡射／scale（見 §3C）
   ├─ icproj.py                 ← **共用引擎**：schema 組裝、四道自動稽核、SVG 預覽
   ├─ gen_fig848.py             ← 最乾淨的範本（opamp＋電阻，141 行）
   ├─ gen_fig1035.py            ← 範本：差動＋雙尾電流＋差動輸出埠
   ├─ gen_fig794.py             ← 範本：被動元件（R／C）＋旋轉 90＋數值標籤
   ├─ gen_fig5170.py            ← 範本：BJT＋電源軌
   ├─ gen_fig934.py             ← BJT 版參考（舊式獨立骨架，不要複製）
   ├─ gen_fig983_cg.py          ← MOS 版參考（舊式獨立骨架，不要複製）
   ├─ validate.mjs              ← 用網站 schema 驗證
   ├─ check_labels.mjs          ← 標籤逐位元比對
   ├─ model.mjs                 ← 網站的 model/schema（**不進版控**，refresh_model.py 產生）
   └─ sym/*.json                ← 符號腳位與外觀（**不進版控**，fetch_symbols.py 產生）
```

**畫新圖的最短路徑（目標 5~10 分鐘）**

1. `python scan_figure.py <截圖>` → 拿到 mirror、GAP、圓點清單（§3C）
2. 複製最接近的範本（兩支都用 `icproj.py`）：
   **有電阻／電容／旋轉／數值標籤 → `gen_fig794.py`**；
   **差動對／多尾電流 → `gen_fig1035.py`**。
   `gen_fig983_cg.py`／`gen_fig934.py` 是舊式獨立骨架，只拿來查 BJT／單端的
   座標寫法，**不要複製**。
   動手前先 `ls sym/`：**缺的符號跑 `python fetch_symbols.py`**，不要自己畫、
   也不要一個一個手動找（2026-08-29 手找 `resistor` 花掉好幾分鐘）。
3. 只改 placement / junctions / nets / routes / annotations 五段；列座標直接抄 §3A 的標準列堆疊
4. `python gen_xxx.py` → 五類問題全部 0（見 §5 的表）
5. `node validate.mjs` → `node check_labels.mjs` → 渲染 PNG 看一次
