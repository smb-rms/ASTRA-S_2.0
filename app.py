import base64

import streamlit as st

from core.data import ROOT
from core.theme import inject_css
from views import (cabin_environment, crew_profile, crew_wellbeing, mission_control, nutrition_log,
                   radiation_watch, risk_assessment, sleep, vitals_activity)

st.set_page_config(page_title="ASTRA-S", page_icon="\U0001F6F0\uFE0F", layout="wide", initial_sidebar_state="expanded")
inject_css()

PAGES = {
    "Mission Control": mission_control,
    "Crew Profile": crew_profile,
    "Sleep": sleep,
    "Vitals & Activity": vitals_activity,
    "Radiation Watch": radiation_watch,
    "Crew Wellbeing": crew_wellbeing,
    "Cabin Environment": cabin_environment,
    "Nutrition Log": nutrition_log,
    "Risk Assessment": risk_assessment,
}

with st.sidebar:
    logo = ROOT / "images" / "astra_logo.png"
    img = (f'<img src="data:image/png;base64,{base64.b64encode(logo.read_bytes()).decode()}" '
           'style="height:54px;width:auto;border-radius:8px;">') if logo.exists() else ""
    st.markdown(f'<div class="brand">{img}<div><div class="brand-name">ASTRA-S</div>'
                '<div class="brand-sub">Astronaut Health and Mission Monitoring System</div></div></div>', unsafe_allow_html=True)
    page = st.radio("Navigation", list(PAGES), label_visibility="collapsed", key="page")

PAGES[page].render()
