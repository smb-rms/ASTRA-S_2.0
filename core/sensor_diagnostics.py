"""Sensor-based Risk Diagnostics (teammate's notebook items 1-17), ported to functions.

Thresholds, reference bands, wording and rules are copied from the notebook. What the notebook did not
show (daily_series, safe_median, the 24 h window, sample interval) is rebuilt below as small helpers.
Pure pandas/numpy: no Streamlit, no file access. Each item returns one row in the shared risk format.
"""
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from core.config import MEAL_LOG_FILE, STRAIN_HIGH_THRESHOLD, SURVEY_FILE, WELLBEING_HIGHER_IS_BETTER

CARDIO, SLEEP, RADIATION, BEHAV, ENV, NUTR = ("Cardiovascular & Physiological", "Sleep", "Radiation",
                                             "Behavioral & Isolation", "Environmental", "Nutrition")
NUMERIC = ["hr_bpm", "hrv_ms", "bp_sys", "bp_dia", "spo2_pct", "body_temp_c", "sleep_hours", "glucose_mg_dl",
           "bone_ca_mg_dl", "cabin_co2_mmhg", "cabin_temp_c", "cabin_o2_pct", "radiation_msv"]
SENSOR_SIGNATURE = {"timestamp", "activity_state", "gravity_level", "hr_bpm", "hrv_ms", "bp_sys", "bp_dia", "spo2_pct", "body_temp_c",
                    "cabin_co2_mmhg", "cabin_temp_c", "cabin_o2_pct", "radiation_msv"}
MOOD_SIGNATURE = {"timestamp", "loneliness", "mood", "stress", "confinement_discomfort", "mental_exhaustion"}
FOOD_SIGNATURE = {"timestamp", "meal_slot", "food_choice"}
MOOD_FIELDS = ["loneliness", "stress", "confinement_discomfort", "confinement", "discomfort", "mental_exhaustion"]
LIMITATIONS = [  # from the notebook's Overall Risk Summary
    "Glucose fasting status is not provided.",
    "Cabin pressure is missing, so inspired oxygen partial pressure cannot be confirmed.",
    "Radiation dose type / unit semantics are not defined.",
    "The bone-calcium field is not identified as a validated biomarker.",
    "Exercise intensity and food nutrient composition / portions are not provided.",
    "Only a short observation window is available; trends and correlations are not diagnoses.",
]


# ---------------------------------------------------------------- helpers
def safe_median(s):
    s = pd.Series(s).dropna()
    return float(s.median()) if len(s) else np.nan


def safe_mean(s):
    s = pd.Series(s).dropna()
    return float(s.mean()) if len(s) else np.nan


def fmt(v, d=1, suffix=""):
    return "Not available" if v is None or pd.isna(v) else f"{v:,.{d}f}{suffix}"

def daily_series(df, col, how):
    d = df.dropna(subset=[col])
    if d.empty:
        return pd.Series(dtype=float)
    out = getattr(d.groupby("date")[col], how)()
    out.index = pd.to_datetime(out.index)
    return out.sort_index()


class Ctx:
    pass


def classify(df):
    """Which kind of file this is, by column signature (file names do not matter)."""
    cols = {str(c).strip().lower() for c in df.columns}
    if SENSOR_SIGNATURE <= cols:
        return "Sensor / environment"
    if MOOD_SIGNATURE <= cols:
        return "Mood check-ins"
    if FOOD_SIGNATURE <= cols:
        return "Food log"
    if {"date", "sleep_hours"} <= cols:
        return "Sleep"
    return ""


def context(frames):
    """Prepared data for all items, or None when no sensor table is present."""
    raw = next((df for df in frames.values() if classify(df) == "Sensor / environment"), None)
    if raw is None:
        return None
    s = raw.copy()
    s.columns = [str(c).strip().lower() for c in s.columns]
    s["timestamp"] = pd.to_datetime(s["timestamp"], errors="coerce")
    s = s.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    if s.empty:
        return None
    for c in NUMERIC:  # optional columns missing from the file are treated as no data, as in the notebook
        s[c] = pd.to_numeric(s[c], errors="coerce") if c in s else np.nan
    s["activity_state"] = s["activity_state"].astype(str).str.strip().str.upper()
    s["gravity_level"] = s["gravity_level"].astype(str).str.strip().str.lower()
    s["date"] = s["timestamp"].dt.normalize()
    c = Ctx()
    c.sensor_df = s
    c.latest = s["timestamp"].max()
    c.last24 = c.latest - pd.Timedelta(hours=24)
    c.recent = s[s["timestamp"] >= c.last24].copy()
    gaps = s["timestamp"].diff().dt.total_seconds().div(60)
    valid = gaps[(gaps > 0) & (gaps <= 60)]
    c.interval = float(valid.median()) if not valid.empty else 5.0   # SAMPLE_INTERVAL_MIN
    c.mood = mood_table(frames)
    c.food = _food(frames)
    return c

def mood_table(frames):
    """Mood check-ins from every uploaded mood file (higher = more strain, as in the notebook) and from the GUI survey
    (1 = worst, 10 = best). Column 'src' tells them apart. Timestamps are parsed file by file because the files
    do not share one format (e.g. '2026-11-01 20:00:00' and '2026-11-15 03:07')."""
    parts = []
    sv = frames.get(Path(SURVEY_FILE).stem)
    sources = [(df, "mood_csv") for df in frames.values() if classify(df) == "Mood check-ins"]
    if sv is not None and len(sv):
        sources.append((sv, "survey"))
    for df, src in sources:
        d = df.copy()
        d.columns = [str(x).strip().lower() for x in d.columns]
        if "timestamp" not in d:
            continue
        d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
        d["src"] = src
        parts.append(d.dropna(subset=["timestamp"]))
    if not parts:
        return None
    m = pd.concat(parts, ignore_index=True).sort_values("timestamp", kind="stable").reset_index(drop=True)
    for f in MOOD_FIELDS + ["mood"]:
        if f in m:
            m[f] = pd.to_numeric(m[f], errors="coerce")
    m["date"] = m["timestamp"].dt.normalize()
    return m if len(m) else None

def food_tables(frames):
    """Every food log (all astronauts) as one table with astronaut_id, timestamp, meal_slot, food_choice, date."""
    parts = []
    for df in frames.values():
        if classify(df) == "Food log":
            f = df.copy()
            f.columns = [str(x).strip().lower() for x in f.columns]
            f["timestamp"] = pd.to_datetime(f["timestamp"], errors="coerce")
            parts.append(f.dropna(subset=["timestamp"]))
    if not parts:
        df = frames.get(Path(MEAL_LOG_FILE).stem)  # the Nutrition Log page's own file
        if df is not None and len(df) and {"timestamp", "food"} <= set(df.columns):
            f = df.rename(columns={"food": "food_choice"}).copy()
            f["timestamp"] = pd.to_datetime(f["timestamp"], errors="coerce")
            parts.append(f.dropna(subset=["timestamp"]))
    if not parts:
        return None
    f = pd.concat(parts, ignore_index=True).sort_values("timestamp", kind="stable").reset_index(drop=True)
    f["date"] = f["timestamp"].dt.normalize()
    return f if len(f) else None


def _food(frames):
    return food_tables(frames)

def _has(c, *cols):
    return all(x in c.sensor_df.columns and c.sensor_df[x].notna().any() for x in cols)


def _row(c, key, category, title, param, value, status, details, reference, caveat, level, label,
         history, sustained, action, source):
    return dict(timestamp=c.latest, metric_key=key, category=category, indicator=title, parameter=param, result=value,
                classification=label, level=level, supporting_data=f"{status} {details}".strip(),
                recommended_action=action, history=history, sustained=sustained, reference=reference,
                caveat=caveat, source=source)


