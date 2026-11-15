import streamlit as st

from core import data, risk, sensor_diagnostics as sdx, ui
from core.theme import plot_layout
import plotly.graph_objects as go


def _bp_card():
    s, d = data.resolve("bp_sys"), data.resolve("bp_dia")
    sv, ts = data.latest(s)
    dv, _ = data.latest(d)
    both = sv is not None and dv is not None
    ui.card("Blood Pressure", f"{data.fmt(sv)}/{data.fmt(dv)}" if both else None, "mmHg", ts, risk.status_for(risk.load(), ["bp"]), kind="live")


def render():
    ui.title("Vitals & Activity", "Physiological measurements and physical activity.")
    ui.section("Current Measurements")
    ui.cards_row([{"key": "heart_rate", "status": ["heart_rate"]}, {"key": "hrv", "status": ["hrv"]}, {"key": "spo2", "status": ["spo2"]}])
    st.write("")
    c = st.columns(3)
    with c[0]:
        ui.metric_card("body_temp", ["body_temp"])
    with c[1]:
        _bp_card()
    with c[2]:
        ui.metric_card("glucose", ["glucose"])

    ui.section("Cardiovascular Trends")
    ui.trend_grid(["heart_rate", "hrv", "spo2", "body_temp", "glucose"], per_row=2)
    t1, t2 = st.columns(2)
    with t1:
        ui.trend("bp_sys")
    with t2:
        ui.trend("bp_dia")

    ui.section("Physical Activity", "Recorded activity time from the sensor's activity_state. Intensity is not recorded.")
    ctx = sdx.context(data.frames())
    if ctx is not None:
        by_day = sdx.activity_by_day(ctx)
        fig = go.Figure()
        for state in ["EXERCISE", "RECOVERY"]:
            fig.add_scatter(x=by_day.index, y=by_day[state], mode="lines+markers", name=state.title())
        plot_layout(fig, 300, "Daily recorded exercise and recovery time (minutes)")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        gh = sdx.gravity_hours(data.frames())
        fig2 = go.Figure(go.Bar(x=[str(i) for i in gh.index], y=gh.values, text=[f"{v:.1f} h" for v in gh.values], textposition="outside"))
        plot_layout(fig2, 280, "Recorded time at each gravity level (hours)")
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
    else:
        ui.cards_row(["activity", "exercise_duration", "exercise_intensity", "fatigue"])
        ui.trend_grid(["activity", "exercise_duration", "exercise_intensity", "fatigue"], per_row=2)
