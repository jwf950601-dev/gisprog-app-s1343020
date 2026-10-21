"""臺北 YouBike 空站觀察：115-1 地理資訊系統運用程式的 App 範本。

執行方式：在終端機輸入 solara run app.py
"""

# pyright: reportMissingImports=false
# pyright: reportMissingModuleSource=false
import os
from pathlib import Path

import folium
import leafmap.foliumap as leafmap
import pandas as pd
import plotly.express as px
import solara

DATA_PATH = Path(__file__).parent / "data" / "my_youbike_w3.csv"

# 底圖：內政部國土測繪中心「臺灣通用電子地圖」，不需要金鑰。
# OSM 官方圖磚在 Codespaces 會被擋（瀏覽器沒送 Referer），CARTO 點陣圖磚需要金鑰，所以不用。
NLSC_URL = "https://wmts.nlsc.gov.tw/wmts/EMAP/default/GoogleMapsCompatible/{z}/{y}/{x}"
NLSC_ATT = "© 內政部國土測繪中心 臺灣通用電子地圖"
地圖高度 = "400px"

# 可借車數分級：(下限, 上限, 圖例文字, 顏色)。上限 None 代表沒有上限。
# 0 單獨一級（空站）；其餘切點是三個時段合併後、可借車數 > 0 站點的
# 第 25、50、75 百分位數（4、8、15 台），讓各級站數接近。
# 配色：空站用紅色＋黑框最醒目；其餘用藍色由淺到深，色盲也能靠深淺分辨。
分級表 = [
    (0, 0, "0（空站）", "#d62728"),
    (1, 4, "1–4", "#c6dbef"),
    (5, 8, "5–8", "#6baed6"),
    (9, 15, "9–15", "#2171b5"),
    (16, None, "16 以上", "#08306b"),
]

# 讀檔放在元件外面：App 啟動時只讀一次，切換選項時不會重新讀檔。
# sno、act 指定為字串，避免被自動轉成整數（W3 的 read_json 陷阱，read_csv 也一樣）。
df = pd.read_csv(DATA_PATH, dtype={"sno": str, "act": str})
df = df[df["act"] == "True"]  # 只看營運中的站（這份 CSV 的 act 存成 True/False）

# 時段加上說明（HW3 的決策：09:40 標成「上午」，不標成「通勤」）。
時段說明 = {
    "09/29 02:21": "09/29 02:21（深夜）",
    "09/29 09:40": "09/29 09:40（上午）",
    "09/29 12:41": "09/29 12:41（中午）",
}
df["時段名稱"] = df["時段"].map(時段說明)

時段們 = sorted(df["時段名稱"].unique())
行政區們 = sorted(df["sarea"].unique())

# reactive：值改變時，用到它的元件會自動重新執行。
# 放在元件外面，Page、全部畫面、單區畫面都讀得到同一個值。
門檻 = solara.reactive(0)
時段 = solara.reactive(時段們[0])
行政區 = solara.reactive("全部")
顯示全部 = solara.reactive(False)  # 選「全部」時，地圖要不要畫全部站點（預設關閉，手機較順）

# 手機版面：避免頁面被撐得比螢幕寬。
# 實測（手機模擬，螢幕 394 px）頁面被撐到 700 px，源頭是 Plotly 圖：它一開始量不到寬度，
# 會先用預設的 700 px 畫。外層容器都是 flex，子元素預設「不能比內容窄」（min-width: auto），
# 所以 700 px 會一層層往上撐開整頁。處理方式：
# 1. 讓所有 flex 子元素可以比內容窄（min-width: 0），寬度就不會往上傳。
# 2. Plotly 的容器寬度改成跟父層一樣（100%），超出的部分先藏起來。
# 3. 表格太寬時只在表格內捲動，不撐寬整頁（保險用）。
# 4. 時段按鈕可以換行。
# 5. v-row 預設左右各有 -12 px 的負邊距，實測比螢幕寬 24 px，設成 0。
# 6. 表格（實測統計表 689 px、站點清單 479 px）：文字可以換行、縮小每格留白，縮到螢幕寬度內。
# 7. 大標題置中；螢幕寬度 600 px 以下（手機）時，標題、內文、表格的字縮小。
# 8. CSS 只能把容器限制在螢幕寬度內，Plotly 圖本身還是 700 px（被藏起來）。
#    Plotly 只有在瀏覽器觸發 resize 事件時才會重新量寬度，所以用 重新量寬度() 元件觸發一次。
手機版CSS = """
.v-application__wrap, .solara-content-main, .solara-autorouter-content { max-width: 100vw; }
.v-sheet.d-flex > *, .v-row > * { min-width: 0; }
.plot-box { max-width: 100%; overflow-x: hidden; }
.plot-box .js-plotly-plot, .plot-box .plot-container, .plot-box .svg-container {
    width: 100% !important; max-width: 100% !important;
}
.table-box { max-width: 100%; overflow-x: auto; }
.time-toggle { flex-wrap: wrap; height: auto !important; max-width: 100%; }
.v-row { margin-left: 0 !important; margin-right: 0 !important; }
.table-box th, .table-box td {
    white-space: normal !important; padding: 4px 6px !important; font-size: 13px;
}
.solara-markdown h1 { text-align: center; }
@media (max-width: 600px) {
    .solara-markdown h1 { font-size: 1.5rem; }
    .solara-markdown h3 { font-size: 1.05rem; }
    .solara-markdown p, .solara-markdown li { font-size: 13px; }
    .table-box th, .table-box td { font-size: 12px; }
}
"""


