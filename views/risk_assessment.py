import plotly.express as px
import streamlit as st

from core import data, risk, sensor_diagnostics as sdx, ui
from core.theme import plot_layout

CATEGORIES = ["Sleep", "Cardiovascular & Physiological", "Radiation", "Behavioral & Isolation", "Environmental", "Nutrition"]
KEYWORDS = {"Sleep": ["sleep"], "Cardiovascular & Physiological": ["cardio"], "Radiation": ["radiation"],
            "Behavioral & Isolation": ["behav"], "Environmental": ["environment"], "Nutrition": ["nutrition"]}


def _rows(r, name):
    cat = r["cols"]["category"]
    if not cat:
        return r["df"].iloc[0:0]
    text = r["df"][cat].astype(str).str.lower()
    return r["df"][text.apply(lambda t: any(k in t for k in KEYWORDS[name]))]


def render():
    ui.title("Risk Assessment", "Results from the team's Risk Diagnostics. Nothing is recalculated on this page.")
    r = risk.load()
    if r is not None:
        st.caption(f"Source: {r['source']}")

    ui.section("Overall Risk Summary")
    if r is None:
        ui.empty("No Risk Diagnostics output yet. Upload the sensor, mood, food and sleep CSVs from Mission Control.")
    else:
        counts = risk.summary_counts(r)
        cols = st.columns(5)
        for c, (g, n) in zip(cols, counts.items()):
            with c:
                ui.card(g, n, "variable(s)", None, kind="calc")
        lt = risk.latest_time(r)
        ov = sdx.overview(data.frames())
        bits = [f"Latest assessment: {lt.strftime('%Y-%m-%d %H:%M')}" if lt is not None else None,
                f"Observation window: {ov['start'].date()} to {ov['end'].date()}" if ov else None,
                f"Sensor records: {ov['sensor']:,} | Mood check-ins: {ov['mood']:,} | Food records: {ov['food']:,}" if ov else None]
        st.caption("  |  ".join(b for b in bits if b))

    ui.section("Risk Category", "One tab for every risk category. Within-reference items are hidden; everything else is listed.")
    for tab, name in zip(st.tabs(CATEGORIES), CATEGORIES):
        with tab:
            if r is None:
                ui.empty("No diagnostics available for this category yet.")
                continue
            sub = _rows(r, name)
            if sub.empty:
                ui.empty("No diagnostics available for this category yet.")
                continue
            lv = sub.apply(lambda x: risk.level_of(x, r["cols"]), axis=1)
            show = sub[lv != "info"]
            if show.empty:
                st.markdown(ui.pill("All assessments within reference", "ok"), unsafe_allow_html=True)
            else:
                order = show.assign(_r=lv[lv != "info"].map(risk.RANK)).sort_values("_r").drop(columns="_r")
                ui.risk_cards(order, r)

    ui.section("Risk History")
    if r is not None:
        df = r["df"]
        t = r["cols"]["time"]
        lvl = "level" if "level" in df.columns else r["cols"]["classification"]
        if t and lvl and df[t].dtype.kind == "M":
            h = df.dropna(subset=[t]).assign(_d=lambda x: x[t].dt.date).groupby(["_d", lvl]).size().reset_index(name="count")
            fig = px.bar(h, x="_d", y="count", color=lvl)
            plot_layout(fig, 300, "Assessments per day by level")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            ui.empty("History needs a time column and a level or classification column in the diagnostics output.")

    with st.expander("Exploratory correlation analysis"):
        res = sdx.correlation(data.frames())
        if res is None or res["corr"].empty:
            st.write("Not enough overlapping daily data to calculate correlations.")
        else:
            fig = px.imshow(res["corr"], zmin=-1, zmax=1, color_continuous_scale="RdBu_r", text_auto=".2f", aspect="auto")
            plot_layout(fig, 520, "Daily Spearman correlation matrix")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with st.expander("Important data limitations"):
        for lim in sdx.LIMITATIONS:
            st.markdown(f"- {lim}")
        miss = sdx.missing_columns(data.frames())
        if miss:
            st.markdown(f"- Sensor columns not in the uploaded file (treated as no data): {', '.join(miss)}")
