# SOP — 新畫法：我擺位置，編輯器走線（acplan）

> 2026-11-11 建立。**沒有參照圖、要自己決定怎麼擺**的電路圖用這份；**有參照圖要照著畫**的用舊的產生器路線（repo 根目錄的 `SOP.md`）（他 2026-11-12 裁示，見 §10）。
> 讀者是之後接手的模型（Opus）。照做就能維持他 2026-11-11 核可的品質；**不要自己發明新畫法，先找最像的範例照抄再改。**

## 0. 流程（六步）

1. 準備 deck（`.cir`，只放拓樸，格式見 §2）。
2. 在 `acplan/plans_py/` 找**最像的範例**（§6 的對照表），複製成 `<名稱>.py`。
3. 改位置：每顆元件在哪一欄、哪一列、閘極朝哪邊；埠放哪；每條多腳 net 的幹線走哪。
4. 跑 `python plans_py/<名稱>.py`，直到印出 `CHECK: PASS`。
5. **用 Read 工具打開 `out\<名稱>.png` 親眼看**，對 §8 的清單逐項檢查；過了才交付 `out\<名稱>.icproj.json`（他在網站按 Import 選檔開啟，拖進去沒用）。

6. 交付：`out/<名稱>.icproj.json` 就是成品，檔名改成一眼看得出是哪張圖；回報時附 PNG。

`CHECK: PASS` 只代表「沒有錯、接線等價、慣例的數值沒超標」，**不代表好看**。第 5 步不能省。

## 1. 怎麼跑

