from datetime import datetime

import pandas as pd
import streamlit as st

from core import data, sensor_diagnostics, ui
from core.config import FOOD_CATEGORY_HINTS, FOOD_DB_HINTS, FOOD_NAME_HINTS, MEAL_LOG_FILE

LOG_PATH = data.DATA_DIR / MEAL_LOG_FILE
EXCLUDE_STEMS = ("profile", "crew", "risk", "survey", "meal_log", "baseline", "sleep")


def _food_db():
    """(table, derived). A real food database file if there is one; otherwise every dish found in the food logs of all astronauts."""
    log_stem = LOG_PATH.stem
    for stem, df in data.frames().items():
        n = data.norm(stem)
        if stem == log_stem or sensor_diagnostics.classify(df) or any(x in n for x in EXCLUDE_STEMS):
            continue
        exact = any(data.norm(c) in ("food_name", "food", "item", "meal_name", "dish") for c in df.columns)
        if (any(h in n for h in FOOD_DB_HINTS) or exact) and data.find_col(df, FOOD_NAME_HINTS):
            return df, False
    logs = sensor_diagnostics.food_tables(data.frames())
    if logs is not None and "meal_slot" in logs:
        g = (logs.groupby("food_choice")
             .agg(meal_slot=("meal_slot", lambda x: x.mode().iat[0] if len(x.mode()) else ""),
                  times_logged=("food_choice", "size")).reset_index().sort_values(["meal_slot", "food_choice"]).reset_index(drop=True))
        return g, True
    return None, False


def _read_log():
    if LOG_PATH.exists():
        try:
            return pd.read_csv(LOG_PATH)
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def render():
    ui.title("Nutrition Log", "Record packed meals eaten during the mission. Nutrition values come from the food database.")
    db, derived = _food_db()
    if db is None:
        ui.empty("No food database found in data/ and no food log to build one from. Upload a food CSV from Mission Control.")
        _history(None)
        return
    name_c = data.find_col(db, FOOD_NAME_HINTS)
    cat_c = data.find_col(db, FOOD_CATEGORY_HINTS)

    ui.section("Meal Database")
    if derived:
        st.caption("No separate food database file was found, so this list is built from the dishes in the food logs "
                   "(category = meal slot). Nutrition values are not available. Upload a food database CSV to replace it.")
    cats = ["All"] + (sorted(db[cat_c].dropna().astype(str).unique()) if cat_c else [])
    f1, f2 = st.columns([1, 2])
    cat = f1.selectbox("Meal category", cats) if cat_c else "All"
    q = f2.text_input("Search food")
    view = db
    if cat != "All":
        view = view[view[cat_c].astype(str) == cat]
    if q:
        view = view[view[name_c].astype(str).str.contains(q, case=False, na=False)]
    st.dataframe(view, use_container_width=True, hide_index=True, height=260)

    ui.section("Log a Meal", "Entries are saved to data/" + MEAL_LOG_FILE + " as manual entries.")
    with st.form("meal_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
        food = c1.selectbox("Food item", view[name_c].dropna().astype(str).tolist() if not view.empty else [])
        qty = c2.number_input("Quantity", min_value=0.5, value=1.0, step=0.5)
        d = c3.date_input("Date", datetime.now().date())
        t = c4.time_input("Time", datetime.now().time().replace(second=0, microsecond=0))
        if st.form_submit_button("Save meal entry") and food:
            row = pd.DataFrame([{"timestamp": datetime.combine(d, t).strftime("%Y-%m-%d %H:%M"), "food": food, "quantity": qty}])
            row.to_csv(LOG_PATH, mode="a", header=not LOG_PATH.exists(), index=False)
            st.success(f"Saved: {food} x {qty:g}")

    _history(db, name_c, derived)


def _history(db, name_c=None, derived=False):
    ui.section("Nutrition History")
    gui = _read_log()
    uploaded = [v for v in data.frames().values() if sensor_diagnostics.classify(v) == "Food log"]
    parts = []
    if not gui.empty:
        g = gui.copy()
        g["timestamp"] = pd.to_datetime(g["timestamp"], errors="coerce")   # each source parsed on its own: formats differ
        parts.append(g.assign(source="Logged here"))
    for u in uploaded:
        u = u.rename(columns=lambda c: str(c).strip().lower()).rename(columns={"food_choice": "food"}).copy()
        u["timestamp"] = pd.to_datetime(u["timestamp"], errors="coerce")
        parts.append(u.assign(source="Uploaded food log"))
    if not parts:
        ui.empty("No meals logged yet.")
        return
    log = pd.concat(parts, ignore_index=True).dropna(subset=["timestamp"])
    if "astronaut_id" in log and log["astronaut_id"].notna().any():
        who = st.selectbox("Astronaut", ["All"] + sorted(log["astronaut_id"].dropna().astype(str).unique()), key="nutr_who")
        if who != "All":
            log = log[log["astronaut_id"].astype(str) == who]
    log = log.sort_values("timestamp", ascending=False)
    st.dataframe(log, use_container_width=True, hide_index=True, height=260)

    # Daily summary: numeric database columns multiplied by quantity logged (per-unit values from the database).
    if db is not None and not derived and "quantity" in log:
        num = [c for c in db.columns if c != name_c and pd.api.types.is_numeric_dtype(db[c])]
        mine = log.dropna(subset=["quantity"])
        if num and not mine.empty:
            m = mine.merge(db[[name_c] + num], left_on="food", right_on=name_c, how="left")
            for c in num:
                m[c] = m[c] * m["quantity"]
            m["Date"] = m["timestamp"].dt.date
            daily = m.groupby("Date")[num].sum(min_count=1).reset_index().sort_values("Date", ascending=False)
            st.markdown("**Daily summary** (database value x quantity logged)")
            st.dataframe(daily, use_container_width=True, hide_index=True)