def _no_recent(c, key, category, title, param, what, source):
    return _row(c, key, category, title, param, "No Data", f"No {what} in the latest 24-hour window.", "", "", "",
                "neutral", "DATA LIMITATION — NO RECENT READINGS", "", "", "Check that the sensor is recording.", source)


# ---------------------------------------------------------------- items
def item_hr(c):
    s = c.sensor_df
    rest_hr = s[s["activity_state"] == "REST"]
    recent_rest_hr = c.recent[c.recent["activity_state"] == "REST"]
    rest_median_24h = safe_median(recent_rest_hr["hr_bpm"])
    rest_median_all = safe_median(rest_hr["hr_bpm"])
    rest_high_count = int((rest_hr["hr_bpm"] > 100).sum())
    rest_low_count = int((rest_hr["hr_bpm"] < 60).sum())
    recent_high_count = int((recent_rest_hr["hr_bpm"] > 100).sum())
    recent_low_count = int((recent_rest_hr["hr_bpm"] < 60).sum())
    if pd.isna(rest_median_24h):
        return _no_recent(c, "heart_rate", CARDIO, "Heart Rate (HR)", "hr_bpm", "resting heart-rate readings", "Supplied Risk Assessment, p. 1.")
    if rest_median_24h > 100:
        lvl, label = "warning", "RISK — CURRENT RESTING MEDIAN ABOVE 100 BPM"
        status = "Current 24-hour resting median is above the supplied 100 bpm upper reference."
    elif recent_high_count:
        lvl, label = "watch", "MONITOR — HIGH RESTING READING IN THE LAST 24 HOURS"
        status = f"The 24-hour median is {rest_median_24h:.1f} bpm, but {recent_high_count} recent REST reading(s) exceeded 100 bpm."
    elif rest_high_count or rest_low_count:
        lvl, label = "watch", "WITHIN RANGE NOW — HISTORICAL READINGS TO REVIEW"
        status = f"The current 24-hour median is {rest_median_24h:.1f} bpm. No recent REST reading exceeded 100 bpm."
    else:
        lvl, label = "info", "OPTIMAL — CURRENT RESTING HEART RATE IN RANGE"
        status = f"The current 24-hour resting median is {rest_median_24h:.1f} bpm."
    return _row(c, "heart_rate", CARDIO, "Heart Rate (HR)", "hr_bpm", fmt(rest_median_24h, 1, " bpm"), status,
        f"Current 24-hour REST median: {fmt(rest_median_24h, 1, ' bpm')}. Recent readings above 100 bpm: {recent_high_count}. "
        f"Recent readings below 60 bpm: {recent_low_count}. Exercise-state readings are kept separate and are not treated as resting tachycardia.",
        "Supplied Risk Assessment, p. 1: resting HR 60–100 bpm. The current median is compared with that range.",
        "HR below 60 bpm is not automatically dangerous, especially during sleep or in physically fit people. "
        "A high HR during exercise is not interpreted as a resting abnormality.", lvl, label,
        f"Across the full {len(s):,}-record observation window, the REST median was {rest_median_all:.1f} bpm. "
        f"There were {rest_high_count} REST reading(s) above 100 bpm and {rest_low_count} below 60 bpm.",
        "Repeated resting readings above 100 bpm may indicate tachycardia and can be associated with palpitations, "
        "dizziness, fatigue, and reduced cardiovascular efficiency. Repeated low readings with symptoms may warrant review; "
        "the supplied reference does not define a number of days for this pattern.",
        "Repeat an unexpected reading after resting quietly and check sensor contact. If high resting HR repeats or occurs "
        "with dizziness, faintness, chest discomfort, or unusual fatigue, alert the crew medical team.",
        "Supplied Risk Assessment, p. 1.")


def item_hrv(c):
    s = c.sensor_df
    hrv_daily = daily_series(s, "hrv_ms", "median")
    hrv_baseline = safe_median(hrv_daily.iloc[:min(3, len(hrv_daily))])
    hrv_current = safe_median(c.recent["hrv_ms"])
    hrv_all_median = safe_median(s["hrv_ms"])
    if pd.isna(hrv_current) or pd.isna(hrv_baseline) or hrv_baseline <= 0:
        return _no_recent(c, "hrv", CARDIO, "Heart Rate Variability (HRV)", "hrv_ms", "HRV readings or baseline", "Supplied Risk Assessment, p. 2.")
    hrv_change_pct = ((hrv_current / hrv_baseline) - 1) * 100
    if hrv_change_pct <= -20:
        lvl, label = "warning", "RISK — HRV SUBSTANTIALLY BELOW PERSONAL BASELINE"
        status = f"Current 24-hour median is {abs(hrv_change_pct):.1f}% below the personal baseline."
    elif hrv_change_pct >= 20:
        lvl, label = "watch", "MONITOR — HRV UNUSUALLY HIGH VS BASELINE"
        status = f"Current 24-hour median is {hrv_change_pct:.1f}% above baseline; higher is not automatically better."
    else:
        lvl, label = "info", "WITHIN PERSONAL BASELINE"
        status = f"Current 24-hour median is {fmt(hrv_current, 1, ' ms')}, near the personal baseline."
    return _row(c, "hrv", CARDIO, "Heart Rate Variability (HRV)", "hrv_ms", fmt(hrv_current, 1, " ms"), status,
        f"Current 24-hour median: {fmt(hrv_current, 1, ' ms')}; first-three-day personal baseline: "
        f"{fmt(hrv_baseline, 1, ' ms')}; change: {fmt(hrv_change_pct, 1, '%')}.",
        "Supplied Risk Assessment, p. 2: no universally accepted normal HRV range; compare with the individual's own baseline.",
        "The ±20% alert boundary is a monitoring heuristic for this notebook, not a clinical cutoff.", lvl, label,
        f"Full-record median: {fmt(hrv_all_median, 1, ' ms')}. Daily medians show whether HRV is stable, rising, or falling over the observation window.",
        "A sustained drop below personal baseline may accompany stress, fatigue, or illness. The supplied reference does not specify "
        "a fixed number of days or a universal HRV value that predicts a disease.",
        "Check measurement quality and compare the HRV trend with sleep, workload, recovery, and reported symptoms. "
        "If the decline persists, review it with the crew medical team.", "Supplied Risk Assessment, p. 2.")


def bp_category(systolic, diastolic):
    if pd.isna(systolic) or pd.isna(diastolic):
        return "Unavailable"
    if systolic > 180 or diastolic > 120:
        return "Severe"
    if systolic >= 140 or diastolic >= 90:
        return "Stage 2"
    if systolic >= 130 or diastolic >= 80:
        return "Stage 1"
    if 120 <= systolic <= 129 and diastolic < 80:
        return "Elevated"
    return "Normal"


