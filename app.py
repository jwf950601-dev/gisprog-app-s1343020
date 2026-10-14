"""臺北 YouBike 空站觀察：115-1 地理資訊系統運用程式的 App 範本。

執行方式：在終端機輸入 solara run app.py
"""

# pyright: reportMissingImports=false
# pyright: reportMissingModuleSource=false
from pathlib import Path

import pandas as pd
import plotly.express as px
import solara

DATA_PATH = Path(__file__).parent / "data" / "my_youbike_w3.csv"

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


@solara.component
def 全部畫面():
    """選「全部」時：選一個時段，比較各區的空站比例。"""
    solara.ToggleButtonsSingle(value=時段, values=時段們)

    當時 = df[df["時段名稱"] == 時段.value]
    表 = 計算指標(當時, "sarea", 門檻.value)
    表 = 表.sort_values("空站比例", ascending=False)

    圖 = px.bar(
        表,
        x="空站比例",
        y="sarea",
        orientation="h",
        title=f"{時段.value}，可借車 ≤ {門檻.value} 算空站（只算營運中的站）",
        labels={"sarea": "", "空站比例": "空站比例"},
    )
    # 每區給 30 px 高度，行政區名稱才不會被 Plotly 自動隔行省略；換成區數更多的縣市也適用。
    圖.update_layout(
        yaxis={"categoryorder": "total ascending"},
        xaxis_tickformat=".0%",
        height=150 + 30 * len(表),
    )
    solara.FigurePlotly(圖)

    solara.DataFrame(表)


@solara.component
def 單區畫面(區名):
    """選某一區時：看這個區在各時段的狀況。"""
    solara.Markdown(f"## {區名}：各時段狀況（可借車 ≤ {門檻.value} 算空站）")

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
        title=f"{區名}各時段的空站比例、滿站比例與權重有車率（只算營運中的站）",
        labels={"時段名稱": "", "比例": "比例", "指標": "指標"},
    )
    圖.update_layout(yaxis_tickformat=".0%")
    solara.FigurePlotly(圖)

    solara.DataFrame(表)


@solara.component
def Page():
    solara.Title("YouBike 空站觀察")
    solara.Markdown("# 臺北 YouBike 各區空站比例")

    # 下拉選單和滑桿預設會撐滿整個頁寬，用 Column 限制最大寬度，比較好操作。
    with solara.Column(style={"max-width": "480px"}):
        solara.Select("選擇行政區", values=["全部"] + 行政區們, value=行政區)
        solara.SliderInt("空站門檻（只影響空站比例）：可借車 ≤", value=門檻, min=0, max=5)

    if 行政區.value == "全部":
        全部畫面()
    else:
        單區畫面(行政區.value)

    solara.Markdown(
        "資料來源：臺北市 YouBike 2.0 即時資料（臺北市資料大平臺），"
        "依政府資料開放授權條款第 1 版使用。"
        f"資料時間：{時段.value}。"
    )
