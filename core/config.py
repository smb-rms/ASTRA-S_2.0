"""Edit this file when the real CSV headers differ from the guesses below.

Each metric lists column-name hints used to find it in ANY csv inside data/.
Hints are matched against normalised headers (lower-case, symbols -> '_').
Exact matches win; substring matches are only tried for hints of 4+ characters.
"unit" is only a fallback: a unit written in the header, e.g. "Dose Rate (uSv/h)", wins.
Nothing here is a medical threshold, and no values are invented.
"""

METRICS = {
    # ---- sleep & circadian
    "sleep_hours":       dict(label="Sleep Hours", hints=["sleep_hours", "sleep_duration", "sleep_hrs", "hours_slept"], unit="hours"),
    "sleep_quality":     dict(label="Sleep Quality", hints=["sleep_quality"], unit="%"),
    "sleep_efficiency":  dict(label="Sleep Efficiency", hints=["sleep_efficiency"], unit="%"),
    "sleep_latency":     dict(label="Sleep Latency", hints=["sleep_latency_min", "sleep_latency"], unit="min"),
    "waso":              dict(label="Wake After Sleep Onset", hints=["waso_min", "waso"], unit="min"),
    "fragmentation":     dict(label="Sleep Fragmentation", hints=["fragmentation_count", "fragmentation"], unit="count"),
    # ---- vitals
    "heart_rate":        dict(label="Heart Rate", hints=["heart_rate", "hr", "hr_bpm", "heart_rate_bpm", "bpm", "pulse"], unit="BPM", exclude=["variab", "hrv"]),
    "hrv":               dict(label="Heart Rate Variability", hints=["hrv", "heart_rate_variability", "rmssd"], unit="ms", loose=True, exclude=["sleep"]),
    "spo2":              dict(label="Blood Oxygen (SpO\u2082)", hints=["spo2", "blood_oxygen", "oxygen_saturation", "o2_saturation"], unit="%"),
    "body_temp":         dict(label="Body Temperature", hints=["body_temperature", "body_temp", "core_temp", "skin_temp"], unit="\u00b0C"),
    "bp_sys":            dict(label="Systolic BP", hints=["systolic", "bp_systolic", "bp_sys", "sbp"], unit="mmHg"),
    "bp_dia":            dict(label="Diastolic BP", hints=["diastolic", "bp_diastolic", "bp_dia", "dbp"], unit="mmHg"),
    "glucose":           dict(label="Blood Glucose", hints=["blood_glucose", "glucose", "blood_sugar"], unit="mg/dL"),
    # ---- activity
    "activity":          dict(label="Physical Activity", hints=["physical_activity", "activity", "steps"], unit="", exclude=["intensity", "duration"]),
    "exercise_duration": dict(label="Exercise Duration", hints=["exercise_duration", "workout_duration", "exercise_minutes"], unit="min"),
    "exercise_intensity":dict(label="Exercise Intensity", hints=["exercise_intensity", "workout_intensity", "intensity"], unit=""),
    "fatigue":           dict(label="Fatigue Level", hints=["fatigue_level", "fatigue"], unit=""),
    # ---- radiation
    "radiation_rate":    dict(label="Radiation Dose Rate", hints=["radiation_dose_rate", "dose_rate", "radiation_rate", "radiation_msv"], unit=""),
    "radiation_cum":     dict(label="Cumulative Radiation Dose", hints=["cumulative_radiation_dose", "cumulative_dose", "cumulative_radiation", "cum_dose"], unit=""),
    # ---- cabin
    "oxygen":            dict(label="Oxygen Availability", hints=["oxygen_availability", "cabin_oxygen", "cabin_o2", "o2_level", "oxygen"], unit="%", exclude=["spo2", "saturation", "blood"]),
    "cabin_co2":         dict(label="Cabin CO\u2082 Partial Pressure", hints=["cabin_co2_mmhg", "cabin_co2", "co2"], unit="mmHg", loose=True),
    "cabin_temp":        dict(label="Cabin Temperature", hints=["cabin_temperature", "cabin_temp"], unit="\u00b0C"),
}

