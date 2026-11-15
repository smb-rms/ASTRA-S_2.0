"""CSV discovery and safe readers. Nothing here fabricates values."""
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from core.config import METRICS, TIME_HINTS

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
NO_DATA = "No Data"
SLEEP_KEYS = ("sleep_hours", "sleep_quality", "sleep_efficiency", "sleep_latency", "waso", "fragmentation")
NA_VALUES = ["", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan", "1.#IND", "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "n/a", "nan", "null"]


def norm(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


def _signature():
    DATA_DIR.mkdir(exist_ok=True)
    return tuple((p.name, p.stat().st_mtime_ns) for p in sorted(DATA_DIR.glob("*.csv")))


def astro_col(df):
    """Column that says which astronaut a row belongs to (astronaut_id, 'Astronaut ID', ...), or None."""
    return next((c for c in df.columns if norm(c) in ("astronaut_id", "astronaut", "crew_id")), None)


@st.cache_data(show_spinner=False)
def _read_all(sig):
    from core import sleep_diagnostics as sd
    frames, errors, sleep, mtimes, meta = {}, {}, {}, {}, {}
    for name, _ in sig:
        stem = Path(name).stem
        try:
            df = pd.read_csv(DATA_DIR / name, keep_default_na=False, na_values=NA_VALUES)  # "None" stays text (e.g. allergies: None)
            ac = astro_col(df)
            ids = sorted(df[ac].dropna().astype(str).unique()) if ac else []
            meta[stem] = dict(multi=len(ids) > 1, astro=ids[0] if ids else "")
            if sd.is_sleep_frame(df):  # adds sleep_quality_pct etc.; other columns stay untouched
                if len(ids) > 1:       # one person's nights only: a file with several astronauts is cut to the first id
                    df = df[df[ac].astype(str) == ids[0]].reset_index(drop=True)
                df, sleep[stem] = sd.score(df)
            frames[stem] = df
            mtimes[stem] = (DATA_DIR / name).stat().st_mtime_ns
        except Exception as exc:  # unreadable or empty file
            errors[name] = str(exc)
    return frames, errors, sleep, mtimes, meta


def frames():
    """{csv_stem: DataFrame}, re-read automatically when a file changes."""
    return _read_all(_signature())[0]


def load_errors():
    return _read_all(_signature())[1]


def mtimes():
    return _read_all(_signature())[3]


def meta():
    return _read_all(_signature())[4]


def sleep_source():
    """Stem of the sleep csv used by the sleep diagnostics, or None. Fixed rule (not 'whatever changed last'):
    single-astronaut files first, then the file with the most sleep columns, then the most rows, then the file name."""
    sl = {k: v for k, v in _read_all(_signature())[2].items() if not v.empty}
    if not sl:
        return None
    mm = meta()
    return min(sl, key=lambda k: (mm.get(k, {}).get("multi", False), -sum(c in sl[k].columns for c in sd_cols()), -len(sl[k]), k))


def sd_cols():
    from core import sleep_diagnostics as sd
    return sd.SLEEP_COLUMNS


def sleep_scored():
    """Scored sleep table from the newest sleep csv (teammate's sleep diagnostics), or None."""
    src = sleep_source()
    return _read_all(_signature())[2][src] if src else None


def signature():
    return _signature()


def detection_report():
    """[(measurement, 'file.csv -> column' or 'Not found', other files that also have it)]."""
    rows = []
    for key, spec in METRICS.items():
        r = resolve(key)
        rows.append((spec["label"], f"{r['file']}.csv -> {r['col']}" if r else "Not found",
                     ", ".join(f"{o}.csv" for o in r["others"]) if r else ""))
    return rows


def find_col(df, hints, exclude=(), loose=False):
    """Best matching column: exact normalised match first, then substring (hints of 4+ chars, or any length if loose)."""
    cols = {norm(c): c for c in df.columns}
    ex = [norm(e) for e in exclude]
    for h in hints:
        h = norm(h)
        if h in cols and not any(e in h for e in ex):
            return cols[h]
    for h in hints:
        h = norm(h)
        if len(h) < 4 and not loose:
            continue
        for n, c in cols.items():
            if h in n and not any(e in n for e in ex):
                return c
    return None


def time_axis(df):
    """Return (x Series, column name or None). Parsed datetimes when possible, else the raw column."""
    col = find_col(df, TIME_HINTS)
    if col is None:
        return pd.Series(range(len(df)), index=df.index), None
    raw = df[col]
    if pd.api.types.is_numeric_dtype(raw):
        return raw, col
    parsed = pd.to_datetime(raw, errors="coerce")
    if parsed.notna().mean() >= 0.5:
        return parsed, col
    return raw, col


def unit_from_header(header):
    m = re.search(r"[\(\[]([^)\]]+)[\)\]]\s*$", str(header))
    return m.group(1).strip() if m else ""


def resolve(key):
    """Locate a configured metric in the loaded CSVs. Returns a dict or None."""
    spec = METRICS[key]
    cands = []
    skip_files = ("profile", "baseline", "crew")                       # reference tables, not readings
    ex = tuple(spec.get("exclude", ())) + ("baseline", "_status")       # e.g. hr_bpm_baseline_mean, hr_bpm_status
    for stem, df in frames().items():
        if any(w in norm(stem) for w in skip_files):
            continue
        col = find_col(df, spec["hints"], ex, spec.get("loose", False))
        if col is not None:
            n = int(pd.to_numeric(df[col], errors="coerce").notna().sum())
            m = meta().get(stem, {})
            # fixed rule: single-astronaut files first, then the file with the most readings, then the lowest astronaut id,
            # then the file name (alphabetical). The same data always gives the same answer, whatever the file dates are.
            cands.append(((m.get("multi", False), -n, m.get("astro", "") or "~", stem), stem, df, col))
    if not cands:
        return None
    cands.sort(key=lambda c: c[0])
    if key in SLEEP_KEYS:   # sleep numbers must all come from the one sleep file the sleep diagnostics use
        src = sleep_source()
        cands = [c for c in cands if c[1] == src] + [c for c in cands if c[1] != src]
    _, stem, df, col = cands[0]
    others = [c[1] for c in cands[1:]]
    x, tcol = time_axis(df)
    y = pd.to_numeric(df[col], errors="coerce")
    data = pd.DataFrame({"x": x, "y": y}).dropna(subset=["y"])
    if pd.api.types.is_datetime64_any_dtype(data["x"]):
        data = data.dropna(subset=["x"]).sort_values("x")
    return dict(key=key, label=spec["label"], unit=unit_from_header(col) or spec["unit"],
                col=col, file=stem, others=others, data=data, time_is_dt=pd.api.types.is_datetime64_any_dtype(data["x"]))


def latest(res):
    """(value, timestamp text) of the newest valid reading, or (None, None)."""
    if not res or res["data"].empty:
        return None, None
    row = res["data"].iloc[-1]
    ts = row["x"]
    if hasattr(ts, "strftime"):
        ts = ts.strftime("%Y-%m-%d %H:%M")
    return row["y"], str(ts)


def previous(res):
    if not res or len(res["data"]) < 2:
        return None
    return res["data"].iloc[-2]["y"]


def fmt(v, digits=1):
    if v is None or pd.isna(v):
        return NO_DATA
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.{digits}f}"


def newest_timestamp():
    """Latest datetime found across all CSVs, for the 'last data update' label."""
    best = None
    for df in frames().values():
        x, col = time_axis(df)
        if col is not None and pd.api.types.is_datetime64_any_dtype(x) and x.notna().any():
            m = x.max()
            best = m if best is None or m > best else best
    return best


def oldest_timestamp():
    best = None
    for df in frames().values():
        x, col = time_axis(df)
        if col is not None and pd.api.types.is_datetime64_any_dtype(x) and x.notna().any():
            m = x.min()
            best = m if best is None or m < best else best
    return best