def 分級顏色(可借車數):
    """依分級表，回傳這個可借車數對應的顏色。"""
    for 下限, 上限, _, 顏色 in 分級表:
        if 可借車數 >= 下限 and (上限 is None or 可借車數 <= 上限):
            return 顏色
    return "#999999"


def 轉成GeoJSON(資料):
    """把站點資料轉成 GeoJSON。注意 GeoJSON 的座標順序是 [經度, 緯度]。

    properties 只放點擊時要顯示的欄位（站名、可借車數）。
    """
    features = []
    for _, 列 in 資料.iterrows():
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [列["longitude"], 列["latitude"]]},
            "properties": {"站名": 列["sna"], "可借車數": int(列["available_rent_bikes"])},
        })
    return {"type": "FeatureCollection", "features": features}


def 站點樣式(feature):
    """每個圓點的樣式：填色依分級；空站用黑色粗框，其他用細灰框。"""
    可借車數 = feature["properties"]["可借車數"]
    是空站 = 可借車數 == 0
    return {
        "fill": True,  # folium 的 CircleMarker 預設不填色（只有外框），要明確打開
        "fillColor": 分級顏色(可借車數),
        "fillOpacity": 0.9,
        "color": "#000000" if 是空站 else "#555555",
        "weight": 2.5 if 是空站 else 0.8,
    }


def 建立地圖HTML(資料):
    """用 leafmap（folium 後端）畫站點地圖，轉成 HTML 字串。沒有站點時只畫臺北市底圖。"""
    m = leafmap.Map(location=[25.06, 121.55], zoom_start=12, tiles=NLSC_URL, attr=NLSC_ATT, max_zoom=18)
    if len(資料) > 0:
        # marker 改成圓點（預設是圖標，點很密時看不清楚位置）；
        # info_mode="on_click"：點擊站點時彈出站名與可借車數；add_geojson 會自動縮放到站點範圍。
        m.add_geojson(
            轉成GeoJSON(資料),
            layer_name="YouBike 站點",
            info_mode="on_click",
            marker=folium.CircleMarker(radius=7),
            style_function=站點樣式,
        )
    m.add_legend(
        title="可借車數（台）",
        labels=[標籤 for _, _, 標籤, _ in 分級表],
        colors=[顏色 for _, _, _, 顏色 in 分級表],
        position="bottomright",
    )
    return m.to_html()


@solara.component
def 站點地圖(資料):
    """顯示地圖。只有行政區、時段或「顯示全部」改變時才重畫，避免每次操作都重新產生 HTML。"""
    html = solara.use_memo(
        lambda: 建立地圖HTML(資料),
        dependencies=[行政區.value, 時段.value, 顯示全部.value],
    )
    # folium 產生的是完整的 HTML 網頁，用 iframe 嵌進頁面。
    solara.HTML(
        tag="iframe",
        attributes={"srcdoc": html, "style": f"width:100%;height:{地圖高度};border:0"},
    )
    solara.Markdown(f"地圖站點數：{len(資料)}（{時段.value}，點擊站點可看站名與可借車數）")


@solara.component
def 地圖區():
    """依目前選的行政區與時段挑出站點，再交給站點地圖。"""
    當時 = df[df["時段名稱"] == 時段.value]
    if 行政區.value != "全部":
        站點地圖(當時[當時["sarea"] == 行政區.value])
        return

    solara.Switch(label=f"顯示全部站點（{len(當時)} 站，手機上可能比較慢）", value=顯示全部)
    if 顯示全部.value:
        站點地圖(當時)
    else:
        # 先顯示沒有站點的底圖，並用醒目的警告框提醒怎麼讓站點出現。
        solara.Warning(
            "地圖目前沒有顯示站點！請在上方「選擇行政區」選一區，或打開「顯示全部站點」開關。",
            icon=True,
        )
        站點地圖(當時.iloc[0:0])