# Header hints for the time axis, in priority order.
TIME_HINTS = ["timestamp", "datetime", "date_time", "recorded_at", "time", "date", "mission_day", "day"]

# Risk Diagnostics (teammate's work) ---------------------------------------
# Option 1: the teammate's python module, placed next to app.py.
#   The function receives {csv_stem: DataFrame} and must return a DataFrame.
RISK_MODULE = "risk_diagnostics"
RISK_FUNCTION = "run_diagnostics"
# Option 2 (fallback): any csv in data/ whose file name contains this text.
RISK_CSV_HINT = "risk"

RISK_COLUMNS = {
    "time":           ["timestamp", "datetime", "date_time", "assessed_at", "time", "date"],
    "category":       ["category", "risk_category", "domain", "system"],
    "indicator":      ["risk_indicator", "indicator", "risk", "alert", "title", "name"],
    "parameter":      ["related_parameter", "parameter", "metric", "measurement", "variable"],
    "result":         ["calculated_result", "result", "value", "score"],
    "classification": ["classification", "risk_level", "risk_status", "status", "level", "severity"],
    "support":        ["supporting_data", "support", "details", "notes", "evidence"],
    "action":         ["recommended_action", "suggested_action", "action", "recommendation"],
}

# Classification labels the team treats as "no alert". Anything else is shown as an alert.
# Replace with the team's own label list if it differs.
NORMAL_LABELS = {"normal", "ok", "okay", "nominal", "safe", "healthy", "low", "none", "green", "stable", "within range", "no risk detected"}

# Food database / meal log
FOOD_DB_HINTS = ["nutrition", "food", "meal"]
MEAL_LOG_FILE = "meal_log.csv"
FOOD_NAME_HINTS = ["food_name", "food", "item", "meal_name", "name"]
FOOD_CATEGORY_HINTS = ["meal_category", "meal_slot", "category", "type"]


# Crew Wellbeing survey (manual entry), scale 1 = worst, 10 = best
SURVEY_FILE = "wellbeing_survey.csv"
SURVEY_ITEMS = [("loneliness", "Loneliness"), ("mood", "Mood"), ("stress", "Stress"),
                ("confinement", "Confinement"), ("discomfort", "Discomfort"), ("mental_exhaustion", "Mental Exhaustion")]

# Wellbeing survey direction: True means 10 = best (as in the GUI survey). The notebook's strain rule
# ("score >= 7 is high strain") assumes higher = more strain, so scores are reversed (11 - score) before it is applied.
WELLBEING_HIGHER_IS_BETTER = True
STRAIN_HIGH_THRESHOLD = 7.0

# Risk levels that count as an alert (watch/warning/critical). info = within reference, neutral = data limitation.
ALERT_LEVELS = {"watch", "warning", "critical"}

# Reference lines drawn on the trend charts (values copied from the team's notebook). label, value.
REFERENCE_LINES = {
    "heart_rate": [("Resting lower reference 60 bpm", 60), ("Resting upper reference 100 bpm", 100)],
    "spo2": [("Normal lower bound 95%", 95), ("Below-usual boundary 93%", 93), ("Low saturation boundary 89%", 89)],
    "body_temp": [("Normal lower bound 36.1\u00b0C", 36.1), ("Slightly elevated 37.3\u00b0C", 37.3), ("High 38\u00b0C", 38), ("Very high 40\u00b0C", 40)],
    "bp_sys": [("Elevated 120", 120), ("Stage 1 130", 130), ("Stage 2 140", 140)],
    "bp_dia": [("Stage 1 80", 80), ("Stage 2 90", 90)],
    "glucose": [("Fasting lower reference 70", 70), ("Fasting elevated boundary 100", 100), ("Fasting high boundary 126", 126)],
    "sleep_hours": [("Lower reference 7 h", 7), ("Upper reference 9 h", 9)],
    "cabin_temp": [("Optimal lower bound 20\u00b0C", 20), ("Optimal upper bound 24\u00b0C", 24), ("Upper comfort 27\u00b0C", 27), ("Hazard 32\u00b0C", 32)],
    "cabin_co2": [("NASA nominal limit 3 mmHg (1-hour average)", 3.0)],
    "oxygen": [("Nominal composition 21%", 21.0)],
}