def item_bp(c):
    s = c.sensor_df
    rest_bp = s[s["activity_state"] == "REST"].copy()
    recent_bp = c.recent[c.recent["activity_state"] == "REST"].copy()
    sys_c, dia_c = safe_median(recent_bp["bp_sys"]), safe_median(recent_bp["bp_dia"])
    cat = bp_category(sys_c, dia_c)
    if cat == "Unavailable":
        return _no_recent(c, "bp", CARDIO, "Blood Pressure (REST-state readings)", "bp_sys / bp_dia", "resting blood-pressure readings", "American Heart Association: Understanding Blood Pressure Readings.")
    rest_bp["bp_category"] = rest_bp.apply(lambda r: bp_category(r["bp_sys"], r["bp_dia"]), axis=1)
    recent_bp["bp_category"] = recent_bp.apply(lambda r: bp_category(r["bp_sys"], r["bp_dia"]), axis=1)
    non_normal = int(rest_bp["bp_category"].isin(["Elevated", "Stage 1", "Stage 2", "Severe"]).sum())
    stage2 = int(rest_bp["bp_category"].isin(["Stage 2", "Severe"]).sum())
    r_non_normal = int(recent_bp["bp_category"].isin(["Elevated", "Stage 1", "Stage 2", "Severe"]).sum())
    r_stage2 = int(recent_bp["bp_category"].isin(["Stage 2", "Severe"]).sum())
    if cat == "Severe":
        lvl, label, status = "critical", "URGENT — CURRENT RESTING MEDIAN IN SEVERE RANGE", "The current 24-hour REST median is in the severe range."
    elif cat == "Stage 2" or r_stage2:
        lvl, label, status = "warning", "RISK — STAGE 2 / SEVERE RESTING VALUES PRESENT", "The current median or recent REST readings include Stage 2 / severe values."
    elif cat in ("Stage 1", "Elevated") or r_non_normal:
        lvl, label = "watch", "MONITOR — ELEVATED RESTING READINGS"
        status = f"The current median is {sys_c:.1f}/{dia_c:.1f} mmHg ({cat}), with {r_non_normal} elevated recent reading(s)."
    elif non_normal:
        lvl, label = "watch", "NORMAL NOW — HISTORICAL ELEVATED READINGS"
        status = f"The current 24-hour median is {sys_c:.1f}/{dia_c:.1f} mmHg (Normal)."
    else:
        lvl, label, status = "info", "OPTIMAL — RESTING MEDIAN IN NORMAL RANGE", "The current resting median is in the normal category."
    return _row(c, "bp", CARDIO, "Blood Pressure (REST-state readings)", "bp_sys / bp_dia", f"{fmt(sys_c, 1)}/{fmt(dia_c, 1)} mmHg", status,
        f"Current 24-hour REST median: {sys_c:.1f}/{dia_c:.1f} mmHg ({cat}). Recent elevated-category readings: {r_non_normal}; recent Stage 2/severe readings: {r_stage2}.",
        "American Heart Association adult categories: normal <120 and <80; elevated 120–129 and <80; Stage 1 130–139 or 80–89; Stage 2 ≥140 or ≥90 mmHg.",
        "These categories are intended for careful resting measurements and repeated averages, not diagnosis from a single sensor sample. "
        "Exercise and recovery readings are excluded.", lvl, label,
        f"Across the full dataset, {non_normal} REST readings were above the normal category, including {stage2} in Stage 2/severe ranges. "
        f"Full-record REST median: {safe_median(rest_bp['bp_sys']):.1f}/{safe_median(rest_bp['bp_dia']):.1f} mmHg.",
        "If repeated resting averages remain in Stage 1 or Stage 2 ranges, ongoing high blood pressure may increase "
        "cardiovascular risk. The present median is normal; the repeated individual samples should be reviewed in context.",
        "Repeat measurements under consistent resting conditions, inspect the time pattern of elevated samples, and review "
        "persistent Stage 1/2 readings with the crew medical team.", "American Heart Association: Understanding Blood Pressure Readings.")


def item_spo2(c):
    s = c.sensor_df
    rec = c.recent["spo2_pct"].dropna()
    cur = safe_median(rec)
    if pd.isna(cur):
        return _no_recent(c, "spo2", CARDIO, "Blood Oxygen Saturation (SpO₂)", "spo2_pct", "SpO₂ readings", "Supplied Risk Assessment, p. 2.")
    mn = float(s["spo2_pct"].min())
    below95 = int((s["spo2_pct"] < 95).sum())
    b9394 = int(((s["spo2_pct"] >= 93) & (s["spo2_pct"] < 95)).sum())
    gap = int(((s["spo2_pct"] > 92) & (s["spo2_pct"] < 93)).sum())
    crit = int((s["spo2_pct"] <= 88).sum())
    rec_below95 = int((rec < 95).sum())
    if (rec <= 88).any():
        lvl, label, status = "critical", "URGENT — CURRENT SpO₂ AT OR BELOW 88%", "A critically low reading is present in the latest 24-hour window."
    elif (rec < 93).any():
        lvl, label, status = "warning", "RISK — CURRENT LOW SpO₂ READING", "At least one recent reading is below 93%; confirm promptly."
    elif rec_below95:
        lvl, label = "watch", "MONITOR — RECENT READINGS BELOW 95%"
        status = f"The current 24-hour median is {cur:.1f}%, with {rec_below95} recent reading(s) below 95%."
    elif below95:
        lvl, label = "watch", "OPTIMAL NOW — HISTORICAL BELOW-USUAL READINGS"
        status = f"The current 24-hour median is {cur:.1f}%; the latest 24-hour readings are at or above 95%."
    else:
        lvl, label, status = "info", "OPTIMAL — CURRENT SpO₂ IN REFERENCE RANGE", f"The current 24-hour median is {cur:.1f}%."
    return _row(c, "spo2", CARDIO, "Blood Oxygen Saturation (SpO₂)", "spo2_pct", fmt(cur, 1, "%"), status,
        f"Current 24-hour median: {cur:.1f}%. Recent readings below 95%: {rec_below95}. The latest readings are currently within the supplied 95–100% reference band.",
        "Supplied Risk Assessment, p. 2: 95–100% normal; 93–94% below usual; 89–92% low (hypoxemia); ≤88% critically low.",
        "Pulse-oximeter readings can be affected by sensor fit, motion, circulation, and measurement quality. "
        "The decimal values 92.x fall between the whole-number bands in the source table and are shown explicitly.", lvl, label,
        f"Across the full dataset, {below95} reading(s) were below 95%: {b9394} were in 93–under 95%, {gap} were between 92% and 93%, "
        f"and the minimum was {mn:.1f}%. Readings at/below 88%: {crit}.",
        "If low saturation persists in the 89–92% band, the supplied assessment identifies hypoxemia; "
        "≤88% is classified as critically low, with risk of impaired organ function and respiratory complications. The source does not specify a multi-day threshold.",
        "Check probe placement and signal quality, repeat unexpected low values, and compare with cabin oxygen/pressure data. "
        "Escalate persistent low or critically low readings through the mission medical protocol.",
        "Supplied Risk Assessment, p. 2; MedlinePlus, British Thoracic Society, and NASA hypoxia references listed there.")