- 工作目錄：`acplan/`（用 Bash 工具，先 `cd` 到絕對路徑；`export PYTHONIOENCODING=utf-8`）。
- 單張：`python plans_py/<名稱>.py`
- 多張＋拼圖：`python runbatch.py <名稱> <名稱> ...` → 一次看 `out\_batch.png`
- 檢查器自測：`python test_check.py`（要印 `SELFTEST PASS`；改過 `acplan.py` 一定要跑）
- 跑圖時還會自動寫 `plans\<名稱>.json`（位置表）與 `ws\<名稱>\`（工作區），不用管。
- 產物都在 `out\`：`<名稱>.png`（看圖）、`.svg`、`.icproj.json`（交付）、`.exported.sp`（編輯器匯出的 netlist）。
- 輸出裡 `GENERATED_NET_NAME`、`GENERIC_*_MODEL` 這類 info 診斷可以不理；`.exported.sp` 裡運放的電源腳接到 0 也正常（運放符號的電源腳沒畫出來）。
- 輸出裡的 `upstream verify: topology different` 可以不理（上游的比對把電源腳算進去）；**以 `NETLIST EQUIVALENT (own check): True` 與 `CHECK: PASS` 為準**。
- 全程在本機跑（Node 執行上游的 headless 編輯器），**不登入、不連正式站**。

## 2. deck 格式

```
.title Two-stage Miller op amp
.global VDD
.subckt MILLER inp inn vb out
.name inp V_inp          ← 埠顯示的名字（底線後面是下標）
.name vb V_b
M1 d1 inp tail 0 nmos    ← M：D G S B 型號（nmos／pmos）
Q1 c b e npn             ← Q：C B E 型號（npn／pnp）
XOA p n out opamp        ← 運放：最後三個 net 依序是 IN+、IN-、OUT
CC x out                 ← 兩端元件：R／C／L／I／V／D，第一個 net 是第 1 支腳
.name CC C_c             ← 元件顯示的名字
.ends
```

- **每個埠都要有 `.name`**（沒有的話會顯示成小寫的 net 名，例：`v_b`）；deck 沒寫又不能改 deck 時，在 `p.port(...)`／`p.port_pin(...)` 加 `name="V_b"`。
- 函式裡的元件代號用 **deck 每行第一欄的字**（例：deck 寫 `MM2 …` 就是 `"MM2"`），不是 `.name` 的顯示名。
- `.show <net>`（標內部節點名）目前**不生效**，內部節點不標名字；他要標再問他要放哪。
- MOS 的第 4 個 net（body）圖上不畫、也不影響等價比對：NMOS 寫 `0`、PMOS 寫 `VDD` 即可。`.iodir`、`.alias` 可省略（`.alias` 等同 `.name`）。
- **自己寫 deck 時先推一次極性再命名**：兩級運放的 x 取在 M2 汲極時，M2 的閘極是同相輸入（V_inp）。沒有明確輸入輸出的偏壓電路，把要給別人用的偏壓節點開成埠（例：V_BN、V_BP）。
- 接地寫 `0`；正電源寫 `VDD` 或 `VCC`；負電源 `VEE`／`VSS`。
- 只放拓樸，不放尺寸、不放模擬指令。
- 新 deck 放 `toolkit/decks/new/`。

## 3. 座標與腳位

- 格點 10 的倍數，**y 向下**。
- **導通欄 col**＝電晶體 D／S（BJT 的 C／E）那條直線的 x。`p.mos(ref, col, y, "L")` 的 col 就是它，不用自己算偏移。
- 閘極／基極：朝 L 時在 (col−30, y)，朝 R 時在 (col+30, y)。要讓 A 的射極接 B 的基極成一條直線：B 的 y ＝ A 的 y＋20。
- 電晶體中心在 y，上端腳在 y−20、下端腳在 y+20、閘極在 y。所以**上下兩顆接在一起時，接點在兩個 y 的正中間**。
- 兩端元件直放：腳在 (x, y−20) 與 (x, y+20)（電感是 ±30）。
- 二極體：預設橫放，A 在 (x−20, y)、K 在 (x+20, y)。直放用 `p.two("D1", x, y, first="U")`（陽極朝上）或 `first="D"`。
- 橫放的 MOS（開關、傳輸閘；PMOS 的 D／S 相反）：

| 寫法 | 閘極 | D | S |
|---|---|---|---|
| `p.place(ref, x, y, 90)` | 閘極在上 (x+0, y-20) | D 在右 (x+20, y+10) | S 在左 (x-20, y+10) |
| `p.place(ref, x, y, 90, "horizontal")` | 閘極在上 (x+0, y-20) | D 在左 (x-20, y+10) | S 在右 (x+20, y+10) |
| `p.place(ref, x, y, 270)` | 閘極在下 (x+0, y+20) | D 在左 (x-20, y-10) | S 在右 (x+20, y-10) |
| `p.place(ref, x, y, 270, "horizontal")` | 閘極在下 (x+0, y+20) | D 在右 (x+20, y-10) | S 在左 (x-20, y-10) |

  不確定就 `print(p.pin(ref, "G"))` 印出來確認。
- D＝G（或 C＝B）的二極體接法不用自己拉線，編輯器會畫出短接。
- 運放 IN+ 接地：`p.ground(ref, "IN+", x−60, y+40)`。
- 運放 `p.opamp(ref, x, y)`：輸入在 (x−40, y−10) 與 (x−40, y+10)，輸出在 (x+30, y)；預設 IN− 在上、IN+ 在下，`plus="top"` 對調。
- 反相器：A 在 (x−30, y)、Y 在 (x+20, y)。
- 完整腳位表：`pins_table.json`。要知道某支腳的實際座標：`p.pin("M1", "G")`。

## 4. Plan 的函式

| 要做的事 | 寫法 |
|---|---|
| 開一張 | `p = Plan("名稱", "../toolkit/decks/new/名稱.cir")`；電源叫 VCC 時加 `vdd_name="VCC"` |
| 一顆 MOS／BJT | `p.mos(ref, col, y, "L"或"R")`／`p.bjt(...)`；不確定哪一種用 `p.tr(...)` |
| 同欄一疊 | `p.stack(col, "L", [("MP1", 110), ("MN1", 210)])` |
| 左右一對 | `p.pair("M1", "M2", cols=(180, 290), y=210, gates="out")`；`"out"`＝閘極朝外（差動輸入對），`"in"`＝閘極相對（電流鏡、疊接對） |
| 兩端元件 | `p.two(ref, x, y)` 直放；`horizontal=True` 橫放；`first="U/D/L/R"` 指定第 1 支腳朝哪 |
| 運放 | `p.opamp(ref, x, y, plus="bottom")`（舊範例寫 `p.place(ref, x, y)`，等價） |
| 橫放的電晶體 | `p.place(ref, x, y, 90)`（例：傳輸閘） |
| 埠（線接上的那一點） | `p.port(net, x, y, "L/R/U/D", name=None)`；`name="V_b"` 可指定顯示名 |
| 埠貼在某支腳外側 | `p.port_pin(net, ref, pin, lead=30)` |
| 埠掛在一條線上 | `p.port_tap(net, x, y, "U", lead=30)`（例：V_b 掛在閘極線中點上方） |
| 只掛同名標籤、不拉線 | `p.label(net, ref, pin)`（邏輯閘的 A／B／C、latch 的 Q／Qb）。可以跟同一條 net 的 `port_pin` 混用：一處拉埠、其他腳掛標籤（例：CLK）；顯示名沿用 deck 的 `.name`。橫放 MOS 的閘極朝上／下時要自己寫 `side="U"`／`"D"` |
| （注意）每條 net 只能有一條幹線 | 同一條 net 第二次呼叫 `hline`／`vline` 會蓋掉前一次、不報錯；其餘的腳用 `p.wire` 接 |
| 橫幹線／直幹線 | `p.hline(net, y)`／`p.vline(net, x)`；不給端點＝自動剛好涵蓋所有**元件腳**（不含埠）。元件腳都在同一欄 → 用 `vline`；都在同一列 → 用 `hline`；埠從側面接上 |
| 指定路徑的線 | `p.wire(ref, pin, [轉折點…], 終點)`；終點是另一支腳 `("REF","PIN")`，或同一條 net 上已經有線的一點 `(x, y)`（幹線，或前面寫過的另一條 `wire`）。終點設在幹線的**端點**，最後一段不要跟幹線重疊。用 `wire` 接的腳不算進幹線的自動範圍；多條 `wire` 可以串接（範例 `ring-osc-3`、`d-latch-tg`） |
| 偏壓線貫穿閘極 | `p.gate_through("M5", "M7")`；被貫穿那顆的標籤會放到下面。尾電流源在上（PMOS 輸入）時下面是尾節點橫線，把輸入對下移 10～20 留位置（範例 `two-stage-pmos-in-rz`） |
| 接地符號換位置 | `p.ground(ref, pin, x, y)` |
| 電源軌 | `p.rail(y)`；負電源軌 `p.rail_low("VEE", y)` |
| 走線順序 | `p.route_order("tail", "d1", …)`（沒列的排後面） |
| 出圖＋檢查 | `p.draw()`（檔案最後一行） |

## 5. 慣例（他 2026-11-11 的裁示；數值在 `acplan.py` 開頭，要改先問他）

1. **要密**。成對兩欄的間距 100～120；上下相鄰兩顆列距 70～140：中間節點有別的線接出去（輸出、幹線）用 100，中間只是一條直連線（疊接的中間節點）用 80；整張「外框面積 ÷ 元件數」不超過 22000。
2. **空的走線不要長**。埠的引線預設 30、最長 50；V_b 這類偏壓埠用 30。不要為了對齊接地或把輸出拉到最右邊而把線拉長。
3. **差動對**：同一列、閘極朝外；尾電流源置中在兩顆正下方。
3a. **交叉耦合對**（各自的閘極接對方的汲極：LC 振盪器、latch 的再生對）：同一列、**閘極朝內**，中間畫成 X。做法：兩條輸出橫線上下錯開 20，上面那條往內伸到對面那顆的閘極 x，下面那條同理（範例 `lc-oscillator-xcoupled`、`strongarm-latch`）。這種電路的兩個輸出埠會差 20 高，是允許的（他 2026-11-11 看圖後同意）。
4. **電流鏡／疊接對（共用閘極）**：同一列、閘極相對，中間一條閘極線；V_b 埠用 `port_tap` 掛在閘極線中點。
5. **唯一允許線穿過元件的情形**：偏壓線從尾電流源的閘極橫向貫穿它，接到同一列另一顆的閘極（`gate_through`）。被貫穿的那顆，標籤放下面（函式會自動做）。
6. **埠跟它那條 net 的橫線同高**，接成一個十字點，不要差一點點變成兩個點。左右對稱的兩個輸出埠要等高（交叉耦合的例外見 3a），而且**成對的埠一律朝外**（左邊的朝左、右邊的朝右），名字才會對稱。
7. **折疊疊接**：輸入對放在疊接 PMOS 那一列的高度，不要放最下面。
7a. **運放串接**：運放的 IN− 比 OUT 高 10，所以下一級運放要往下 10，讓它的 IN− 跟上一級的 OUT 同高（範例 `tow-thomas-biquad`）。整體回授的長線走最上方，這種線不算「空線過長」。
7b. **二極體接法的方形畫大一點**（他 2026-11-12 看圖後要求）：編輯器自動畫的短接只有 30×20，偏小。自己畫成 30×30：汲極那條直線設成幹線（`vline` 要寫明範圍，不然會被拉到閘極高度而穿過元件），閘極用 `p.wire` 往外 30 再接回幹線；另一顆的閘極用 `p.wire` 接到這顆的閘極。埠接在方形的接點上，同一條線只留一個點（範例 `constant-gm-bias`、`widlar-current-source`）。
7c. **沒掛東西的線不要拉長**（同日）：電源軌到第一顆、電阻到電晶體之間的空線留 20～30 就好，列距用 90～100；小電路寧可密一點。
7d. **傳輸閘兩顆並聯**（同日）：左右兩條線從兩顆 MOS 的**中間高度**接進來，接點落在兩顆中間，不要掛在其中一顆的腳上（範例 `d-latch-tg` 下面那組）。
8. **多級**：第二級的元件對齊第一級的列（PMOS 對 PMOS 列、NMOS 對 NMOS 列）；級間連線短。
9. **電源**：最上面一條 VDD 軌；接地用各自腳下的接地符號，不拉一條地線。BJT 電路有 VEE 時最下面放 VEE 軌。
10. **輸出在右、輸入在左**；回授繞線走外圍（上方或下方），不穿過元件。運放回授走哪邊：看哪邊是空的——下方有接地的電容／電阻就讓 IN− 在上、回授走上方；反之用 `plus="top"`、回授走下方。
11. 邏輯閘：PMOS 並聯排一列、NMOS 串聯疊一欄（或反過來），每顆閘極各掛 A／B／C 標籤，不拉線。
12. 交叉耦合太亂時用同名標籤代替拉線（例：SR latch 的 Q／Qb、比較器的 Vsp／Vsn）。

## 6. 範例對照表（先找最像的照抄）

| 要畫的 | 抄這份（`plans_py\`） |
|---|---|
| 差動對＋鏡負載、兩級 | `5T-OTA`、`two-stage-miller`（含 gate_through、Miller 電容）、`two-stage-pmos-in-rz`（PMOS 輸入、R_z＋C_c） |
| 疊接、telescopic、folded cascode | `telescopic-cascode`、`midterm-folded-cascode`、`folded-cascode-pmos-in`、`cs-cascode-pmos-load`、`cs-degen-cascode` |
| 電流鏡各種 | `cascode-current-mirror`、`cascode-mirror-wide-swing`、`wilson-mirror-bjt`、`beta-helper-mirror`、`regulated-cascode` |
| BJT 差動對、VEE 軌、Gilbert | `bjt-diffpair-vee`、`bjt-diffpair-mirror-load`、`gilbert-cell` |
| 單級（CS／CE／CG／隨耦器） | `darlington-follower`、`source-follower-bootstrap`、`class-ab-diode-bias`、`cs-active-load`、`ce-bypassed`、`cg-stage-current-load`、`source-follower-isrc`、`emitter-follower-vee`、`push-pull-output` |
| 運放＋被動元件 | `summing-amp`、`sample-hold`、`opamp-inverting`、`opamp-noninverting`、`opamp-integrator`、`difference-amp`、`sallen-key-lp`、`wien-bridge-osc`、`schmitt-trigger`、`precision-rectifier` |
| 邏輯閘、反相器、latch | `cmos-inverter`、`cmos-inverter-chain`、`nand3-cmos`、`nor3-cmos`、`aoi21-cmos`、`sr-latch-nor`、`transmission-gate`、`ring-osc-3` |
| 比較器（兩級、交叉耦合、反相器方塊） | `hw2-double-tail-comparator`、`strongarm-latch` |
| 交叉耦合對、LC 振盪器 | `lc-oscillator-xcoupled` |
| 多級運放迴路（biquad） | `tow-thomas-biquad` |
| 傳輸閘 latch | `d-latch-tg` |
| 偏壓電路 | `constant-gm-bias`、`widlar-current-source` |
| 小訊號等效電路（§6b） | `ss-cs`、`ss-cs-degen`、`ss-ce-hybrid-pi`、`sstest-cg`（共閘） |
| 訊號方塊圖（§6a） | `feedback-loop`、`pll-linear-model`、`delta-sigma-1st`、`loop-with-disturbance`（干擾從上面進）、`receiver-chain`（三角形、乘法點、ADC） |
| 多顆運放串接 | `instrumentation-amp`（上下兩顆的 IN− 都朝向中間的電阻串；運放輸入腳的分支可以貼著三角形往上／下拉，不會被判碰到本體） |
| 其他 | `bandgap-core`、`ldo-regulator`、`charge-pump`、`colpitts-osc`、`esd-2stage-clamp`、`half-wave-rectifier` |

## 6a. 訊號方塊圖（2026-11-12 加入）

回授系統、PLL 線性模型、ΔΣ 調變器、收發機訊號鏈這類「方框＋加法點＋箭頭」的圖，也用這份 SOP，流程六步不變。差別只有下面幾點。

**deck**（放 `toolkit/decks/flow/`，元件代號一律 `X` 開頭）：

```
.subckt FeedbackLoop x y
.iodir x=input y=output
.name x X
.name y Y
XS1 x fb e adder         ← 加法點：A（左）、B（下或上）、Y（輸出）
.sign XS1 + -            ← A、B 兩個輸入的正負號（不寫＝都是加，圖上不標）
XH1 e y block            ← 方框：輸入、輸出
.formula XH1 A(s)        ← 方框裡的字；可寫 K_VCO/s（自動排成分式）、z^-1/(1-z^-1)、1/N、β
.ends
```

| deck 類型 | 畫出來 | net 順序 |
|---|---|---|
| `adder`／`multiplier` | 圓圈裡 ＋／× | A B Y |
| `block` | 方框（字用 `.formula`） | 入 出 |
| `delay` | z^-1 方框 | 入 出 |
| `quantizer` | 階梯方框 | 入 出 |
| `adc`／`dac` | 五邊形 | 入 出 |
| `amp` | 三角形（要名字就 `.name XLNA LNA`） | 入 出 |
| `gm` | 梯形 g_m | 入 出 |
| `comparator` | 比較器三角形 | IN+ IN− OUT |

**擺位置**：

| 要做的事 | 寫法 |
|---|---|
| 方框類 | `p.block(ref, x, y)`：輸入在左 `x−30`、輸出在右 `x+30` |
| 腳位名（`p.wire` 要用） | `block`／`delay`／`quantizer`／`gm`：輸入 `"A"`、輸出 `"Y"`。`adc`／`dac`／`amp`：輸入 `"IN"`、輸出 `"OUT"`。`comparator`：`"IN+"`、`"IN-"`、`"OUT"`。加法點／乘法點：`"A"`、`"B"`、`"Y"` |
| 左右不對稱的符號 | `adc`：IN `x−50`、OUT `x+40`。`dac`：IN `x−40`、OUT `x+50`。`amp`：IN `x−40`、OUT `x+30`。`comparator`：IN+ `(x−40, y+10)`、IN− `(x−40, y−10)`、OUT `x+30`。`flip=True` 時左右對調（例：翻轉的 `dac` IN 在 `x+40`、OUT 在 `x−50`） |
| 回授路徑上的方框（訊號由右往左） | `p.block(ref, x, y, flip=True)` |
| 加法點／乘法點 | `p.adder(ref, x, y)`：A `(x−20, y)`、Y `(x+20, y)`、B `(x, y+20)`；B 要從上面進寫 `b="U"` |
| 字太長把方框撐寬 | 程式會報「把 p.block(..., w=) 設成 N」，照它給的數字填；接點在 `x∓(w/2+10)` |

**慣例**（檢查器會抓前兩條）：

1. 主路徑排成一列、由左往右；回授路徑在下面一列（列距 90～100）、由右往左，方框 `flip=True`。
2. 來源的輸出腳跟下一個方框的輸入腳同高，線才是直的。
3. 輸出線用 `p.hline` 設成幹線；回授從幹線上分出去：`p.wire(回授方框, 輸入腳, [(x分支, y回授)], (x分支, y主路徑))`，回到加法點：`p.wire(回授方框, 輸出腳, [(x加法點, y回授)], (加法點, "B"))`。
4. 干擾、雜訊、LO 這類從旁邊注入的訊號，用埠接在加法點／乘法點的 B 腳正上方或正下方（`p.port(net, x, y∓70, "U"／"D")`，引線長 50）。
5. 左右兩端的埠（輸入、輸出）引線留 60～80（線上要放得下箭頭）。
6. 回授要接到兩個以上的加法點（例：二階 ΔΣ）：第一條回授線照第 3 條畫到最遠的加法點；其餘加法點的 B 腳直接往下接到這條回授線上：`p.wire("XS2", "B", [], (x加法點, y回授))`。終點落在同一條 net 的另一條 `p.wire` 上是允許的，不必另外補幹線。
7. 前饋路徑（訊號從輸入分出去、繞過主路徑）：方框放主路徑上面一列（列距 90）、不翻轉；第二個加法點寫 `b="U"`。輸入線先設成幹線 `p.hline(輸入net, y主, x埠, x加法點A腳)`，再 `p.wire(前饋方框, "A", [(x分支, y上)], (x分支, y主))`、`p.wire(前饋方框, "Y", [(x加法點2, y上)], (加法點2, "B"))`。

**箭頭是自動的**：每個方塊輸入腳、每個輸出埠各一個箭頭，不用自己畫。log 的 `arrows` 那行若 FAIL，代表有輸入腳的線不是停在腳上（通常是讓編輯器自動走的多腳 net）；把那支輸入腳改用 `p.wire` 接。

**驗收**：方塊符號沒有 netlist 定義，所以不匯出 netlist；`NETLIST EQUIVALENT` 改成比對專案檔裡的接線跟 deck 是否一致。`CHECK: PASS`＋看圖的要求不變，另外多看一項：每個箭頭方向對、正負號標在對的輸入。

**畫不了的**：方框上下還要接線的（三個以上輸入的方塊、控制訊號從上面進方框）、一般流程圖（判斷菱形、步驟框）。遇到就說明畫不了，不要硬湊。

## 6b. 小訊號等效電路（2026-11-13 加入）

受控源＋電阻＋「+ v_gs −」這類圖也用這份 SOP，流程六步不變。差別只有下面幾點。先抄範例：`ss-cs`（共源）、`ss-cs-degen`（源極退化）、`ss-ce-hybrid-pi`（BJT hybrid-π）、`sstest-cg`（共閘：閘極接地、輸入在源極）。

**deck**（放 `toolkit/decks/new/`）：

```
G1 d s g s               ← 壓控電流源：電流從第 1 條 net 流向第 2 條；後兩條是控制端，只當說明用、不接線
.label G1 g_m v_gs       ← 受控源旁邊的字：空白分段，每段「字_下標」（g_m v_π、A_v v_1、β i_b）
RO d s
.name RO r_o             ← 電阻的名字照舊用 .name
```

代號開頭決定種類：`G` 壓控電流源、`E` 壓控電壓源、`F` 流控電流源、`H` 流控電壓源。閘極（開路）那條 net 只出現在 `.subckt` 的埠和受控源的控制端，不會接到任何元件，這是正常的。

**擺位置**：

| 要做的事 | 寫法 |
|---|---|
| 受控源 | `p.source(ref, x, y)`：直放，腳在 `(x, y∓20)`，箭頭由上往下（第 1 條 net 在上）；要朝上寫 `first="D"`。預設菱形，要圓形寫 `shape="circle"` |
| 開路的輸入端子（閘極） | `p.open_port(net, x, y, x_end)`：端子在 `(x, y)`，引線水平拉到 `x_end` 停住 |
| 標控制電壓 | `p.vmark("v_gs", x, y_plus, y_minus)`：`x` 用線頭的 x；`y_plus`＝上面那條線 +15、`y_minus`＝下面那條線 −15。**＋、− 相距至少 50**（不到 50 會壓到中間的字，檢查器會擋）。＋ 要在下面就把兩個 y 對調（`y_plus` > `y_minus`） |
| 三顆以上接地 | `p.ground_bus(y, x0, x1, at=x)`：一條共用地線、只畫一個接地符號；`at` 要是 10 的倍數、不要跟任何接地腳同 x。**它會把圖上所有接地腳都接上去**，不能只接其中幾支；接地腳不在同一列（例：R_S 在下面、R_D 在上面）就不要用，讓每支腳各畫一個接地符號 |

**慣例**（他 2026-11-13 看圖後的裁示，檢查器會抓前三條）：

1. 開路的輸入端子跟輸出那條線（汲極／集極）**同高**，引線長 50～60。
2. 控制電壓「+ v_gs −」標在線頭正下方；下面那條線（源極線或共用地線）往左拉到線頭正下方，當「−」的參考。
3. 輸出線設成幹線，比元件上端腳高 20（`p.hline("d", 80, …)`，元件中心 y=120）；下面那條線比下端腳低 20（y=160）。腳剛好落在幹線中段會走線失敗。
4. 並聯的元件欄距 70（受控源右邊要放得下 g_m v_gs）；整張圖不要超過需要的寬度。
5. 控制端有一端是地（共閘：閘極接地、輸入在源極）：deck 的控制端寫 `0 s`，不用 `open_port`；輸入用一般的 `p.port` 接在源極線上，v_gs 標在源極到地的那顆元件（R_S）左邊 30，＋ 在地那一側、− 在源極那一側（範例 `sstest-cg`）。
6. 輸入端不是開路的（BJT 的 r_π 接在基極）：用一般的 `p.port`＋`p.hline`，基極線跟集極線同高；v_π 標在 r_π 左邊 25。

**驗收**：受控源的控制端不接線，所以不匯出 netlist；`NETLIST EQUIVALENT` 改成比對專案檔裡的接線跟 deck 是否一致（含每支接地腳有沒有接到接地符號）。`CHECK: PASS`＋看圖的要求不變，另外多看：受控源箭頭方向、＋／− 沒有壓到線或字。

**畫不了的**：電容（C_gs、C_gd）橫跨在兩個節點之間要畫成橫放的可以畫（`p.two(..., horizontal=True)`），但流控源的「控制電流 i_b」箭頭標不了。遇到就說明。

## 7. 走線怎麼運作、被拒絕怎麼修

編輯器**不是自動繞線器**：每條 net 它畫「一條直的幹線＋每支腳垂直接上幹線」。所以位置要擺到「每支腳都能直直接上幹線、途中不碰到別的東西」。

- 兩支腳的 net：對齊（同 x 或同 y）就自動一條直線，不用寫任何東西。
- 三支腳以上：寫 `hline`／`vline` 指定幹線。
- 繞得比較遠的（回授）：用 `p.wire(...)` 指定整條路徑，終點落在同一條 net 的幹線上。

| 訊息 | 原因 | 修法 |
|---|---|---|
| `the branch from … touches X's drawing` | 某支腳接上幹線的直線撞到元件 X | 換幹線位置；或把那支腳改用 `p.wire` 繞外圍 |
| `trunk must be one non-zero horizontal or vertical segment` | 幹線長度是 0：元件腳都在同一欄卻用了 `hline`（或反過來） | 換成另一個方向的幹線 |
| `branch from … touches X's drawing`（X 是同一條 net 上的元件） | **幹線的端點或分支的落點剛好在 X 的腳端**（埠接回幹線、或別顆的腳橫接過來） | 通則：幹線端點與交叉點不要落在別顆元件的腳端。把 X 沿幹線的垂直方向移開 10～20（例：負載電容往下 10），或把要接的那顆移到兩支腳之間的高度 |
| `the trunk touches X's drawing` | X 的某支腳剛好落在幹線**中段** | 把 X 移開 10～20，讓它用一小段分支接上幹線 |
| 埠在幹線外側、分支碰到端點那顆元件 | 幹線只到元件腳，埠還要再往外接 | `p.hline(net, y, x0=埠的 x)`：手動把幹線延伸到埠 |
| `WORKSPACE_SAVE_FAILED (EPERM: rename …)` | 檔案暫時被鎖，跟畫法無關 | 原樣重跑一次 |
| `passes over pin X.Y, which is on no Net` | 分支經過另一支還沒接的腳 | 用 `route_order` 把那條 net 排前面；或改幹線 |
| `ERC_DANGLING_WIRE` | 幹線端點超出最後一支腳 | `hline`／`vline` 不要自己給端點，或把端點縮到剛好 |
| `No wire at (x, y)` | `p.wire` 的終點那裡沒有線 | 終點要落在 `hline`／`vline` 的範圍內，或前面寫過的同 net `wire` 上；都沒有就補一條短的幹線 |
| `VISUAL_LABEL_CLEARANCE` | 標籤壓到線或元件 | 把旁邊的元件／埠移開 10～30；軌的名字旁不要放接地符號 |
| 兩端元件說線跨過另一支腳 | 接線那端朝錯方向 | `p.two(..., first="D")` 等，讓要接的那支腳朝向連線 |
| 接地符號壓到元件 | 腳朝側面時預設位置不對 | `p.ground(ref, pin, x, y)` |
| `netlist 不等價` | 有線接錯或沒接上 | 先看上面的走線失敗訊息；都沒有就比 `out\<名稱>.exported.sp` 和 deck |
| `太鬆` | 外框太大 | 縮欄距／列距；埠靠近 |
| `列距 … 應在 70～140` | 上下兩顆太近或太遠 | 調 y；若是為了對齊別欄的列而拉長，兩顆都要真的跟別欄同列才會放行 |

