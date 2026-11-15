"""Sleep monitoring diagnostics (teammate's Part 1 script), ported to functions.

The scoring formulas, thresholds and risk rules are unchanged from the original script.
Pure pandas/numpy, so it can be imported anywhere. No Streamlit, no file access.
"""
import numpy as np
import pandas as pd

SLEEP_COLUMNS = ["date", "sleep_hours", "sleep_efficiency_pct", "sleep_latency_min", "waso_min",
                 "fragmentation_count", "avg_sleep_hr_bpm", "avg_sleep_hrv_ms"]
# Recommended actions / countermeasures per sleep risk. Left empty on purpose: fill in the team's approved
# wording here (nothing is invented). Empty entries show "not provided yet" in the GUI.
COUNTERMEASURES = {
    "Acute Sleep Deficiency": None,
    "Extended Sleep Duration": None,
    "Sustained Sleep Deficiency": None,
    "Recurring Weekly Sleep Deficiency": None,
}
COMPUTED = ["duration_score", "efficiency_score", "interruption_score", "recovery_score", "sleep_quality_pct"]


def is_sleep_frame(df):
    cols = {str(c).strip().lower() for c in df.columns}
    # the multi-sensor table (one row per reading, has activity_state) is handled by sensor_diagnostics instead
    return {"date", "sleep_hours"} <= cols and "activity_state" not in cols


def duration_score(hours):
    if 7 <= hours <= 8:
        return 100
    elif hours < 7:
        return max(0, (hours / 8) * 100)
    elif hours <= 9:
        return max(0, 100 - ((hours - 8) * 25))
    return max(0, 75 - ((hours - 9) * 25))


def efficiency_score(value):
    if pd.isna(value):
        return np.nan
    return np.clip(value, 0, 100)


def interruption_score(row):
    waso = row.get("waso_min", np.nan)
    fragments = row.get("fragmentation_count", np.nan)
    scores = []
    if pd.notna(waso):
        scores.append(max(0, 100 - waso))
    if pd.notna(fragments):
        scores.append(max(0, 100 - fragments * 8))
    return np.mean(scores) if scores else np.nan


def _recovery(sleep):
    out = pd.Series(np.nan, index=sleep.index)
    for i in range(len(sleep)):
        if i < 7:
            continue
        previous = sleep.iloc[max(0, i - 7):i]
        current = sleep.iloc[i]
        comps = []
        if "avg_sleep_hrv_ms" in sleep.columns and pd.notna(current.get("avg_sleep_hrv_ms")):
            base = previous["avg_sleep_hrv_ms"].median()
            if pd.notna(base) and base > 0:
                comps.append(np.clip(current["avg_sleep_hrv_ms"] / base * 100, 0, 100))
        if "avg_sleep_hr_bpm" in sleep.columns and pd.notna(current.get("avg_sleep_hr_bpm")):
            base = previous["avg_sleep_hr_bpm"].median()
            if pd.notna(base) and base > 0:
                comps.append(np.clip(100 - (current["avg_sleep_hr_bpm"] - base) * 5, 0, 100))
        if comps:
            out.iloc[i] = np.mean(comps)
    return out


def _quality(row):
    comps = [(row["duration_score"], 0.40), (row["efficiency_score"], 0.30),
             (row["interruption_score"], 0.20), (row["recovery_score"], 0.10)]
    avail = [(s, w) for s, w in comps if pd.notna(s)]
    if not avail:
        return np.nan
    tw = sum(w for _, w in avail)
    return round(sum(s * w for s, w in avail) / tw, 1)


def quality_basis(row):
    """Which parts of the quality score had data for this night."""
    names = [("duration", row["duration_score"]), ("efficiency", row["efficiency_score"]),
             ("interruptions", row["interruption_score"]), ("recovery", row["recovery_score"])]
    return " + ".join(n for n, v in names if pd.notna(v))


def score(df):
    """Returns (df_with_scores, sleep). df_with_scores is the original table (other metrics untouched)
    plus the computed columns; sleep is the cleaned, date-sorted sleep table used by assess()."""
    src = df.copy()
    src.columns = [str(c).strip().lower() for c in src.columns]
    sleep = src[[c for c in SLEEP_COLUMNS if c in src.columns]].copy()
    sleep["date"] = pd.to_datetime(sleep["date"], errors="coerce")
    for c in sleep.columns:
        if c != "date":
            sleep[c] = pd.to_numeric(sleep[c], errors="coerce")
    sleep = sleep.dropna(subset=["date", "sleep_hours"]).sort_values("date")
    orig_idx = sleep.index.to_numpy()
    sleep = sleep.reset_index(drop=True)
    if sleep.empty:
        return src, sleep
    sleep["duration_score"] = sleep["sleep_hours"].apply(duration_score)
    sleep["efficiency_score"] = sleep["sleep_efficiency_pct"].apply(efficiency_score) if "sleep_efficiency_pct" in sleep else np.nan
    sleep["interruption_score"] = sleep.apply(interruption_score, axis=1)
    sleep["recovery_score"] = _recovery(sleep)
    sleep["sleep_quality_pct"] = sleep.apply(_quality, axis=1)
    sleep["quality_basis"] = sleep.apply(quality_basis, axis=1)
    for name in COMPUTED + ["quality_basis"]:
        src[name] = np.nan if name != "quality_basis" else ""
        src.loc[orig_idx, name] = sleep[name].to_numpy()
    return src, sleep