def item_temp(c):
    s = c.sensor_df
    rec = c.recent["body_temp_c"].dropna()
    cur = safe_median(rec)
    if pd.isna(cur):
        return _no_recent(c, "body_temp", CARDIO, "Body Temperature", "body_temp_c", "body-temperature readings", "Supplied Risk Assessment, pp. 2–3.")
    rmax = float(rec.max())
    tmax = float(s["body_temp_c"].max())
    below35 = int((s["body_temp_c"] < 35).sum())
    slight = int(s["body_temp_c"].between(37.3, 37.9, inclusive="both").sum())
    fever = int(s["body_temp_c"].between(38, 39.9, inclusive="both").sum())
    very_high = int((s["body_temp_c"] >= 40).sum())
    rec_fever = int((rec >= 38).sum())
    if rmax >= 40 or (rec < 35).any():
        lvl, label, status = "critical", "URGENT — EXTREME CURRENT TEMPERATURE", "The latest 24-hour window contains an extreme temperature reading."
    elif rec_fever:
        lvl, label, status = "warning", "RISK — CURRENT FEVER-RANGE READINGS", f"{rec_fever} recent reading(s) were at or above 38°C."
    elif fever:
        lvl, label = "watch", "NORMAL NOW — HISTORICAL FEVER-RANGE READINGS"
        status = f"The current 24-hour median is {cur:.2f}°C, but fever-range readings occurred earlier."
    elif slight:
        lvl, label, status = "watch", "MONITOR — SLIGHTLY ELEVATED HISTORICAL READINGS", f"The current 24-hour median is {cur:.2f}°C."
    else:
        lvl, label, status = "info", "OPTIMAL — CURRENT TEMPERATURE IN REFERENCE RANGE", f"The current 24-hour median is {cur:.2f}°C."
    return _row(c, "body_temp", CARDIO, "Body Temperature", "body_temp_c", fmt(cur, 2, " °C"), status,
        f"Current 24-hour median: {cur:.2f}°C; current 24-hour maximum: {rmax:.2f}°C. Recent readings ≥38°C: {rec_fever}.",
        "Supplied Risk Assessment, pp. 2–3: 36.1–37.2°C normal; 37.3–37.9°C slightly elevated; 38.0–39.9°C high; ≥40°C very high; <35°C very low.",
        "Temperature varies with measurement site, time, and activity. The card separates current readings from earlier fever-range readings.", lvl, label,
        f"Across the full record, {fever} readings were between 38.0–39.9°C; maximum was {tmax:.2f}°C. Readings ≥40°C: {very_high}; readings <35°C: {below35}.",
        "Repeated 38–39.9°C readings may reflect fever associated with infection or dehydration. "
        "The supplied assessment identifies ≥40°C as very high, with possible heatstroke, severe infection, sepsis, "
        "neurological complications, and organ damage. No fixed duration threshold is supplied.",
        "Because fever-range readings occurred in the historical record, review the dated trend with the crew medical team "
        "even though the latest 24-hour median is normal. Confirm sensor quality and repeat if temperature rises again.",
        "Supplied Risk Assessment, pp. 2–3; MedlinePlus, NHS, and CDC references listed there.")


def item_sleep(c):
    s = c.sensor_df
    data_ = s.dropna(subset=["sleep_hours"])
    daily = daily_series(data_, "sleep_hours", "mean")
    latest_h = float(daily.iloc[-1]) if not daily.empty else np.nan
    latest_d = daily.index[-1] if not daily.empty else None
    mean7 = safe_mean(daily.tail(7))
    below7 = int((daily < 7).sum())
    above9 = int((daily > 9).sum())
    consec = 0
    for h in reversed(daily.tolist()):
        if h < 7:
            consec += 1
        else:
            break
    low = daily[daily < 7]
    low_min = float(low.min()) if not low.empty else np.nan
    if daily.empty:
        lvl, label, status, current = "neutral", "DATA LIMITATION — NO VALID SLEEP RECORDS", "No valid sleep-duration records were found.", "Not available"
    else:
        current = f"{latest_h:.2f} hours on {latest_d.strftime('%Y-%m-%d')}"
        if latest_h < 7 or mean7 < 7:
            lvl, label = "warning", "RISK — CURRENT / WEEKLY SLEEP BELOW 7 HOURS"
            status = f"Latest sleep was {latest_h:.2f} h; 7-record mean is {mean7:.2f} h."
        elif below7:
            lvl, label = "watch", "OPTIMAL NOW — ONE OR MORE SHORT-SLEEP DAYS IN HISTORY"
            status = f"Latest sleep was {latest_h:.2f} h; the latest 7-record mean is {mean7:.2f} h."
        elif latest_h > 9:
            lvl, label, status = "watch", "MONITOR — SLEEP ABOVE 9 HOURS", f"Latest sleep was {latest_h:.2f} h."
        else:
            lvl, label = "info", "OPTIMAL — CURRENT SLEEP WITHIN 7–9 HOURS"
            status = f"Latest sleep was {latest_h:.2f} h; 7-record mean is {mean7:.2f} h."
    return _row(c, "sleep", SLEEP, "Sleep Duration", "sleep_hours", current, status,
        f"Latest sleep duration: {fmt(latest_h, 2)} hours. The supplied reference band is 7–9 hours. Latest 7-record average: {fmt(mean7, 2)} hours.",
        "Supplied Risk Assessment, p. 1: 7–9 hours is the stated reference band; <7 and >9 hours are associated with possible cardiovascular/metabolic risks.",
        "The sensor CSV supplies sleep_hours only. It does not include sleep efficiency, sleep latency, wake-after-sleep-onset, "
        "fragmentation, or sleep-onset clock time, so those Code Output Reference calculations cannot be reproduced from this CSV.", lvl, label,
        f"{below7} of {len(daily)} recorded nights were below 7 hours; shortest night was {fmt(low_min, 2, ' h')}. "
        f"Consecutive nights below 7 hours at the end of the record: {consec}. Nights above 9 hours: {above9}.",
        "A short night (<7 h) may impair alertness, attention, reaction time, and decision-making. If the 7-night average remains below 7 h, "
        "recurring weekly sleep deficiency is flagged. If sleep stays below 7 h for 14 consecutive nights, sustained sleep deficiency is flagged: "
        "sleep debt may accumulate and cognitive / operational performance may be impaired. Persistent short sleep is also associated with cardiovascular and metabolic risks.",
        "Protect a 7–9 hour sleep opportunity and monitor the next seven nights. If nights below 7 hours recur or the "
        "7-night average falls below 7 hours, review schedule, workload, and recovery with the crew medical / operations team.",
        "Code Output Reference, Part 1 — Sleep Monitoring; supplied Risk Assessment, p. 1.")


def item_glucose(c):
    s = c.sensor_df
    g = s.dropna(subset=["glucose_mg_dl"]).sort_values("timestamp")
    recent = c.recent["glucose_mg_dl"].dropna()
    if g.empty:
        cur, status, history = np.nan, "No valid blood-glucose observations were found.", "No historical comparison is available."
        label = "DATA LIMITATION — NO GLUCOSE RECORDS"
    else:
        cur = float(g.iloc[-1]["glucose_mg_dl"])
        when = g.iloc[-1]["timestamp"].strftime("%Y-%m-%d %H:%M")
        peak, low = float(g["glucose_mg_dl"].max()), float(g["glucose_mg_dl"].min())
        status = f"Latest valid sample: {cur:.1f} mg/dL ({when}). Fasting status is not recorded."
        label = "DATA LIMITATION — FASTING STATUS UNKNOWN"
        history = f"{len(g)} valid sample(s); range {low:.1f}–{peak:.1f} mg/dL. "
        if 100 <= peak <= 125:
            history += f"Peak {peak:.1f} mg/dL would fall in the supplied 100–125 mg/dL band only if it was a fasting sample."
        elif peak >= 126:
            history += f"Peak {peak:.1f} mg/dL would fall in the supplied ≥126 mg/dL band only if fasting."
        else:
            history += "Recorded values did not exceed 125 mg/dL."
    return _row(c, "glucose", CARDIO, "Blood Glucose", "glucose_mg_dl", fmt(cur, 1, " mg/dL"), status,
        f"Latest valid value: {fmt(cur, 1, ' mg/dL')}. Latest 24-hour median: {fmt(safe_median(recent), 1, ' mg/dL')}.",
        "Supplied Risk Assessment, pp. 6–7: fasting reference bands include 70–99 mg/dL normal, 100–125 slightly elevated, 126–199 high, 200–249 very high, and ≥250 extremely high.",
        "The CSV does not state whether readings were fasting. Do not classify a non-fasting sample using fasting thresholds.", "neutral", label, history,
        "If repeated confirmed fasting readings remain at 100–125 mg/dL, the supplied assessment identifies a prediabetes / "
        "insulin-resistance risk range. Repeated fasting readings ≥126 mg/dL warrant medical assessment for diabetes; this notebook does not diagnose either condition.",
        "Add a fasting / non-fasting indicator and time since last meal to the CSV. Confirm unexpected values using the "
        "mission-approved glucose protocol and review repeated fasting elevations with the crew medical team.", "Supplied Risk Assessment, pp. 6–7.")


