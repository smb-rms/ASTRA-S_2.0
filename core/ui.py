import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import data, risk
from core.config import METRICS, REFERENCE_LINES
from core.theme import plot_layout

KIND = {"live": "Live", "manual": "Manual entry", "calc": "Calculated", "base": "Baseline"}


def esc(x):
    return html.escape(str(x))


def title(text, sub=""):
    st.markdown(f'<div class="page-title">{esc(text)}</div><div class="page-sub">{esc(sub)}</div>', unsafe_allow_html=True)


def section(text, sub=""):
    small = f"<small>{esc(sub)}</small>" if sub else ""
    st.markdown(f'<div class="sec">{esc(text)}{small}</div>', unsafe_allow_html=True)


def empty(msg):
    st.markdown(f'<div class="empty">{esc(msg)}</div>', unsafe_allow_html=True)


def pill(text, cls=""):
    return f'<span class="pill {cls}">{esc(text)}</span>'


def card(label, value, unit="", ts=None, status=None, kind="live", delta=None):
    """value=None renders 'No Data'. status is shown only when supplied by the risk diagnostics."""
    nd = value is None
    val = f'<div class="val nd">{data.NO_DATA}</div>' if nd else f'<div class="val">{esc(value)}<span class="unit">{esc(unit)}</span></div>'
    stat = ""
    if status:
        text, level = status if isinstance(status, tuple) else (status, "info")
        cls = {"info": "ok", "critical": "alert", "warning": "alert", "watch": "manual"}.get(level, "")
        stat = f'<div style="margin-top:6px">{pill(text, cls)}</div>'
    dl = f'<div class="delta">{esc(delta)}</div>' if delta and not nd else ""
    tsl = f'<div class="ts">{esc(ts)}</div>' if ts and not nd else '<div class="ts">&nbsp;</div>'
    st.markdown(f'<div class="card"><div class="lab"><span>{esc(label)}</span>{pill(KIND[kind], kind)}</div>{val}{tsl}{dl}{stat}</div>', unsafe_allow_html=True)


def metric_card(key, status_keys=None, kind="live", show_delta=False):
    res = data.resolve(key)
    v, ts = data.latest(res)
    label = res["label"] if res else METRICS[key]["label"]
    unit = res["unit"] if res else ""
    delta = None
    if show_delta and v is not None:
        p = data.previous(res)
        if p is not None and not pd.isna(p):
            delta = f"Change since previous: {v - p:+,.2f}".rstrip("0").rstrip(".")
    status = risk.status_for(risk.load(), status_keys) if status_keys else None
    card(label, None if v is None else data.fmt(v), unit, ts, status, kind, delta)


def cards_row(keys, **kw):
    cols = st.columns(len(keys))
    for c, k in zip(cols, keys):
        with c:
            spec = k if isinstance(k, dict) else {"key": k}
            metric_card(spec["key"], spec.get("status"), kind=spec.get("kind", kw.get("kind", "live")), show_delta=kw.get("show_delta", False))


def trend(key, height=250, bar=False, color_idx=0):
    res = data.resolve(key)
    label = METRICS[key]["label"]
    if res is None or res["data"].empty:
        empty(f"{label}: No Data")
        return
    d = res["data"]
    unit = f" ({res['unit']})" if res["unit"] else ""
    fig = go.Figure()
    if bar:
        fig.add_bar(x=d["x"], y=d["y"], name=label)
    else:
        fig.add_scatter(x=d["x"], y=d["y"], mode="lines+markers" if len(d) < 60 else "lines", name=label, line=dict(width=2.2), marker=dict(size=5))
    for name, val in REFERENCE_LINES.get(key, []):
        fig.add_hline(y=val, line_dash="dash", line_width=1, line_color="rgba(224,96,122,.7)",
                      annotation_text=name, annotation_position="top left", annotation_font_size=10)
    plot_layout(fig, height, f"{label}{unit}")
    fig.update_xaxes(title=None if res["time_is_dt"] else "Mission time / index")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def trend_grid(keys, per_row=2, **kw):
    for i in range(0, len(keys), per_row):
        cols = st.columns(per_row)
        for c, k in zip(cols, keys[i:i + per_row]):
            with c:
                trend(k, **kw)


