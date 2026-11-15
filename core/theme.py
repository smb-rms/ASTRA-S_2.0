import streamlit as st

NAVY = "#0a1128"
NAVY_2 = "#111a3a"
NAVY_3 = "#182450"
MAROON = "#5c1426"
MAROON_2 = "#8a2038"
ROSE = "#e0607a"
TEXT = "#e8ecf8"
MUTED = "#9aa5c8"
LINE = "rgba(150,165,215,.18)"
SERIES = ["#7ea6ff", "#e0607a", "#6fd3c0", "#f0b86e", "#b497ff"]

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Unbounded:wght@400;500;600&display=swap');
html, body, [class*="css"], .stApp {{ font-family: 'DM Sans', sans-serif; color: {TEXT}; }}
.stApp {{ background: radial-gradient(1200px 600px at 85% -10%, {MAROON}55, transparent 60%), {NAVY}; }}
header[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer {{ visibility: hidden; }}
.block-container {{ padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1500px; }}

/* sidebar stays visible */
[data-testid="stSidebarCollapseButton"], [data-testid="collapsedControl"] {{ display: none; }}
section[data-testid="stSidebar"] {{ background: linear-gradient({NAVY_2}, {NAVY}); border-right: 1px solid {LINE}; min-width: 270px !important; }}
section[data-testid="stSidebar"] .stRadio > div {{ gap: 2px; }}
section[data-testid="stSidebar"] .stRadio label {{ padding: 9px 12px; border-radius: 10px; width: 100%; border: 1px solid transparent; }}
section[data-testid="stSidebar"] .stRadio label:hover {{ background: {NAVY_3}; }}
section[data-testid="stSidebar"] .stRadio label[data-checked="true"],
section[data-testid="stSidebar"] .stRadio label:has(input:checked) {{ background: linear-gradient(90deg, {MAROON}, {NAVY_3}); border-color: {MAROON_2}; }}
section[data-testid="stSidebar"] .stRadio label > div:first-child {{ display: none; }}
section[data-testid="stSidebar"] .stRadio p {{ font-size: .95rem; font-weight: 500; }}

.brand {{ display: flex; align-items: center; gap: 12px; padding: 4px 4px 16px; margin-bottom: 8px; border-bottom: 1px solid {LINE}; }}
.brand-name {{ font-family: 'Unbounded', sans-serif; font-size: 1.15rem; font-weight: 600; letter-spacing: .04em; }}
.brand-sub {{ color: {MUTED}; font-size: .72rem; line-height: 1.25; margin-top: 3px; }}

h1, h2, h3 {{ font-family: 'Unbounded', sans-serif; letter-spacing: -.01em; }}
.page-title {{ font-family: 'Unbounded', sans-serif; font-size: 1.55rem; font-weight: 500; margin: 0; }}
.page-sub {{ color: {MUTED}; margin: .25rem 0 1rem; font-size: .95rem; }}
.sec {{ font-family: 'Unbounded', sans-serif; font-size: .95rem; font-weight: 500; margin: 1.6rem 0 .6rem; padding-left: 10px; border-left: 3px solid {ROSE}; }}
.sec small {{ display: block; font-family: 'DM Sans'; color: {MUTED}; font-weight: 400; font-size: .8rem; margin-top: 2px; }}

.hdr {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: stretch; margin-bottom: .4rem; }}
.hdr .box {{ flex: 1 1 180px; background: {NAVY_2}; border: 1px solid {LINE}; border-radius: 14px; padding: 12px 16px; }}
.hdr .box.main {{ flex: 2 1 320px; background: linear-gradient(120deg, {MAROON}, {NAVY_3}); border-color: {MAROON_2}; }}
.k {{ color: {MUTED}; font-size: .74rem; }}
.v {{ font-size: 1.02rem; font-weight: 600; margin-top: 2px; }}

.card {{ background: {NAVY_2}; border: 1px solid {LINE}; border-radius: 14px; padding: 14px 16px; height: 100%; }}
.card .lab {{ color: {MUTED}; font-size: .82rem; display: flex; justify-content: space-between; gap: 8px; }}
.card .val {{ font-family: 'Unbounded', sans-serif; font-size: 1.6rem; font-weight: 500; margin: 6px 0 2px; }}
.card .val.nd {{ font-size: 1.1rem; color: {MUTED}; padding: .5rem 0; }}
.card .unit {{ font-family: 'DM Sans'; font-size: .85rem; color: {MUTED}; margin-left: 5px; }}
.card .ts {{ color: {MUTED}; font-size: .74rem; }}
.card .delta {{ font-size: .78rem; color: {MUTED}; }}
.pill {{ display: inline-block; padding: 1px 9px; border-radius: 999px; font-size: .7rem; border: 1px solid {LINE}; color: {MUTED}; white-space: nowrap; }}
.pill.live {{ color: #7ea6ff; border-color: #7ea6ff66; }}
.pill.manual {{ color: #f0b86e; border-color: #f0b86e66; }}
.pill.calc {{ color: #b497ff; border-color: #b497ff66; }}
.pill.base {{ color: #6fd3c0; border-color: #6fd3c066; }}
.pill.alert {{ color: #ff9aae; border-color: {ROSE}99; background: {MAROON}66; }}
.pill.ok {{ color: #7be0b0; border-color: #7be0b066; }}

.alert {{ background: {NAVY_2}; border: 1px solid {LINE}; border-left: 4px solid {ROSE}; border-radius: 12px; padding: 12px 16px; margin-bottom: 10px; }}
.alert .t {{ font-weight: 600; }}
.alert .m {{ color: {MUTED}; font-size: .8rem; margin: 3px 0; }}
.alert .a {{ font-size: .86rem; margin-top: 4px; }}
.card .pill {{ white-space: normal; }}
.alert details {{ margin-top: 6px; }}
.alert summary {{ cursor: pointer; color: {MUTED}; font-size: .8rem; }}
.empty {{ border: 1px dashed {LINE}; border-radius: 12px; padding: 18px; color: {MUTED}; text-align: center; font-size: .9rem; }}
.note {{ color: {MUTED}; font-size: .8rem; }}

div[data-testid="stExpander"] {{ background: {NAVY_2}; border: 1px solid {LINE}; border-radius: 12px; }}
button[data-baseweb="tab"] {{ font-family: 'DM Sans'; }}
div[data-testid="stDataFrame"] {{ border: 1px solid {LINE}; border-radius: 12px; }}
.stButton > button, .stFormSubmitButton > button {{ background: {MAROON}; border: 1px solid {MAROON_2}; color: {TEXT}; border-radius: 10px; }}
.stButton > button:hover, .stFormSubmitButton > button:hover {{ background: {MAROON_2}; border-color: {ROSE}; color: white; }}
@media (max-width: 800px) {{ .card .val {{ font-size: 1.3rem; }} }}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def plot_layout(fig, height=260, title=None):
    fig.update_layout(
        height=height, title=dict(text=title, font=dict(size=13, color=TEXT), x=0.01) if title else None,
        margin=dict(l=10, r=10, t=38 if title else 10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(17,26,58,.55)",
        font=dict(family="DM Sans", color=TEXT, size=12), colorway=SERIES,
        legend=dict(orientation="h", y=-0.2), hovermode="x unified",
        xaxis=dict(gridcolor="rgba(150,165,215,.10)", zeroline=False),
        yaxis=dict(gridcolor="rgba(150,165,215,.10)", zeroline=False),
    )
    return fig