def item_bone(c):
    b = c.sensor_df.dropna(subset=["bone_ca_mg_dl"]).sort_values("timestamp")
    if b.empty:
        cur, med, mx, mn, n_out = "Not available", np.nan, np.nan, np.nan, 0
    else:
        last = b.iloc[-1]
        cur = f"{last['bone_ca_mg_dl']:.1f} mg/dL on {last['timestamp'].date()}"
        med = float(b["bone_ca_mg_dl"].median())
        mn, mx = float(b["bone_ca_mg_dl"].min()), float(b["bone_ca_mg_dl"].max())
        mad = (b["bone_ca_mg_dl"] - med).abs().median()
        limit = med + (3 * 1.4826 * mad) if mad > 0 else np.inf
        n_out = len(b[b["bone_ca_mg_dl"] > limit])
    return _row(c, "bone", CARDIO, "Bone-Calcium Field (bone_ca_mg_dl)", "bone_ca_mg_dl", cur,
        "The latest valid value is displayed, but the field cannot be medically classified from its name alone.",
        f"Latest valid sample: {cur}. Statistical outlier count in this short series: {n_out}.",
        "No clinical threshold for this exact field is supplied. NASA discusses bone-mineral-density loss in microgravity, "
        "but this CSV field is not identified as bone mineral density or a validated bone-turnover biomarker.",
        "Do not interpret this column as serum calcium or bone mineral density without a sensor/data dictionary. "
        "The statistical outlier rule is not a medical threshold.", "neutral", "DATA LIMITATION — BIOMARKER DEFINITION REQUIRED",
        f"Observed median: {fmt(med, 1, ' mg/dL')}; range: {fmt(mn, 1)}–{fmt(mx, 1)} mg/dL. "
        "Any unusual value is flagged only relative to this dataset, not a clinical reference interval.",
        "No reliable health-risk projection can be made from this column until its biological meaning, unit, and sensor "
        "calibration are confirmed. Long-term reduced gravity is a separate bone-health risk described in the supplied assessment.",
        "Confirm the sensor/data dictionary, exact analyte, unit, calibration, and whether this is a blood, urine, or other "
        "measurement. Use a validated bone-density or bone-turnover measure for bone-health assessment.",
        "Supplied Risk Assessment, pp. 10–11; NASA spaceflight bone-health references cited there.")


def item_co2(c):
    s = c.sensor_df
    co2 = s.set_index("timestamp")["cabin_co2_mmhg"].dropna().sort_index()
    co2_1h = co2.rolling("60min", min_periods=8).mean()
    daily_max = co2_1h.resample("D").max()
    ok = co2_1h.dropna()
    latest = float(ok.iloc[-1]) if not ok.empty else np.nan
    mx = float(co2_1h.max()) if not ok.empty else np.nan
    rec = co2_1h[co2_1h.index >= c.last24].dropna()
    rec_max = float(rec.max()) if not rec.empty else np.nan
    n_win = int((co2_1h > 3.0).sum())
    n_days = int((daily_max > 3.0).sum())
    if pd.notna(latest) and latest > 3:
        lvl, label, status = "warning", "RISK — CURRENT 1-HOUR CO₂ AVERAGE ABOVE 3 mmHg", f"Latest 1-hour rolling average is {latest:.2f} mmHg."
    elif pd.notna(rec_max) and rec_max > 3:
        lvl, label = "warning", "RISK — RECENT 1-HOUR CO₂ EXCEEDANCE"
        status = f"Latest 1-hour average is {latest:.2f} mmHg, but a recent 1-hour window exceeded 3 mmHg."
    elif n_win:
        lvl, label = "watch", "WITHIN LIMIT NOW — HISTORICAL CO₂ EXCEEDANCES"
        status = f"Latest 1-hour average is {latest:.2f} mmHg; earlier windows exceeded the NASA nominal limit."
    elif pd.isna(latest):
        lvl, label, status = "neutral", "DATA LIMITATION — NOT ENOUGH CO₂ READINGS FOR A 1-HOUR AVERAGE", "A 1-hour average could not be calculated."
    else:
        lvl, label, status = "info", "OPTIMAL — 1-HOUR CO₂ AVERAGE WITHIN LIMIT", f"Latest 1-hour average is {latest:.2f} mmHg."
    return _row(c, "co2", ENV, "Cabin CO₂ Partial Pressure", "cabin_co2_mmhg", fmt(latest, 2, " mmHg") + " (latest 1-hour average)", status,
        f"Latest 1-hour average: {fmt(latest, 2, ' mmHg')}. Maximum 1-hour average in the latest 24 hours: {fmt(rec_max, 2, ' mmHg')}.",
        "NASA-STD-3001 Volume 2: nominal habitable-volume CO₂ partial pressure should average no more than 3 mmHg over one hour.",
        "Rolling 60-minute windows overlap; 35 windows do not necessarily represent 35 separate incidents. "
        "This is an engineering/environmental monitoring flag, not a medical diagnosis.", lvl, label,
        f"Across the full record, {n_win} rolling 1-hour windows exceeded 3 mmHg, across {n_days} day(s). Maximum 1-hour average: {fmt(mx, 2)} mmHg.",
        "A 1-hour average above 3 mmHg exceeds the NASA nominal cabin limit and warrants environmental-system review. "
        "The supplied standard defines an engineering limit; it does not provide a disease prediction based on a number of days.",
        "Review CO₂ scrubber / ventilation performance around the exceedance times, verify the CO₂ sensor, and continue "
        "checking the 1-hour average rather than relying only on the latest instantaneous sample.",
        "NASA-STD-3001, Volume 2, Revision F, cabin CO₂ requirements.")


def item_cabin_temp(c):
    s = c.sensor_df
    rec = c.recent["cabin_temp_c"].dropna()
    cur = safe_median(rec)
    if pd.isna(cur):
        return _no_recent(c, "cabin_temp", ENV, "Cabin Temperature", "cabin_temp_c", "cabin-temperature readings", "Supplied Risk Assessment, pp. 9–10.")
    rmax = float(rec.max())
    tmax = float(s["cabin_temp_c"].max())
    above27 = int((s["cabin_temp_c"] > 27).sum())
    hazard = int((s["cabin_temp_c"] >= 32).sum())
    rec_above27 = int((rec > 27).sum())
    if rmax >= 32:
        lvl, label, status = "critical", "URGENT — CURRENT CABIN TEMPERATURE AT HAZARD BOUNDARY", f"Recent maximum is {rmax:.2f}°C."
    elif rec_above27:
        lvl, label = "watch", "MONITOR — CURRENT TEMPERATURE ABOVE COMFORT BAND"
        status = f"Recent median is {cur:.2f}°C; {rec_above27} recent reading(s) exceeded 27°C."
    elif above27:
        lvl, label = "watch", "OPTIMAL NOW — HISTORICAL ABOVE-COMFORT EXCURSIONS"
        status = f"Current 24-hour median is {cur:.2f}°C, within the 20–24°C optimal target."
    else:
        lvl, label, status = "info", "OPTIMAL — CABIN TEMPERATURE IN COMFORT RANGE", f"Current 24-hour median is {cur:.2f}°C."
    return _row(c, "cabin_temp", ENV, "Cabin Temperature", "cabin_temp_c", fmt(cur, 2, " °C"), status,
        f"Current 24-hour median: {cur:.2f}°C; current 24-hour maximum: {rmax:.2f}°C. The supplied optimal target is 20–24°C.",
        "Supplied Risk Assessment, pp. 9–10: optimal target 20–24°C; upper comfort bound 25–27°C; ≥32°C hazardous/unhealthy.",
        "Comfort bands are not equivalent to immediate injury thresholds. Duration, humidity, airflow, clothing, and workload affect heat stress.", lvl, label,
        f"{above27} readings exceeded 27°C in the full record; historical maximum was {tmax:.2f}°C. Readings at or above 32°C: {hazard}.",
        "Sustained temperatures above the 25–27°C comfort band may cause discomfort. The supplied assessment identifies "
        "≥32°C as hazardous because heat dissipation is impaired, increasing heat-exhaustion risk and potentially heatstroke "
        "if core temperature rises. No multi-day duration threshold is provided.",
        "Maintain the 20–24°C target where operationally possible. Review HVAC / humidity / airflow logs around past excursions "
        "and escalate if the cabin approaches 32°C or crew develop heat-stress symptoms.",
        "Supplied Risk Assessment, pp. 9–10; NASA-STD-3001 and NASA OCHMO environmental-health references cited there.")


