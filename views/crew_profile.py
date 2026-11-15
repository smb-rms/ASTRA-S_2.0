import re

import pandas as pd
import streamlit as st

from core import data, sensor_diagnostics, ui, uploader

SLOTS = 3  # fixed number of astronaut profiles
PROFILE_WORDS = ("profile", "crew", "baseline")          # file names that hold profile / baseline data
NOT_PROFILE = ("sleep", "summary", "assessment", "analyzed", "input", "logs", "food", "survey", "risk")
SLOT_COLUMNS = {"astronaut", "crew_member", "member", "slot"}   # long format: which astronaut a row belongs to
KEY_FIELDS = ("astronaut_id", "id", "name", "astronaut_name", "full_name")
NAME_FIELDS = ("name", "astronaut_name", "full_name")
IDENTITY = ("astronaut_id", "id", "name", "astronaut_name", "full_name", "age", "role", "position", "mission", "mission_assignment")
MEDICAL = ("medical", "allergies", "allergy", "restrictions", "conditions")
GROUPS = ["Astronaut Information", "Individual Baseline Information", "Medical and Personal Reference Information"]
# <prefix>_baseline_mean / <prefix>_baseline_std columns -> label, unit
BASELINE_LABELS = {
    "hr_bpm": ("Heart rate", "bpm"), "hrv_ms": ("Heart rate variability", "ms"), "bp_sys": ("Systolic blood pressure", "mmHg"),
    "bp_dia": ("Diastolic blood pressure", "mmHg"), "spo2_pct": ("Blood oxygen (SpO\u2082)", "%"),
    "body_temp_c": ("Body temperature", "\u00b0C"), "cabin_co2_mmhg": ("Cabin CO\u2082", "mmHg"),
    "cabin_temp_c": ("Cabin temperature", "\u00b0C"), "cabin_o2_pct": ("Cabin oxygen", "%"),
    "radiation_msv": ("Radiation (column labelled mSv)", "mSv"), "sleep_hours": ("Sleep duration", "hours"),
    "glucose_mg_dl": ("Blood glucose", "mg/dL"), "bone_ca_mg_dl": ("Bone-calcium field", "mg/dL"),
}


def _profile_files():
    files = [(stem, df) for stem, df in data.frames().items()
             if any(w in data.norm(stem) for w in PROFILE_WORDS)
             and not any(w in data.norm(stem) for w in NOT_PROFILE) and not sensor_diagnostics.classify(df)]
    return sorted(files, key=lambda t: "baseline" in data.norm(t[0]))   # plain profile files first: they set the astronaut order


def _people_from(df):
    """Up to 3 astronauts from one file, each a list of (section, field, value).
    Wide file: one row per astronaut, one column per field. Long file: field,value[,section][,astronaut]."""
    fcol = data.find_col(df, ["field", "key", "parameter", "item"])
    vcol = data.find_col(df, ["value", "details", "info"])
    scol = data.find_col(df, ["section", "group"])
    acol = next((c for c in df.columns if data.norm(c) in SLOT_COLUMNS), None)
    if fcol and vcol:
        mk = lambda sub: [(r[scol] if scol else None, r[fcol], r[vcol]) for _, r in sub.iterrows() if not pd.isna(r[fcol])]
        if acol:
            return [mk(sub) for _, sub in df.groupby(acol, sort=False)][:SLOTS]
        return [mk(df)]
    return [[(None, c, row[c]) for c in df.columns] for _, row in df.head(SLOTS).iterrows()]


def _key_of(rows):
    """Who this row set describes: astronaut id if there is one, else name."""
    for want in KEY_FIELDS:
        for _, f, v in rows:
            if data.norm(f) == want and not pd.isna(v):
                return str(v).strip().lower()
    return None


def _astronauts():
    """Merge every profile/baseline file into 3 slots (matched by astronaut id or name, else by row order).
    A field already filled in is never overwritten by an empty value from another file."""
    slots, keys = [{} for _ in range(SLOTS)], [None] * SLOTS
    for stem, df in _profile_files():
        for i, rows in enumerate(_people_from(df)[:SLOTS]):
            k = _key_of(rows)
            idx = keys.index(k) if k and k in keys else i
            if k and keys[idx] is None:
                keys[idx] = k
            for sec, f, v in rows:
                nf = data.norm(f)
                if nf not in slots[idx] or (pd.isna(slots[idx][nf][2]) and not pd.isna(v)):
                    slots[idx][nf] = (sec, f, v)
    return [list(s.values()) for s in slots]