**偶發失敗**：偶爾有一張「走線失敗」或 `WORKSPACE_SAVE_FAILED (EPERM)`，原樣重跑就過（工作區檔案暫時被鎖；2026-11-11 整批 46 張見過 2 張）。沒改任何東西卻失敗 → 先原樣重跑一次；`runbatch.py` 會自動重跑一次。

改了三次同一條線還不過 → 不要繼續試參數，改擺法（換欄、把元件移到幹線另一側、改用同名標籤）。

## 8. 交付前看圖清單（開 PNG 逐項看）

1. 沒有線穿過任何元件（`gate_through` 那一條除外）。
2. 沒有標籤壓到線、元件、別的標籤。
3. 每個連接點是一個乾淨的點；沒有兩個點擠在一起（同一條線上相距 ≤20 的兩個點——**檢查器不會抓，只能看圖**；把其中一顆移到同高或同欄就會併成一個點）、沒有多出來的線頭。
4. 對稱的電路看起來對稱（左右欄位、埠的高度、引線長度）。
5. 夠密：沒有大片空白、沒有為了對齊而拉長的空線。
6. 名字都是下標格式（V_b、V_out、M_1），沒有小寫的原始 net 名（v_b）。

有任何一項不過就改到過，再交付。交付時附 PNG 路徑（他要看圖才算數）。