def item_o2(c):
    s = c.sensor_df
    cur = safe_median(c.recent["cabin_o2_pct"])
    if pd.isna(cur):
        return _no_recent(c, "cabin_o2", ENV, "Cabin Oxygen Availability", "cabin_o2_pct", "cabin-oxygen readings", "Supplied Risk Assessment, p. 8.")
    mn, mx = float(s["cabin_o2_pct"].min()), float(s["cabin_o2_pct"].max())
    pb = 760.0  # assumed: cabin pressure is not in the CSV
    pio2 = (pb - 47.0) * (cur / 100.0)
    return _row(c, "cabin_o2", ENV, "Cabin Oxygen Availability", "cabin_o2_pct", fmt(cur, 2, "% O₂"),
        "Current oxygen fraction is close to the 21% reference composition. "
        f"At an assumed 760 mmHg cabin pressure, illustrative PIO₂ would be {pio2:.1f} mmHg.",
        f"Current 24-hour median O₂ fraction: {cur:.2f}%. The supplied table's nominal atmosphere uses approximately 21% O₂.",
        "Supplied Risk Assessment, p. 8: normoxia target PIO₂ 145–155 mmHg, with 21% O₂ and 14.7 psia cabin pressure.",
        "The CSV has cabin_o2_pct but no total cabin pressure. The 760 mmHg calculation is illustrative only; actual PIO₂ cannot be confirmed.",
        "neutral", "NOMINAL O₂ FRACTION — INSPIRED O₂ PRESSURE NOT VERIFIED",
        f"Across the record, cabin O₂ fraction ranged from {mn:.2f}% to {mx:.2f}%.",
        "If actual inspired oxygen partial pressure falls to ≤122 mmHg (the supplied assessment's hypoxia lower boundary), "
        "subtle cognitive and physiological decrements may begin. If PIO₂ is above 160–200 mmHg for weeks/months, the "
        "assessment notes possible oxygen toxicity and lung-tissue damage. The CSV lacks pressure, so neither condition can be classified.",
        "Add total cabin pressure (psia, kPa, or mmHg) to the sensor export and calculate PIO₂ using measured pressure and oxygen fraction. "
        "Do not use oxygen percentage alone as proof of normoxia.", "Supplied Risk Assessment, p. 8; NASA-STD-3001 inspired-oxygen framework.")


def item_radiation(c):
    v = c.sensor_df["radiation_msv"].dropna()
    latest = float(v.iloc[-1]) if not v.empty else np.nan
    mn, mx = (float(v.min()), float(v.max())) if not v.empty else (np.nan, np.nan)
    med = safe_median(v)
    return _row(c, "radiation", RADIATION, "Radiation Reading", "radiation_msv", fmt(latest, 3, " (CSV column label: mSv)"),
        "The latest recorded value is shown, but a dose-risk category cannot be assigned yet.",
        f"Latest recorded value: {fmt(latest, 3)}. Full-record median: {fmt(med, 3)}.",
        "Supplied Risk Assessment, pp. 3–5: dose-rate bands use µSv/hour, while cumulative-dose bands and exposure limits use mSv.",
        "The column name radiation_msv does not establish whether values are instantaneous dose, dose rate, or cumulative dose. "
        "The notebook does not sum, convert, or compare it with exposure limits.", "neutral", "DATA LIMITATION — DOSE TYPE / UNIT MUST BE CONFIRMED",
        f"Recorded values range from {fmt(mn, 3)} to {fmt(mx, 3)}.",
        "If the confirmed cumulative effective dose becomes elevated, lifetime cancer risk may increase. Acute radiation "
        "syndrome is possible only when a sufficiently large absorbed dose is received over a short period. "
        "No valid projection can be made from this field until its measurement semantics are known.",
        "Confirm the sensor's exact unit, whether the value is a dose rate or accumulated dose, and the integration interval. "
        "Then compare the correctly interpreted value with the applicable mission and radiation-protection limits.",
        "Supplied Risk Assessment, pp. 3–5; NASA, CDC, IAEA, and UNSCEAR references listed there.")


def activity_by_day(c):
    """Daily minutes per activity state (REST/EXERCISE/RECOVERY) from the sensor sampling interval."""
    s = c.sensor_df
    out = s.groupby(["date", "activity_state"]).size().unstack(fill_value=0) * c.interval
    for st_ in ["EXERCISE", "RECOVERY", "REST"]:
        if st_ not in out.columns:
            out[st_] = 0
    return out


def item_activity(c):
    s = c.sensor_df
    ex = int((s["activity_state"] == "EXERCISE").sum())
    rc = int((s["activity_state"] == "RECOVERY").sum())
    ex_min, rc_min = ex * c.interval, rc * c.interval
    days = s["date"].nunique()
    return _row(c, "activity", CARDIO, "Physical Activity", "activity_state",
        f"{ex_min:.0f} min labeled EXERCISE over {days} day(s)",
        f"{ex_min:.0f} minutes were recorded in the EXERCISE state; this is a recorded activity duration, not a verified intensity-based exercise prescription.",
        f"EXERCISE-state time: {ex_min:.0f} min. RECOVERY-state time: {rc_min:.0f} min. Average EXERCISE-state time per day: {ex_min / max(days, 1):.1f} min.",
        "Supplied Risk Assessment, p. 6: 150–300 minutes/week moderate activity or 75–150 minutes/week vigorous activity.",
        "The CSV records EXERCISE / RECOVERY labels but not intensity. Therefore these minutes cannot be directly equated with moderate- or vigorous-intensity guideline minutes.",
        "neutral", "EXERCISE LOGGED — INTENSITY / RECOVERY ADEQUACY NOT VERIFIED",
        f"Total recorded EXERCISE time over the observation window: {ex_min:.0f} min.",
        "The supplied assessment links 0 minutes/week with higher risk of cardiovascular disease, obesity, type 2 diabetes, "
        "hypertension, and deconditioning. It also warns that excessive activity without adequate recovery can lead to "
        "overtraining, musculoskeletal injury, prolonged fatigue, and reduced performance. This dataset does not establish either condition.",
        "Record exercise intensity, resistance-training details, and recovery quality. Compare the time series with the astronaut's "
        "prescribed exercise / countermeasure plan rather than using total minutes alone.",
        "Supplied Risk Assessment, p. 6; CDC adult physical-activity guidance and NASA exercise overview cited there.")