def _group_of(section, field):
    f = data.norm(field)
    if "baseline" in f:
        return GROUPS[1]
    if f in IDENTITY:
        return GROUPS[0]
    if any(k in f for k in MEDICAL):
        return GROUPS[2]
    if section:
        sec = data.norm(section)
        for g in GROUPS:
            if data.norm(g).split("_")[0] in sec:
                return g
    return GROUPS[0]


def _num(v, digits=2):
    try:
        return f"{float(v):,.{digits}f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(v)


def _baseline_rows(rows):
    """Pair <x>_baseline_mean with <x>_baseline_std into one line: 'Heart rate: 57.97 ± 2 bpm'."""
    vals = {data.norm(f): (f, v) for f, v in rows}
    out, used = [], set()
    for nf, (f, v) in vals.items():
        m = re.match(r"^(.*)_baseline_(mean|std)$", nf)
        if not m or nf in used:
            if not m:
                out.append((f, v))
            continue
        base = m.group(1)
        mean, sd = vals.get(f"{base}_baseline_mean"), vals.get(f"{base}_baseline_std")
        used |= {f"{base}_baseline_mean", f"{base}_baseline_std"}
        label, unit = BASELINE_LABELS.get(base, (base.replace("_", " ").title(), ""))
        text = "No Data" if mean is None or pd.isna(mean[1]) else _num(mean[1]) + (f" \u00b1 {_num(sd[1])}" if sd and not pd.isna(sd[1]) else "") + (f" {unit}" if unit else "")
        out.append((label, text))
    return out


def _show(rows):
    if not rows:
        ui.empty("No Data")
        return
    for field, value in rows:
        a, b = st.columns([1, 2])
        a.markdown(f'<span class="note">{ui.esc(str(field).replace("_", " ").title() if "_" in str(field) else field)}</span>', unsafe_allow_html=True)
        b.write(data.NO_DATA if pd.isna(value) else str(value))


def _field(rows, names):
    for _, f, v in rows:
        if data.norm(f) in names and not pd.isna(v):
            return str(v)
    return None


def _photo(name, aid, n):
    slugs = [f"astronaut_{n}"] + [re.sub(r"[^a-z0-9]+", "_", x.lower()).strip("_") for x in (aid, name) if x]
    for stem in slugs:
        for ext in ("png", "jpg", "jpeg", "webp"):
            p = data.ROOT / "images" / f"{stem}.{ext}"
            if p.exists():
                return p
    return None


def _photo_uploader(n):
    f = st.file_uploader("Upload profile picture", type=["png", "jpg", "jpeg", "webp"], key=f"photo_{n}")
    if f:
        ext = f.name.rsplit(".", 1)[-1].lower()
        folder = data.ROOT / "images"
        folder.mkdir(exist_ok=True)
        target = folder / f"astronaut_{n}.{ext}"
        if not target.exists() or target.read_bytes() != f.getvalue():
            for old in folder.glob(f"astronaut_{n}.*"):
                old.unlink()
            target.write_bytes(f.getvalue())
            st.rerun()
    st.caption(f"Saved as images/astronaut_{n}.{{png,jpg}}")


def render():
    ui.title("Crew Profile", "Personal and mission reference information for three astronauts. Baseline values are fixed references, not live readings.")
    uploader.baseline_uploader()
    people = _astronauts()
    if not any(people):
        st.info("No profile data yet. Use 'Upload baseline information' above.")
    names = [_field(p, NAME_FIELDS) or f"Astronaut {i + 1}" for i, p in enumerate(people)]

    for tab, rows, name, n in zip(st.tabs(names), people, names, range(1, SLOTS + 1)):
        with tab:
            grouped = {g: [] for g in GROUPS}
            for section, field, value in rows:
                grouped[_group_of(section, field)].append((field, value))
            left, right = st.columns([1, 3])
            with left:
                img = _photo(name, _field(rows, ("astronaut_id", "id")), n)
                if img:
                    st.image(str(img), use_container_width=True)
                else:
                    ui.empty("No profile image")
                _photo_uploader(n)
            with right:
                # expanders start closed on every visit and can be opened together
                with st.expander("Astronaut Information"):
                    _show(grouped[GROUPS[0]])
                with st.expander("Individual Baseline Information"):
                    st.markdown(ui.pill("Baseline reference (mean \u00b1 SD)", "base"), unsafe_allow_html=True)
                    _show(_baseline_rows(grouped[GROUPS[1]]))
                with st.expander("Medical and Personal Reference Information"):
                    st.caption("Shown only when provided and authorized.")
                    _show(grouped[GROUPS[2]])