def 計算指標(資料, 分組欄位, 門檻值):
    """依分組欄位計算站數、空站數、空站比例、滿站數、滿站比例、權重有車率。

    空站：可借車 <= 門檻值（預設 0）；滿站：可還空位 = 0。
    權重有車率 = Σ可借 ÷ Σ可用格位（可借＋可還），等於把每站有車率用可用格位數加權平均。
    """
    資料 = 資料.assign(
        空站=資料["available_rent_bikes"] <= 門檻值,
        滿站=資料["available_return_bikes"] == 0,
        可用格位=資料["available_rent_bikes"] + 資料["available_return_bikes"],
    )
    表 = 資料.groupby(分組欄位).agg(
        站數=("sno", "size"),
        空站數=("空站", "sum"),
        滿站數=("滿站", "sum"),
        可借總數=("available_rent_bikes", "sum"),
        可用格位總數=("可用格位", "sum"),
    )
    表["空站比例"] = (表["空站數"] / 表["站數"]).round(3)
    表["滿站比例"] = (表["滿站數"] / 表["站數"]).round(3)
    表["權重有車率"] = (表["可借總數"] / 表["可用格位總數"]).round(3)
    欄位順序 = ["站數", "空站數", "空站比例", "滿站數", "滿站比例", "權重有車率"]
    return 表[欄位順序].reset_index()


def 比例長表(表):
    """把三個比例欄位轉成長表（一列＝一個時段的一個指標），給分組長條圖使用。"""
    return 表.melt(
        id_vars="時段名稱",
        value_vars=["空站比例", "滿站比例", "權重有車率"],
        var_name="指標",
        value_name="比例",
    )


@solara.component_vue("resize_fix.vue")
def 重新量寬度():
    """觸發瀏覽器的 resize 事件，讓 Plotly 圖配合螢幕寬度（說明見 resize_fix.vue）。"""


def 點擊長條(資料):
    """在「全部」畫面點某一區的長條，就切換到那一區（下拉選單也會跟著變）。"""
    # 橫向長條圖的行政區名稱在 Y 軸，所以讀 ys。
    點到的區們 = 資料["points"]["ys"]
    if 點到的區們:
        行政區.value = 點到的區們[0]


@solara.component
def 全部畫面():
    """選「全部」時：依上方選的時段，比較各區的空站比例。"""
    當時 = df[df["時段名稱"] == 時段.value]
    表 = 計算指標(當時, "sarea", 門檻.value)
    表 = 表.sort_values("空站比例", ascending=False)

    圖 = px.bar(
        表,
        x="空站比例",
        y="sarea",
        orientation="h",
        labels={"sarea": "", "空站比例": "空站比例"},
    )
    # 每區給 30 px 高度，行政區名稱才不會被 Plotly 自動隔行省略；換成區數更多的縣市也適用。
    # 留白縮小（margin），手機上才有空間畫長條。
    圖.update_layout(
        yaxis={"categoryorder": "total ascending"},
        xaxis_tickformat=".0%",
        height=80 + 30 * len(表),
        margin={"l": 10, "r": 10, "t": 10, "b": 40},
    )
    # 標題放在圖外面用文字顯示：Plotly 的標題不會換行，手機上會被切掉。
    solara.Markdown(f"### {時段.value}：各區空站比例\n可借車 ≤ {門檻.value} 算空站（只算營運中的站）。"
                    "點某一區的長條，可以直接查看該區各時段的狀況。")
    with solara.Column(classes=["plot-box"]):
        solara.FigurePlotly(圖, on_click=點擊長條)
        重新量寬度()

    # 表格的欄名改成中文（圖表仍用原本的 sarea 欄位）。
    with solara.Column(classes=["table-box"]):
        solara.DataFrame(表.rename(columns={"sarea": "行政區"}))