def item_gravity(c):
    s = c.sensor_df
    gm = s.groupby("gravity_level").size() * c.interval
    text = "; ".join(f"{lvl}: {m / 60:.1f} h" for lvl, m in gm.items())
    reduced = [str(g) for g in gm.index if any(k in str(g).lower() for k in ("0g", "1/6", "0.16", "0.38"))]
    return _row(c, "gravity", CARDIO, "Gravity Exposure", "gravity_level", text,
        "Reduced-gravity exposure is present in the uploaded sensor record." if reduced else "No reduced-gravity label was detected.",
        f"Recorded exposure time by gravity label: {text}.",
        "Supplied Risk Assessment, pp. 10–13: microgravity and partial gravity may contribute to long-term bone and muscle deconditioning without countermeasures.",
        "Exposure time alone cannot estimate an individual's bone loss. The CSV does not include bone-density scans or a full countermeasure record.",
        "watch" if reduced else "info",
        "MONITOR — REDUCED-GRAVITY COUNTERMEASURES IMPORTANT" if reduced else "NO REDUCED-GRAVITY LABEL DETECTED",
        f"Total observation window: {s['date'].nunique()} day(s).",
        "If microgravity or partial-gravity exposure continues long term without effective countermeasures, the supplied assessment "
        "describes bone-mineral-density loss, muscle atrophy, cardiovascular deconditioning, and other adaptation effects. "
        "It does not provide a short fixed number of days after which these effects occur.",
        "Maintain the mission-prescribed resistance / aerobic exercise and bone-health countermeasures. Track exposure duration "
        "alongside validated bone and muscle-health measurements.", "Supplied Risk Assessment, pp. 10–13; NASA spaceflight bone-health references cited there.")


def item_mood(c):
    m = c.mood
    fields = [f for f in ["loneliness", "stress", "confinement_discomfort", "confinement", "discomfort", "mental_exhaustion"] if f in m and m[f].notna().any()]
    if not fields:
        return None
    # Notebook rule: score >= 7 on a "higher = more strain" scale. The uploaded mood CSV is used as is. The GUI survey is
    # 1 = worst, 10 = best, so its scores are reversed (11 - score) before the rule is applied.
    strain = m.copy()
    if WELLBEING_HIGHER_IS_BETTER:
        gui = strain["src"] == "survey"
        for f in fields:
            strain.loc[gui, f] = 11 - strain.loc[gui, f]
    th = STRAIN_HIGH_THRESHOLD
    high_counts = {f: int((strain[f] >= th).sum()) for f in fields}
    days = strain["date"].nunique()
    persistent = [f for f, n in high_counts.items() if n >= max(3, int(np.ceil(days * 0.5)))]
    latest = strain.sort_values("timestamp").iloc[-1]
    latest_raw = m.sort_values("timestamp").iloc[-1]
    latest_strain = {f: float(latest[f]) for f in fields if pd.notna(latest[f])}
    latest_high = [f for f, v in latest_strain.items() if v >= th]
    if persistent:
        lvl, label = "warning", "ATTENTION — REPEATED HIGH STRAIN SCORES"
        status = "Several self-reported strain dimensions were high on at least half of the available check-ins."
    elif latest_high:
        lvl, label, status = "watch", "MONITOR — HIGH SCORE IN LATEST CHECK-IN", "One or more strain scores are high in the latest check-in."
    else:
        lvl, label = "info", "NO REPEATED HIGH-STRAIN PATTERN BY HEURISTIC"
        status = "The current check-in does not meet the notebook's high-strain monitoring heuristic."
    scale = (f"Scores from the uploaded mood file count as strain when {th:.0f}/10 or higher; GUI survey answers (1 = worst, 10 = best) "
             f"count as strain when {11 - th:.0f} or lower." if WELLBEING_HIGHER_IS_BETTER
             else f"A score of {th:.0f}/10 or higher is the strain flag.")
    latest_text = ", ".join(f"{f.replace('_', ' ')} {latest_raw[f]:.0f}/10" for f in fields if pd.notna(latest_raw[f]))
    pers_text = ", ".join(f"{f.replace('_', ' ')} ({high_counts[f]}/{days})" for f in persistent) or "None met the repeated-score heuristic."
    return _row(c, "wellbeing", BEHAV, "Behavioral Wellbeing Check-ins", "wellbeing survey",
        f"Latest check-in: {latest['timestamp'].strftime('%Y-%m-%d %H:%M')}", status,
        f"Latest survey answers: {latest_text}. {scale} This is only a monitoring flag in this notebook.",
        "The supplied Risk Assessment does not provide numerical mood-score thresholds. NASA identifies behavioral health and performance as important to crew health and mission performance.",
        "The 7/10 strain threshold is a user-facing monitoring heuristic, not a clinical cutoff. The separate mood score is not used for the flag.", lvl, label,
        f"Repeated strain flags: {pers_text} Available check-in days: {days}.",
        "If high self-reported strain continues, it deserves a supportive wellbeing check-in and review by the appropriate "
        "crew-support team. These scores do not diagnose a mental-health condition, and the source does not specify a fixed duration threshold.",
        "Offer a private, non-judgmental check-in; review workload, sleep, isolation, and available support. "
        "Follow the mission's behavioral-health escalation pathway if the astronaut requests help or functioning is affected.",
        "NASA behavioral-health and performance framework; the supplied Risk Assessment does not set score thresholds.")


def item_food(c):
    f = c.food.copy()
    f["food_choice"] = f["food_choice"].astype(str).str.strip()
    counts = f["food_choice"].value_counts()
    unique, total = int(f["food_choice"].nunique()), len(f)
    last_date = f["date"].max()
    last_day = f[f["date"] == last_date]
    top, top_n = (counts.index[0], int(counts.iloc[0])) if not counts.empty else ("Not available", 0)
    return _row(c, "food", NUTR, "Food-Choice Variety", "food_choice", f"{unique} distinct dishes across {total} logged meals",
        "Food choices are recorded, but nutritional adequacy cannot be classified from names alone.",
        f"Latest logged day: {len(last_day)} meal(s). Distinct dishes on that day: {last_day['food_choice'].nunique()}.",
        "The supplied Risk Assessment and food CSV do not provide validated nutrition thresholds or nutrient values.",
        "Food names alone do not provide portion sizes, calories, protein, sodium, fiber, vitamins, minerals, or hydration information.",
        "neutral", "DATA LIMITATION — NUTRITIONAL RISK NOT CLASSIFIABLE",
        f"{total} meals were logged across {f['date'].nunique()} day(s), with {unique} distinct dishes. The most frequently logged dish was '{top}' ({top_n} meal(s)).",
        "No reliable deficiency or excess-risk projection can be made from food names alone. If a limited menu is sustained "
        "without adequate nutrient coverage, nutritional adequacy could become a concern, but this dataset cannot determine that.",
        "Add portion size and nutrient composition (energy, protein, fiber, sodium, vitamins, minerals, and fluid intake) "
        "or link the food log to the mission's approved nutrient database.", "Uploaded food log; no nutrient-composition dataset supplied.")


ITEMS = [  # (builder, required sensor columns)
    (item_hr, ["hr_bpm", "activity_state"]), (item_hrv, ["hrv_ms"]), (item_bp, ["bp_sys", "bp_dia", "activity_state"]),
    (item_spo2, ["spo2_pct"]), (item_temp, ["body_temp_c"]), (item_sleep, ["sleep_hours"]), (item_glucose, ["glucose_mg_dl"]),
    (item_bone, ["bone_ca_mg_dl"]), (item_co2, ["cabin_co2_mmhg"]), (item_cabin_temp, ["cabin_temp_c"]), (item_o2, ["cabin_o2_pct"]),
    (item_radiation, ["radiation_msv"]), (item_activity, ["activity_state"]), (item_gravity, ["gravity_level"]),
]