def alert_cards(df, risk_obj, limit=8):
    if df is None or df.empty:
        empty("No active alerts from Risk Diagnostics.")
        return
    cols = risk_obj["cols"]
    g = lambda r, role: (None if not cols[role] or pd.isna(r[cols[role]]) else r[cols[role]])
    for _, r in df.head(limit).iterrows():
        t = g(r, "time")
        t = t.strftime("%Y-%m-%d %H:%M") if hasattr(t, "strftime") else t
        head = g(r, "indicator") or g(r, "parameter") or "Alert"
        meta = " | ".join(f"{k}: {esc(v)}" for k, v in
                          [("Category", g(r, "category")), ("Time", t), ("Measurement", g(r, "parameter")), ("Result", g(r, "result"))] if v is not None)
        cls = g(r, "classification")
        act = g(r, "action")
        st.markdown(
            f'<div class="alert"><div class="t">{esc(head)} {pill(cls, "alert") if cls else ""}</div>'
            f'<div class="m">{meta}</div>' + (f'<div class="a">Suggested action: {esc(act)}</div>' if act else "") + "</div>",
            unsafe_allow_html=True)


def risk_cards(df, risk_obj):
    """Risk Category cards: assessment title, status, supporting data, recommended action, plus a collapsed detail block."""
    if df is None or df.empty:
        empty("Nothing to show.")
        return
    cols = risk_obj["cols"]
    g = lambda r, name: (None if name not in r.index or pd.isna(r[name]) else r[name])
    gr = lambda r, role: (None if not cols[role] or pd.isna(r[cols[role]]) else r[cols[role]])
    for _, r in df.iterrows():
        lvl = risk.level_of(r, cols)
        cls = {"critical": "alert", "warning": "alert", "watch": "manual", "info": "ok"}.get(lvl, "")
        label, sup, act = gr(r, "classification"), gr(r, "support"), gr(r, "action")
        more = "".join(f"<div class='a'><b>{lab}:</b> {esc(g(r, k))}</div>" for lab, k in
                       [("History", "history"), ("If the pattern continues", "sustained"), ("Reference", "reference"),
                        ("Data note", "caveat"), ("Source", "source")] if g(r, k))
        st.markdown(
            f'<div class="alert"><div class="t">{esc(gr(r, "indicator") or "Assessment")} {pill(label, cls) if label else ""}</div>'
            + (f'<div class="a"><b>Supporting data:</b> {esc(sup)}</div>' if sup else "")
            + (f'<div class="a"><b>Recommended action:</b> {esc(act)}</div>' if act
               else '<div class="a note">Recommended action: not provided yet.</div>')
            + (f"<details><summary>More detail</summary>{more}</details>" if more else "") + "</div>",
            unsafe_allow_html=True)


def history_table(keys, rows=200):
    """Merged table of the given metrics (one column each) for the history sections."""
    frames_ = []
    for k in keys:
        r = data.resolve(k)
        if r is None or r["data"].empty:
            continue
        unit = f" ({r['unit']})" if r["unit"] else ""
        t = r["data"].rename(columns={"y": f"{r['label']}{unit}"}).set_index("x")
        frames_.append(t[~t.index.duplicated(keep="last")])
    if not frames_:
        empty("No Data")
        return
    kind = pd.api.types.is_datetime64_any_dtype(frames_[0].index)   # keep only series on the same kind of time axis
    frames_ = [f for f in frames_ if pd.api.types.is_datetime64_any_dtype(f.index) == kind]
    t = pd.concat(frames_, axis=1).sort_index(ascending=False).reset_index().rename(columns={"x": "Time"})
    st.dataframe(t.head(rows), use_container_width=True, hide_index=True)


def missing_files_notice():
    if not data.frames():
        st.warning("No CSV files found in the data/ folder. Add the team's CSV files there and refresh. Nothing is shown until real data is available.")
    for name, err in data.load_errors().items():
        st.error(f"Could not read {name}: {err}")