@solara.component
def 單區畫面(區名):
    """選某一區時：看這個區在各時段的狀況。"""
    solara.Markdown(f"### {區名}：各時段狀況\n空站比例、滿站比例與權重有車率（可借車 ≤ {門檻.value} 算空站，"
                    "只算營運中的站）。灰底＝地圖目前的時段。")

    該區 = df[df["sarea"] == 區名]
    表 = 計算指標(該區, "時段名稱", 門檻.value)

    # barmode="group"：同一個時段的三個指標並排；text_auto 把數值直接標在長條上。
    圖 = px.bar(
        比例長表(表),
        x="時段名稱",
        y="比例",
        color="指標",
        barmode="group",
        text_auto=".1%",
        labels={"時段名稱": "", "比例": "比例", "指標": ""},
    )
    # 圖例改放在圖的上方、橫向排列（放右側會占掉手機一半寬度）；留白縮小。
    圖.update_layout(
        yaxis_tickformat=".0%",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        margin={"l": 10, "r": 10, "t": 40, "b": 10},
    )
    # 類別軸的第 i 個類別位在 x = i，前後各延伸 0.5 就是整個類別的寬度。
    i = list(表["時段名稱"]).index(時段.value)
    圖.add_vrect(x0=i - 0.5, x1=i + 0.5, fillcolor="gray", opacity=0.15, line_width=0)
    with solara.Column(classes=["plot-box"]):
        solara.FigurePlotly(圖)
        重新量寬度()

    with solara.Column(classes=["table-box"]):
        solara.DataFrame(表)

    站點清單(區名)


def 整理站點清單(資料):
    """挑出站名、可借、可還三欄並改成中文欄名，依可借車數由少到多排序（空站排最前面）。"""
    清單 = 資料[["sna", "available_rent_bikes", "available_return_bikes"]]
    清單 = 清單.rename(columns={"sna": "站名", "available_rent_bikes": "可借車數", "available_return_bikes": "可還空位"})
    # 每一站都以「YouBike2.0_」開頭，拿掉可以讓表格在手機上窄一點。
    清單["站名"] = 清單["站名"].str.replace("YouBike2.0_", "", regex=False)
    return 清單.sort_values("可借車數").reset_index(drop=True)


@solara.component
def 站點清單(區名):
    """這一區在目前時段的每一站，會隨時段切換更新，和地圖上的點一一對應。"""
    該區當時 = df[(df["sarea"] == 區名) & (df["時段名稱"] == 時段.value)]
    solara.Markdown(f"### {時段.value}：{區名}各站（{len(該區當時)} 站，可借車數由少到多）")
    with solara.Column(classes=["table-box"]):
        solara.DataFrame(整理站點清單(該區當時), items_per_page=10)


@solara.component
def Page():
    solara.Title("YouBike 空站觀察")
    solara.Markdown("# 臺北 YouBike 各區空站比例")

    # 電腦（中等寬度以上）：左 5 格放控制項與地圖、右 7 格放圖表與表格；
    # 手機：每欄都占滿 12 格，自動變成上下排列（篩選 → 地圖 → 圖表 → 表格）。
    solara.Style(手機版CSS)
    # min-width: 0：欄位預設會被裡面最寬的內容撐開，設成 0 才會乖乖縮到螢幕寬度。
    欄位樣式 = {"min-width": "0", "max-width": "100%"}
    with solara.ColumnsResponsive(default=12, medium=[5, 7]):
        with solara.Column(style=欄位樣式):
            solara.Select("選擇行政區", values=["全部"] + 行政區們, value=行政區)
            solara.ToggleButtonsSingle(value=時段, values=時段們, dense=True, classes=["time-toggle"])
            solara.SliderInt("空站門檻：可借車 ≤", value=門檻, min=0, max=5)
            solara.Markdown("<small>空站門檻只影響空站比例，不影響地圖分級。</small>")
            地圖區()
        with solara.Column(style=欄位樣式):
            if 行政區.value == "全部":
                全部畫面()
            else:
                單區畫面(行政區.value)

    # 資料時間是 snapshot_time（抓取時間），三個快照都在 2026-09-29（星期二）。
    solara.Markdown(
        "- 資料來源：臺北市資料大平臺「YouBike2.0 臺北市公共自行車即時資訊」，"
        "依政府資料開放授權條款第 1 版使用。\n"
        "- 資料時間：2026-09-29（二）02:21（深夜）、09:40（上午）、12:41（中午）三個時段的快照。\n"
        "- 只計入營運中的站（暫停營運的 27 站不列入）。\n"
        "- 臺大公館校區為資料原始分區，跨大安、中正區，未併入行政區。\n"
        "- 底圖：內政部國土測繪中心「臺灣通用電子地圖」。\n"
        "- 地圖分級：0 台（空站）單獨一級；其餘依三個時段合併後、可借車數大於 0 的站點的"
        "第 25、50、75 百分位數（4、8、15 台）切成 1–4、5–8、9–15、16 以上四級。"
        "分級固定，不隨空站門檻改變。"
    )
    # 暫時的檢查用（決策點 2）：確認上線的 App 不是以 root 執行。1000＝一般使用者、0＝root。確認後刪除。
    solara.Markdown(f"（暫時的檢查用）執行使用者 UID：{os.getuid()}")