def _safe(fn, c):
    try:
        return fn(c)
    except Exception as exc:  # one broken item must not hide the others
        name = fn.__name__.replace("item_", "").replace("_", " ").title()
        return _row(c, fn.__name__.replace("item_", ""), CARDIO, name, "", "Not available", "This assessment could not be calculated.",
                    f"Error: {exc}", "", "", "neutral", "DATA LIMITATION — COULD NOT BE ASSESSED", "", "", "Check the data columns for this item.", "")


def run(frames, skip_sleep=False):
    """All assessments as a DataFrame in the shared risk format (empty when there is no sensor table).
    skip_sleep: the dedicated sleep diagnostics already cover sleep, so the sensor Sleep Duration card is left out."""
    c = context(frames)
    if c is None:
        return pd.DataFrame()
    rows = []
    for fn, _ in ITEMS:
        if fn is item_sleep and skip_sleep:
            continue
        r = _safe(fn, c)
        if r:
            rows.append(r)
    if c.mood is not None:
        r = _safe(item_mood, c)
        if r:
            rows.append(r)
    if c.food is not None and len(c.food):
        rows.append(_safe(item_food, c))
    return pd.DataFrame(rows)


def overview(frames):
    """Item 17 header facts, or None."""
    c = context(frames)
    if c is None:
        return None
    return dict(start=c.sensor_df["timestamp"].min(), end=c.latest, sensor=len(c.sensor_df),
                mood=0 if c.mood is None else len(c.mood), food=0 if c.food is None else len(c.food), interval=c.interval)


def gravity_hours(frames):
    c = context(frames)
    if c is None:
        return None
    return (c.sensor_df.groupby("gravity_level").size() * c.interval) / 60


def missing_columns(frames):
    raw = next((df for df in frames.values() if classify(df) == "Sensor / environment"), None)
    if raw is None:
        return None
    have = {str(x).strip().lower() for x in raw.columns}
    return [col for col in NUMERIC if col not in have]


def group_of(level, label):
    if str(label).startswith(("DATA LIMITATION", "NOMINAL O₂ FRACTION")):
        return "Data limitation"
    return {"critical": "Urgent", "warning": "Attention", "watch": "Monitor"}.get(level, "Optimal / within reference")


SUMMARY_ORDER = ["Urgent", "Attention", "Monitor", "Optimal / within reference", "Data limitation"]


def _spearman(a, b, min_periods=5):
    """Spearman rho on the rows where both series have values (ranks + Pearson), so scipy is not needed."""
    p = pd.concat([a, b], axis=1).dropna()
    if len(p) < min_periods:
        return np.nan
    r = p.rank()
    if r.iloc[:, 0].nunique() < 2 or r.iloc[:, 1].nunique() < 2:
        return np.nan
    return float(r.iloc[:, 0].corr(r.iloc[:, 1]))


def correlation(frames):
    """Item 16. Returns dict(corr, pairs, notes, n_days) or None."""
    c = context(frames)
    if c is None:
        return None
    s = c.sensor_df
    daily = pd.DataFrame(index=pd.DatetimeIndex(sorted(s["date"].unique())))
    rest = s[s["activity_state"] == "REST"] if "activity_state" in s else s.iloc[0:0]
    for col, name in [("hr_bpm", "Resting HR"), ("hrv_ms", "HRV"), ("bp_sys", "Resting SBP"), ("bp_dia", "Resting DBP"), ("spo2_pct", "SpO2"),
                      ("body_temp_c", "Body temperature"), ("cabin_co2_mmhg", "Cabin CO2"), ("cabin_temp_c", "Cabin temperature"),
                      ("cabin_o2_pct", "Cabin O2"), ("radiation_msv", "Radiation field")]:
        if col in s:
            src = rest if col in ["hr_bpm", "bp_sys", "bp_dia"] else s
            daily[name] = daily_series(src, col, "median").reindex(daily.index)
    for col, name in [("sleep_hours", "Sleep hours"), ("glucose_mg_dl", "Glucose"), ("bone_ca_mg_dl", "Bone-calcium field")]:
        if col in s:
            daily[name] = daily_series(s, col, "mean").reindex(daily.index)
    if c.mood is not None:
        md = c.mood.groupby("date")[[f for f in MOOD_FIELDS + ["mood"] if f in c.mood]].mean()
        for col, name in [("stress", "Stress"), ("loneliness", "Loneliness"), ("mental_exhaustion", "Mental exhaustion"),
                          ("confinement_discomfort", "Confinement discomfort"), ("confinement", "Confinement"),
                          ("discomfort", "Discomfort"), ("mood", "Mood score")]:
            if col in md:
                daily[name] = md[col].reindex(daily.index)
    names = list(daily.columns)
    corr = pd.DataFrame(np.nan, index=names, columns=names)
    for i, a in enumerate(names):
        for b in names[i:]:
            corr.loc[a, b] = corr.loc[b, a] = _spearman(daily[a], daily[b])
    valid = [x for x in corr.columns if corr[x].notna().sum() >= 2]
    corr = corr.loc[valid, valid]
    env = [x for x in ["Cabin CO2", "Cabin temperature", "Cabin O2"] if x in daily]
    health = [x for x in ["Resting HR", "HRV", "SpO2", "Body temperature", "Sleep hours", "Stress", "Loneliness", "Mental exhaustion",
                          "Confinement discomfort", "Confinement", "Discomfort", "Resting SBP", "Resting DBP"] if x in daily]
    pairs = []
    for e in env:
        for h in health:
            p = daily[[e, h]].dropna()
            if len(p) >= 5:
                rho = _spearman(daily[e], daily[h])
                if pd.notna(rho):
                    pairs.append((e, h, float(rho), len(p)))
    pairs.sort(key=lambda t: abs(t[2]), reverse=True)
    notable = [p for p in pairs if abs(p[2]) >= 0.60]
    notes = []
    for e, h, rho, n in notable[:8]:
        direction = "tended to rise together" if rho > 0 else "tended to move in opposite directions"
        notes.append(f"{e} ↔ {h}: {rho:+.2f} ({'strong' if abs(rho) >= 0.70 else 'moderate-to-strong'}, {n} paired days); values {direction}.")
    if not notable:
        notes.append("No environment–health pair reached the |Spearman ρ| ≥ 0.60 screening level with at least five paired days.")
    has = lambda e, hs: any(p[0] == e and p[1] in hs for p in notable)
    hints = []
    if has("Cabin temperature", ("Stress", "Mental exhaustion")):
        hints.append("Cabin temperature and self-reported strain moved together in this short record. Review thermal-control logs against the dates of higher stress / mental-exhaustion scores.")
    if has("Cabin CO2", ("Stress", "Mental exhaustion", "SpO2")):
        hints.append("Cabin CO₂ showed notable associations with stress / mental-exhaustion scores and/or SpO₂. Review CO₂ scrubber, ventilation, and sensor logs at matching timestamps; verify SpO₂ readings.")
    if has("Cabin O2", ("SpO2",)):
        hints.append("Cabin O₂ fraction and SpO₂ moved together. Interpret cautiously: cabin pressure is not in the CSV, so inspired O₂ partial pressure cannot be verified.")
    hints += ["These are screening clues, not proof that the environment caused a health change. Check timestamps, sensor calibration, activity, and sleep before taking action.",
              f"Only {len(daily)} daily observation(s) are available. Repeat the analysis on a longer time series before treating any association as stable.",
              "Radiation was left out of the written environment–health interpretation because the CSV does not define whether it is dose rate or cumulative dose."]
    return dict(corr=corr, pairs=pd.DataFrame(pairs, columns=["Environmental variable", "Health / wellbeing variable", "Spearman ρ", "Paired days (n)"]),
                notes=notes, hints=hints)
