from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import data, risk, sensor_diagnostics as sdx, ui
from core.config import SURVEY_FILE, SURVEY_ITEMS
from core.theme import plot_layout

PATH = data.DATA_DIR / SURVEY_FILE


def _items(df):
    """Items that have data. The uploaded mood file has one merged confinement_discomfort column, the GUI survey has two."""
    have = lambda k: df is not None and k in df and df[k].notna().any()
    items = [(k, label) for k, label in SURVEY_ITEMS if have(k)]
    if have("confinement_discomfort"):
        items.append(("confinement_discomfort", "Confinement & Discomfort"))
    return items or list(SURVEY_ITEMS)   # nothing yet: show empty cards


def render():
    ui.title("Crew Wellbeing", "Self-reported wellbeing. These are monitoring signals, not diagnoses.")

    ui.section("Mood and Tension Check", "Manual entry: the astronaut answers the survey. Scale 1 to 10 (1 = worst, 10 = best).")
    with st.form("wellbeing_form"):
        vals, cols = {}, st.columns(3)
        for i, (k, label) in enumerate(SURVEY_ITEMS):
            vals[k] = cols[i % 3].slider(label, 1, 10, 5, help="1 = worst, 10 = best")
        if st.form_submit_button("Submit survey"):
            row = pd.DataFrame([{"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"), **vals}])
            row.to_csv(PATH, mode="a", header=not PATH.exists(), index=False)
            st.success("Survey saved.")

    df = sdx.mood_table(data.frames())  # survey answers + any uploaded mood check-in file; read after the form
    items = _items(df)
    cols = st.columns(3)
    for i, (k, label) in enumerate(items):
        with cols[i % 3]:
            s = df[k].dropna() if df is not None and k in df else []
            if len(s):
                ts = df.loc[s.index[-1], "timestamp"].strftime("%Y-%m-%d %H:%M")
                delta = f"Change since previous: {s.iloc[-1] - s.iloc[-2]:+g}" if len(s) > 1 else None
                ui.card(label, f"{s.iloc[-1]:g}", "/10", ts, kind="manual", delta=delta)
            else:
                ui.card(label, None, "", None, kind="manual")
            st.write("")
    if df is not None and (df["src"] == "mood_csv").any():
        st.caption("An uploaded mood check-in file is included. Its score direction (higher = more strain) is kept as supplied; "
                   "GUI survey answers use 1 = worst, 10 = best. Both are handled correctly by the risk check.")

    ui.section("Behavioral Trend")
    if df is None or df[[k for k, _ in items if k in df]].dropna(how="all").empty:
        ui.empty("No survey responses yet.")
    else:
        fig = go.Figure()
        for k, label in items:
            if k in df:
                d = df.dropna(subset=[k])
                if not d.empty:
                    fig.add_scatter(x=d["timestamp"], y=d[k], mode="lines+markers", name=label)
        plot_layout(fig, 340)
        fig.update_yaxes(range=[0.5, 10.5], title="Score (1 to 10)")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        with st.expander("Survey history"):
            st.dataframe(df.sort_values("timestamp", ascending=False), use_container_width=True, hide_index=True)

    ui.section("Related Alerts")
    r = risk.load()
    if r is None:
        ui.empty("No Data")
    else:
        ui.alert_cards(risk.related(r, ["behav", "wellbeing", "isolation"]), r)