def assess(sleep):
    """Returns (risks, summary). risks is a list of {name, detail}; summary holds the history stats."""
    latest = sleep.iloc[-1]
    last_7, last_14 = sleep.tail(7), sleep.tail(14)
    hours, quality = latest["sleep_hours"], latest["sleep_quality_pct"]
    duration_7 = last_7["sleep_hours"].mean()
    consecutive_low = 0
    for h in reversed(sleep["sleep_hours"].tolist()):
        if h < 7:
            consecutive_low += 1
        else:
            break

    risks = []
    if hours < 7:
        risks.append({"name": "Acute Sleep Deficiency", "detail": (
            f"Only {hours:.1f} hours of sleep were recorded. Insufficient sleep may impair alertness, "
            "attention, reaction time, and decision-making.")})
    if hours > 9:
        risks.append({"name": "Extended Sleep Duration", "detail": (
            "Sleep exceeded 9 hours. Persistent unusually long sleep should be reviewed alongside "
            "recovery and other health indicators.")})
    if consecutive_low >= 14:
        risks.append({"name": "Sustained Sleep Deficiency", "detail": (
            f"Sleep has remained below 7 hours for {consecutive_low} consecutive nights. Continued sleep "
            "restriction can accumulate sleep debt and impair cognitive and operational performance.")})
    if len(last_7) >= 7 and duration_7 < 7 and consecutive_low < 14:
        risks.append({"name": "Recurring Weekly Sleep Deficiency", "detail": (
            "Average sleep duration over the last 7 records is below 7 hours. Continued exposure may "
            "lead to cumulative sleep loss.")})

    trend = None
    if len(last_7) >= 2:
        first, cur = last_7.iloc[0]["sleep_quality_pct"], last_7.iloc[-1]["sleep_quality_pct"]
        if pd.notna(first) and pd.notna(cur):
            d = cur - first
            trend = "Improving" if d > 2 else "Declining" if d < -2 else "Relatively stable"

    status = ("Below optimal" if hours < 7 else "Optimal" if hours <= 8
              else "Above optimal range" if hours <= 9 else "Extended sleep")
    summary = dict(date=latest["date"], hours=hours, quality=quality, status=status, n=len(sleep),
                   avg_duration=sleep["sleep_hours"].mean(), avg_quality=sleep["sleep_quality_pct"].mean(),
                   duration_7=duration_7, quality_7=last_7["sleep_quality_pct"].mean(),
                   duration_14=last_14["sleep_hours"].mean(), quality_14=last_14["sleep_quality_pct"].mean(),
                   consecutive_low=consecutive_low, trend=trend)
    return risks, summary


def risk_rows(sleep):
    """Sleep diagnostics as rows in the shared Risk Diagnostics format. No severity is invented:
    a detected risk is labelled 'Risk detected', otherwise 'No risk detected' (the script's own wording)."""
    if sleep is None or sleep.empty:
        return pd.DataFrame()
    risks, s = assess(sleep)
    base = dict(timestamp=s["date"], category="Sleep", metric_key="sleep")
    if not risks:
        return pd.DataFrame([dict(base, indicator="Sleep risk screening", parameter="Sleep Hours", result=s["hours"],
                                  classification="No risk detected", level="info",
                                  supporting_data="No sleep-related risks detected in the available data.",
                                  recommended_action=None)])
    return pd.DataFrame([dict(base, indicator=r["name"], parameter="Sleep Hours", result=s["hours"],
                              classification="Risk detected", level="warning", supporting_data=r["detail"],
                              recommended_action=COUNTERMEASURES.get(r["name"])) for r in risks])


def report_text(sleep):
    """The sleep monitoring report in the same text layout as the original script's printout."""
    risks, s = assess(sleep)
    bar, line = "=" * 55, "-" * 55
    out = [bar, "          ASTRA-S | SLEEP MONITORING", bar, "", "CURRENT SLEEP STATUS", line,
           f"Date: {s['date'].date()}", f"Sleep Duration: {s['hours']:.1f} hours"]
    out.append(f"Sleep Quality: {s['quality']:.1f}%" if pd.notna(s["quality"]) else "Sleep Quality: Insufficient data")
    out += [f"Duration Status: {s['status']}", "", "SLEEP HISTORY SUMMARY", line,
            f"Recorded sleep sessions: {s['n']}",
            f"Overall average duration: {s['avg_duration']:.2f} hours",
            f"Overall average quality: {s['avg_quality']:.1f}%",
            f"7-session average duration: {s['duration_7']:.2f} hours",
            f"7-session average quality: {s['quality_7']:.1f}%",
            f"14-session average duration: {s['duration_14']:.2f} hours",
            f"14-session average quality: {s['quality_14']:.1f}%",
            "", "SLEEP RISK ASSESSMENT", line]
    if risks:
        for i, r in enumerate(risks, 1):
            out += ["", f"{i}. {r['name']}", f"   {r['detail']}"]
    else:
        out.append("No sleep-related risks detected in the available data.")
    out += ["", "SLEEP TRENDS", line]
    if s["trend"]:
        out.append(f"Sleep quality trend: {s['trend']}")
    out.append(f"Consecutive nights below 7 hours: {s['consecutive_low']}" if s["consecutive_low"] > 0
               else "No consecutive sleep-deficiency pattern.")
    out += ["", "RECENT SLEEP HISTORY", line]
    h = sleep[["date", "sleep_hours", "sleep_quality_pct"]].tail(14).copy()
    h["date"] = h["date"].dt.strftime("%Y-%m-%d")
    h = h.rename(columns={"date": "Date", "sleep_hours": "Hours Slept", "sleep_quality_pct": "Sleep Quality (%)"})
    out.append(h.to_string(index=False))
    return "\n".join(out)
