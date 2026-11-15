import streamlit as st

from core import data, risk, ui
from core import sleep_diagnostics as sd


def _stat(v, digits=1):
    return None if v is None or v != v else f"{v:.{digits}f}"


def render():
    ui.title("Sleep", "Sleep patterns, quality and sleep-related risks.")
    scored = data.sleep_scored()
    if scored is None and data.resolve("sleep_hours") is None:
        ui.empty("No sleep data found. Upload the sleep CSV (date and sleep_hours columns) or the sensor CSV from Mission Control.")
        return

    ui.section("Sleep Summary", "Latest recording." + (" Sleep quality is calculated by the sleep diagnostics." if scored is not None else ""))
    cards = [{"key": "sleep_hours", "status": ["sleep"]}]
    if scored is not None:
        cards.append({"key": "sleep_quality", "kind": "calc"})
    ui.cards_row(cards + ["sleep_efficiency"], show_delta=True)
    if scored is not None:
        basis = scored.iloc[-1].get("quality_basis", "")
        if basis == "duration":
            st.caption("Sleep quality for the latest night uses sleep duration only, because this file has no efficiency, "
                       "wake-after-sleep-onset or fragmentation columns. A full night of sleep therefore scores 100%. "
                       "Add those columns for a fuller score.")
        elif basis:
            st.caption(f"Sleep quality for the latest night is calculated from: {basis}.")

    if scored is not None:
        _, s = sd.assess(scored)
        ui.section("Sleep History Summary", f"{s['n']} recorded sleep sessions. Latest night: {s['status']}.")
        rows = [("Overall average", s["avg_duration"], s["avg_quality"]), ("Last 7 sessions", s["duration_7"], s["quality_7"]),
                ("Last 14 sessions", s["duration_14"], s["quality_14"])]
        cols = st.columns(4)
        for c, (lab, dur, q) in zip(cols, rows):
            with c:
                ui.card(lab, _stat(dur, 2), "hours", f"Quality {_stat(q) or data.NO_DATA}%", kind="calc")
        with cols[3]:
            ui.card("Nights below 7 hours in a row", s["consecutive_low"], "", f"Quality trend: {s['trend'] or data.NO_DATA}", kind="calc")

    ui.section("Sleep Trends")
    ui.trend_grid(["sleep_hours", "sleep_quality", "sleep_efficiency"], per_row=3)
    ui.trend_grid(["sleep_latency", "waso", "fragmentation"], per_row=3)

    ui.section("Sleep Risk Assessment", "From the sleep diagnostics.")
    r = risk.load()
    ui.alert_cards(risk.related(r, ["sleep"]), r) if r else ui.empty("No Data")

    ui.section("History")
    ui.history_table(["sleep_hours", "sleep_quality", "sleep_efficiency"])