## 9. 不准做的事

- 不准為了讓 CHECK 過而改 `acplan.py` 開頭的數值或放寬檢查規則；規則擋到合理的畫法 → 先問他。
- 不准用 `p.wire` 或 `free` 線穿過元件來硬接。
- 不准連正式站的 Agent／MCP 介面；只用本機的 headless 工具。
- 推到公開 repo 前先問使用者。
- 舊工具 `python -m toolkit validate` 對新產物會報錯（它的 schema 快取是舊的），**不要拿它當驗收**；新產物的驗收＝編輯器診斷＋netlist 等價＋慣例檢查＋看圖。

## 10. 什麼時候不用這個方法

- **有參照圖、要照著那張圖畫的**（課本圖、論文圖、手繪圖臨摹）→ 舊 SOP repo 根目錄的 `SOP.md`。他 2026-11-12 的裁示：有參照圖跑舊的，沒參照圖跑這份。
- 沒參照圖但這個工具畫不了的：剖面圖、波形示意、一般流程圖 → 舊 SOP repo 根目錄的 `SOP.md` 對應章節。**訊號方塊圖（方框＋加法點＋箭頭）畫得了，見 §6a。**
- deck 裡有本工具還不認得的元件（`parse_deck` 報錯）→ 先看 `pins_table.json` 有沒有那個符號；沒有就問他要不要擴充，不要硬畫。

