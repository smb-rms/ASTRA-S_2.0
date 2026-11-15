"""Upload CSVs from the GUI into data/, so every page and Risk Diagnostics read the same files."""
import io
from pathlib import Path

import pandas as pd
import streamlit as st

from core import data, sensor_diagnostics


def _save(files, rename=None):
    changed = False
    for f in files:
        name = rename or Path(f.name).name
        content = f.getvalue()
        try:
            pd.read_csv(io.BytesIO(content), nrows=5)
        except Exception as exc:
            st.error(f"{f.name} is not a readable CSV: {exc}")
            continue
        target = data.DATA_DIR / name
        if not target.exists() or target.read_bytes() != content:
            data.DATA_DIR.mkdir(exist_ok=True)
            target.write_bytes(content)
            changed = True
    return changed


def data_manager():
    """Collapsed panel for Mission Control: upload any monitoring CSVs and see how they map to pages."""
    with st.expander("Upload data files"):
        st.caption("CSV files are saved to the data/ folder and used by every page and by Risk Diagnostics. "
                   "Uploading a file with the same name replaces it.")
        files = st.file_uploader("Monitoring CSV files", type="csv", accept_multiple_files=True, key="upload_main")
        if files and _save(files):
            st.rerun()
        loaded = data.frames()
        if loaded:
            st.dataframe(pd.DataFrame([{"File": f"{k}.csv", "Recognised as": sensor_diagnostics.classify(v) or "General data", "Rows": len(v), "Columns": len(v.columns)} for k, v in loaded.items()]),
                         use_container_width=True, hide_index=True)
            st.caption("Files are recognised by their columns, not their names: sensor/environment, mood check-ins, food log and sleep.")
            names = [f"{k}.csv" for k in loaded]
            c1, c2 = st.columns([3, 1])
            gone = c1.selectbox("Remove a file from data/", names, key="rm_file", label_visibility="collapsed")
            if c2.button("Remove file") and gone:
                (data.DATA_DIR / gone).unlink(missing_ok=True)
                st.rerun()
            st.caption("When several files contain the same measurement, the most recently uploaded file is used. Remove old sample files you no longer need.")
        with st.expander("How columns were matched"):
            st.dataframe(pd.DataFrame(data.detection_report(), columns=["Measurement", "Used from", "Also found in"]),
                         use_container_width=True, hide_index=True)
            st.caption("If a measurement says Not found, add your column name to its hints in core/config.py.")


def baseline_uploader():
    """Profile and baseline CSVs, saved into data/ under their own names."""
    with st.expander("Upload baseline information"):
        st.caption("Up to 3 astronauts, one row per astronaut and one column per field. Use two files if you like: "
                   "crew_profile.csv (name, id, role, mission, medical fields) and baseline.csv (name plus resting_heart_rate, "
                   "baseline_hrv, baseline_blood_oxygen, ...). A file with 'baseline' in its name is shown entirely as baseline data. "
                   "A field,value layout with an astronaut column also works.")
        fs = st.file_uploader("Profile / baseline CSV files", type="csv", accept_multiple_files=True, key="upload_baseline")
        if fs and _save(fs):
            st.rerun()
