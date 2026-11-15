"""Adapter that combines every Risk Diagnostics source. No risk logic lives here; it only reads, merges and filters."""
import importlib
from collections import Counter

import pandas as pd
import streamlit as st

from core import data, sensor_diagnostics, sleep_diagnostics
from core.config import ALERT_LEVELS, NORMAL_LABELS, RISK_COLUMNS, RISK_CSV_HINT, RISK_FUNCTION, RISK_MODULE

STD = {"time": "timestamp", "category": "category", "indicator": "indicator", "parameter": "parameter",
       "result": "result", "classification": "classification", "support": "supporting_data", "action": "recommended_action"}
RANK = {"critical": 0, "warning": 1, "watch": 2, "neutral": 3, "info": 4}


def _standardize(df):
    """Rename whatever columns an external diagnostics source uses to the shared names; extra columns are kept."""
    ren = {}
    for role, hints in RISK_COLUMNS.items():
        c = data.find_col(df, hints)
        if c is not None and c not in ren:
            ren[c] = STD[role]
    return df.rename(columns=ren)


def _external_frame():
    try:  # another teammate module
        mod = importlib.import_module(RISK_MODULE)
        fn = getattr(mod, RISK_FUNCTION, None)
        if callable(fn):
            out = fn(data.frames())
            if isinstance(out, pd.DataFrame) and not out.empty:
                return _standardize(out), f"{RISK_MODULE}.{RISK_FUNCTION}"
    except ImportError:
        pass
    for stem, df in data.frames().items():  # or a risk csv
        if RISK_CSV_HINT in data.norm(stem) and not df.empty:
            return _standardize(df), f"{stem}.csv"
    return None, None


@st.cache_data(show_spinner=False)
def _build(sig):
    parts, sources = [], []
    sleep = data.sleep_scored()
    if sleep is not None:
        parts.append(sleep_diagnostics.risk_rows(sleep))
        sources.append("sleep diagnostics")
    sensor = sensor_diagnostics.run(data.frames(), skip_sleep=sleep is not None)
    if not sensor.empty:
        parts.append(sensor)
        sources.append("sensor diagnostics")
    ext, src = _external_frame()
    if ext is not None:
        parts.append(ext)
        sources.append(src)
    if not parts:
        return None
    df = pd.concat(parts, ignore_index=True)
    if "timestamp" in df:
        t = pd.to_datetime(df["timestamp"], errors="coerce")
        if t.notna().mean() >= 0.5:
            df["timestamp"] = t
    return dict(df=df, source=" + ".join(sources))


def load():
    """Combined Risk Diagnostics as dict(df, cols, source), or None."""
    built = _build(data.signature())
    if built is None:
        return None
    df = built["df"]
    cols = {role: data.find_col(df, hints) for role, hints in RISK_COLUMNS.items()}
    return dict(df=df, cols=cols, source=built["source"])


def level_of(row, cols):
    """critical / warning / watch / info / neutral. Uses the diagnostics' own level when given."""
    if "level" in row.index and pd.notna(row["level"]):
        return str(row["level"])
    c = cols["classification"]
    if c is None or pd.isna(row[c]):
        return "neutral"
    return "info" if str(row[c]).strip().lower() in NORMAL_LABELS else "warning"


def is_alert(row, cols):
    return level_of(row, cols) in ALERT_LEVELS


def alerts(risk):
    if not risk:
        return pd.DataFrame()
    df, cols = risk["df"], risk["cols"]
    if df.empty:
        return df
    out = df[df.apply(lambda r: is_alert(r, cols), axis=1)].copy()
    out["_rank"] = out.apply(lambda r: RANK.get(level_of(r, cols), 9), axis=1)
    return out.sort_values("_rank").drop(columns="_rank")


def summary_counts(risk):
    """Item 17: counts per status group, in the notebook's order."""
    df, cols = risk["df"], risk["cols"]
    cnt = Counter()
    for _, r in df.iterrows():
        label = r[cols["classification"]] if cols["classification"] else ""
        cnt[sensor_diagnostics.group_of(level_of(r, cols), label)] += 1
    return {g: cnt.get(g, 0) for g in sensor_diagnostics.SUMMARY_ORDER}


def critical_count(risk):
    df, cols = risk["df"], risk["cols"]
    return int(sum(level_of(r, cols) == "critical" for _, r in df.iterrows()))


def latest_time(risk):
    t = risk["cols"]["time"] if risk else None
    if not t or not pd.api.types.is_datetime64_any_dtype(risk["df"][t]):
        return None
    return risk["df"][t].max()


def overall(risk):
    """Overall classification only if the diagnostics provide one (a row/column named 'overall')."""
    if not risk:
        return None
    df, cols = risk["df"], risk["cols"]
    c = cols["classification"]
    for role in ("indicator", "category", "parameter"):
        col = cols[role]
        if col and c:
            hit = df[df[col].astype(str).str.contains("overall", case=False, na=False)]
            if not hit.empty:
                return str(hit.iloc[-1][c])
    return None


def related(risk, keywords):
    """Alerts whose category/parameter/indicator text mentions any keyword."""
    a = alerts(risk)
    if a.empty:
        return a
    cols = risk["cols"]
    use = [cols[r] for r in ("category", "parameter", "indicator") if cols[r]]
    if not use:
        return a.iloc[0:0]
    text = a[use].astype(str).agg(" ".join, axis=1).str.lower()
    return a[text.apply(lambda t: any(k in t for k in keywords))]


def status_for(risk, keys):
    """(classification text, level) of the newest assessment whose metric_key is in keys, else None."""
    if not risk or "metric_key" not in risk["df"].columns or not risk["cols"]["classification"]:
        return None
    df, cols = risk["df"], risk["cols"]
    hit = df[df["metric_key"].isin(keys)]
    if hit.empty:
        return None
    if cols["time"]:
        hit = hit.sort_values(cols["time"])
    row = hit.iloc[-1]
    return str(row[cols["classification"]]), level_of(row, cols)