## 11. 他退件或給新裁示時（讓品質只進不退）

1. 把裁示寫成一句可以量的規則，加進本檔 §5。
2. 能量的就加進 `acplan.py` 的 `check()`，並在 `test_check.py` 加一個「違反時會被抓到」的案例。
3. 改正那張圖的 `plans_py\<名稱>.py`（它就是新的範例）。
4. 跑 `python runbatch.py <全部名稱>`，確認既有範例全部還是 PASS；有變 FAIL 的要逐張處理，不准放寬規則帶過。
5. 本機 commit，進度檔 記一行。

## 11a. 推到公開 repo（他說要推才做）

1. `python _publish_acplan.py`（在 `upstream_mcp\` 裡；匯出到公開 repo 的 `acplan/`、SOP 去識別化、閘門）。
2. 在 repo 裡 commit（訊息用 Write 工具落檔再 `git commit -F`）。
3. **推之前用乾淨 clone 實跑**：clone 到暫存夾 → 把上游兩個檔複製進 `acplan/`、解開 → `runbatch.py` 全部 → 要全部 PASS，且 `out/*.exported.sp` 跟來源端逐位元相同（`.icproj.json` 只會差隨機 ID 與時間）。
4. `git push` → 比對遠端 hash、確認 `acplan/` 底下沒有 `.mjs`／`.tgz`／`pkg/`。

## 12. 上游工具／網站改版時

現況：`analog-canvas-headless-0.17.107.mjs`＋`analog-canvas-mcp-server-0.17.107.tgz`（雜湊在 `SHA256SUMS.txt`），來源是上游 GitHub `cascode-ai/analog-canvas` 的 release。

徵兆：他在網站 Import 我們的 `.icproj.json` 失敗或開出來跑版；或他說網站又更新了。

1. **先問他**要不要升級（下載新版屬於對外動作，且舊版仍可出圖）。
2. 新版下載到 `upstream_mcp\` 的**新檔名**（舊檔留著），把雜湊追加到 `SHA256SUMS.txt`。
3. 改 `acsession.py` 的 `HEADLESS` 與 `BIN` 指到新版（tgz 解到 `pkg_<版號>\`）。
4. 跑一張最簡單的（`cmos-inverter`）。失敗 → 看是哪個工具呼叫的格式變了（`acdraw.py` 裡的 `circuit_place`／`circuit_wire`／`apply_actions`／`inspect`／`render`／`netlist_code`），對照新版附的說明文件修。
5. 腳位可能變：重新產生 `pins_table.json`（放每種元件一顆，`inspect` 讀腳位座標），跟舊表 diff。
6. `python runbatch.py <全部>`：全部 PASS 才算升級完成；逐張看拼圖有沒有跑版。
7. 請他 Import 一張新產物確認網站開得起來。
8. 沒全過就退回舊版（把 `acsession.py` 兩行改回去），把卡住的地方寫進 進度檔。
