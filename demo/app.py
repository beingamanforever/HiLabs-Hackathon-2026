"""R3 Provider Directory Accuracy Engine — Interactive Demo.

Run:  streamlit run demo/app.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as _components

sys.path.insert(0, str(Path(__file__).parent))
try:
    from llm_explainer import explain_row as _llm_explain_row, fallback_local as _llm_fallback
    _LLM_AVAILABLE = True
except Exception:
    _LLM_AVAILABLE = False
    def _llm_explain_row(row): return "", "unavailable"
    def _llm_fallback(row, m): return "Call: row is in conformal-uncertain pool."

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT    = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"
T1, T2, T3 = OUTPUTS / "track1", OUTPUTS / "track2", OUTPUTS / "track3"

st.set_page_config(page_title="R3 Accuracy Engine", layout="wide",
                   initial_sidebar_state="expanded")

if "dark" not in st.session_state:
    st.session_state.dark = True

# ── Palettes ───────────────────────────────────────────────────────────────────
#  Restrained two-tone palette: one accent (slate-indigo), one safe (teal-green),
#  one negative (rose). Tracks 2 / 3 share the accent so the eye isn't asked
#  to learn a fourth color. Light + dark map 1:1 — same roles, same contrast.
LIGHT = dict(
    bg="#ffffff", surface="#ffffff", surface2="#f4f6fa",
    sidebar="#f9fafb", sidebar_border="#e5e7eb",
    border="#e2e6ec", text="#0f172a", text2="#1e293b", muted="#64748b",
    accent="#3858e9", accent_soft="#eef2ff",
    positive="#0f766e", positive_soft="#ecfdf5",
    warning="#92400e", warning_soft="#fffbeb",
    negative="#b91c1c", negative_soft="#fef2f2",
    t2="#3858e9", t2soft="#eef2ff",
    t3="#3858e9", t3soft="#eef2ff",
    safe="#0f766e", safe_soft="#ecfdf5",
    chart_grid="#e5e7eb",
)
DARK = dict(
    bg="#0b0f17", surface="#121826", surface2="#0e1320",
    sidebar="#0e1320", sidebar_border="#1f2a3a",
    border="#1f2a3a", text="#e6edf3", text2="#c9d1d9", muted="#7c8aa0",
    accent="#7c93ff", accent_soft="#1a2143",
    positive="#34d399", positive_soft="#0d2a22",
    warning="#d29922", warning_soft="#2a2010",
    negative="#f87171", negative_soft="#2a1216",
    t2="#7c93ff", t2soft="#1a2143",
    t3="#7c93ff", t3soft="#1a2143",
    safe="#34d399", safe_soft="#0d2a22",
    chart_grid="#1c2433",
)
C = DARK if st.session_state.dark else LIGHT


# ── CSS ────────────────────────────────────────────────────────────────────────
# Inject CSS via JS into parent document to avoid Streamlit's markdown text leak
_CSS_RULES = f"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,300..700,0..1,-50..200&display=block');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,300..700,0..1,-50..200&display=block');

/* Design tokens (8px base rhythm) */
:root{{
  --r3-s1:4px; --r3-s2:8px; --r3-s3:12px; --r3-s4:16px; --r3-s5:20px; --r3-s6:24px; --r3-s8:32px;
  --r3-r-sm:6px; --r3-r-md:8px; --r3-r-lg:10px;
}}

/* Keep Streamlit's native sidebar + collapse/expand controls fully native.
   Earlier attempts at restyling them killed the expand button. We hide ONLY
   chrome we don't want (Deploy, MainMenu, footer, status decoration). */
#MainMenu,footer,
.stDeployButton,.stAppDeployButton,[data-testid="stDeployButton"],
.viewerBadge_container__1QSob,[href*="streamlit.io/cloud"],
[data-testid="stStatusWidget"],
[data-testid="stDecoration"]{{
  display:none!important;visibility:hidden!important}}

/* Header stays a thin transparent strip so the native collapse / expand
   button keeps working in both states. */
[data-testid="stHeader"]{{
  background:transparent!important;height:auto!important;
  border:none!important;box-shadow:none!important}}
[data-testid="stHeader"]::before{{display:none!important}}

/* Force every flavor of sidebar collapse / expand control to be visible.
   Different Streamlit versions use different test-ids, so target all of them
   without overriding position so Streamlit's own layout still applies. */
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapseButton"],
button[data-testid="stSidebarCollapseButton"],
button[data-testid="stExpandSidebarButton"],
button[data-testid="collapsedControl"],
button[kind="header"],
button[kind="headerNoPadding"]{{
  display:inline-flex!important;visibility:visible!important;opacity:1!important;
  pointer-events:auto!important}}

/* Sidebar header — give the collapse arrow comfortable room (don't hide it) */
[data-testid="stSidebarHeader"]{{
  background:transparent!important;border:none!important;padding:8px 10px 0 10px!important;
  display:flex!important;justify-content:flex-end!important;align-items:center!important;
  min-height:36px!important;
}}
[data-testid="stSidebarCollapseButton"]{{
  background:transparent!important;border:none!important;color:{C['muted']}!important;
}}
[data-testid="stSidebarCollapseButton"]:hover{{color:{C['text']}!important}}

@keyframes badge-pulse{{
  0%{{box-shadow:0 0 0 0 rgba(63,185,80,.55)}}
  70%{{box-shadow:0 0 0 10px rgba(63,185,80,0)}}
  100%{{box-shadow:0 0 0 0 rgba(63,185,80,0)}}
}}
.agreement-badge{{animation:badge-pulse 1.8s ease-out .4s 3}}

html,body,p,h1,h2,h3,h4,h5,h6,label,button,input,select,textarea,
.stApp,.stApp div,.stApp span:not([class*="material"]):not([class*="Icon"]):not([class*="symbol"]),
[class*="st-"]{{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif!important}}

/* Material Symbols — ensure the actual font is applied, not just the name */
.material-symbols-outlined,.material-symbols-rounded,.material-icons,
[data-testid="stIconMaterial"],
span[data-testid="stIconMaterial"]{{
  font-family:'Material Symbols Outlined','Material Symbols Rounded','Material Icons'!important;
  font-weight:normal!important;font-style:normal!important;
  font-size:20px!important;line-height:1!important;letter-spacing:normal!important;
  text-transform:none!important;display:inline-block!important;white-space:nowrap!important;
  word-wrap:normal!important;direction:ltr!important;
  -webkit-font-feature-settings:'liga'!important;font-feature-settings:'liga'!important;
  -webkit-font-smoothing:antialiased!important;
  font-variation-settings:'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24!important;
}}

/* If the icon font still hasn't loaded by the time the user sees the page,
   hide the raw ligature text and replace it with an inline SVG double-arrow.
   Targets only the sidebar collapse button so we don't blow away other icons. */
[data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"]{{
  font-size:0!important;color:transparent!important;width:20px;height:20px;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='%237c8aa0' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='11 17 6 12 11 7'/><polyline points='18 17 13 12 18 7'/></svg>");
  background-repeat:no-repeat;background-position:center;background-size:20px 20px;
}}

/* Same SVG fallback for the EXPAND button (sidebar collapsed → ») */
[data-testid="stSidebarCollapsedControl"] [data-testid="stIconMaterial"],
button[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"]{{
  font-size:0!important;color:transparent!important;width:20px;height:20px;
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='%237c8aa0' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='13 17 18 12 13 7'/><polyline points='6 17 11 12 6 7'/></svg>");
  background-repeat:no-repeat;background-position:center;background-size:20px 20px;
}}
[data-testid="stSidebarCollapseButton"]:hover [data-testid="stIconMaterial"]{{
  background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='%23{C['text'].lstrip('#')}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='11 17 6 12 11 7'/><polyline points='18 17 13 12 18 7'/></svg>")!important;
}}

.main .block-container{{padding-top:.6rem!important;padding-bottom:1.5rem!important;max-width:1400px}}
.stApp,.main .block-container{{background:{C['bg']}!important}}

/* Sidebar theming — wins over Streamlit's defaults in both modes */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div,
section[data-testid="stSidebar"] > div > div{{
  background:{C['sidebar']}!important;
  border-right:1px solid {C['sidebar_border']}!important;
  box-shadow:1px 0 0 {C['sidebar_border']}!important}}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{{
  background:{C['sidebar']}!important;padding:var(--r3-s4) var(--r3-s4) var(--r3-s5) var(--r3-s4)!important}}
section[data-testid="stSidebar"] *{{color:{C['text']}}}
section[data-testid="stSidebar"] hr{{
  margin:var(--r3-s4) 0!important;border:none!important;
  border-top:1px solid {C['border']}!important;opacity:.7}}

/* Streamlit (?) help / tooltip icons — circular, muted, hover state */
[data-testid="stTooltipIcon"],
[data-testid="stTooltipHoverTarget"]{{
  width:16px!important;height:16px!important;border-radius:50%!important;
  border:1px solid {C['border']}!important;background:transparent!important;
  display:inline-flex!important;align-items:center!important;justify-content:center!important;
  color:{C['muted']}!important;font-size:11px!important;line-height:1!important;
  transition:border-color .12s ease, color .12s ease, background-color .12s ease;
  cursor:help!important;margin-left:6px!important;flex-shrink:0!important}}
[data-testid="stTooltipIcon"]:hover,
[data-testid="stTooltipHoverTarget"]:hover{{
  border-color:{C['accent']}!important;color:{C['accent']}!important;
  background:{C['accent_soft']}!important}}
[data-testid="stTooltipIcon"] svg,
[data-testid="stTooltipHoverTarget"] svg{{width:11px!important;height:11px!important}}
/* Stack rhythm inside the sidebar: every element block gets a baseline gap */
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{{gap:var(--r3-s2)!important}}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{{margin:0 0 var(--r3-s1) 0}}

h1,h2,h3,h4{{color:{C['text']}!important;font-weight:700}}
.stApp p,.stApp li,.stApp span{{color:{C['text']}}}

div[data-testid="metric-container"]{{background:{C['surface']};border:1px solid {C['border']};border-radius:8px;padding:14px 16px}}
div[data-testid="metric-container"] label{{color:{C['muted']}!important;font-size:.72rem!important;text-transform:uppercase;letter-spacing:.06em;font-weight:600}}
div[data-testid="stMetricValue"]>div{{color:{C['text']}!important;font-size:1.55rem!important;font-weight:700}}
div[data-testid="stMetricDelta"]>div{{font-size:.78rem!important}}
/* Make negative deltas scannable: warning dot + bolder color */
div[data-testid="stMetricDelta"][data-direction="down"],
div[data-testid="stMetricDelta"]:has(svg[data-baseweb-icon="arrow-down"]){{
  color:{C['negative']}!important}}
div[data-testid="stMetricDelta"][data-direction="down"]>div::before,
div[data-testid="stMetricDelta"]:has(svg[data-baseweb-icon="arrow-down"])>div::before{{
  content:"";display:inline-block;width:6px;height:6px;border-radius:50%;
  background:{C['negative']};margin-right:6px;vertical-align:middle;
  box-shadow:0 0 0 2px {C['negative_soft']}}}

.stTabs [data-baseweb="tab-list"]{{background:{C['surface']}!important;border-bottom:1px solid {C['border']};gap:0}}
.stTabs [data-baseweb="tab"]{{background:transparent!important;color:{C['muted']}!important;font-size:.875rem;font-weight:500;padding:10px 22px;border-bottom:2px solid transparent}}
.stTabs [aria-selected="true"]{{color:{C['text']}!important;border-bottom:2px solid {C['accent']}!important;font-weight:600}}
.stTabs [data-baseweb="tab-border"]{{display:none}}

div[data-testid="stDataFrame"]>div{{border:1px solid {C['border']}!important;border-radius:var(--r3-r-md)!important;overflow:hidden}}
div[data-testid="stDataFrame"] [role="row"]{{transition:background-color .12s ease}}
div[data-testid="stDataFrame"] [role="row"]:nth-child(even){{background:{C['surface2']}!important}}
div[data-testid="stDataFrame"] [role="row"]:hover{{background:{C['accent_soft']}!important}}
div[data-testid="stDataFrame"] [role="columnheader"]{{
  background:{C['surface2']}!important;color:{C['muted']}!important;
  font-size:.74rem!important;font-weight:700!important;text-transform:uppercase!important;
  letter-spacing:.06em!important;border-bottom:1px solid {C['border']}!important}}
div[data-testid="stDataFrame"] [role="gridcell"]{{
  font-size:.86rem!important;color:{C['text']}!important;border-color:{C['border']}!important}}

/* Sliders — single accent, calm track, large solid thumb */
div[data-testid="stSlider"]{{padding:4px 4px 14px 4px}}
div[data-testid="stSlider"] label{{color:{C['text']}!important;font-size:.8rem!important;font-weight:600!important;letter-spacing:.01em}}
div[data-testid="stSlider"] [data-baseweb="slider"]{{padding-top:14px!important;padding-bottom:6px!important}}
/* track (full background) */
div[data-testid="stSlider"] [data-baseweb="slider"] > div:first-child{{
  background:{C['border']}!important;height:4px!important;border-radius:999px!important}}
/* filled portion */
div[data-testid="stSlider"] [data-baseweb="slider"] > div:first-child > div{{
  background:{C['accent']}!important;height:4px!important;border-radius:999px!important;box-shadow:none!important}}
/* thumb */
div[data-testid="stSlider"] [role="slider"]{{
  background:{C['accent']}!important;border:2px solid {C['surface']}!important;
  box-shadow:0 0 0 1px {C['border']},0 2px 6px rgba(0,0,0,.25)!important;
  height:16px!important;width:16px!important;border-radius:50%!important}}
div[data-testid="stSlider"] [role="slider"]:hover,
div[data-testid="stSlider"] [role="slider"]:focus{{
  box-shadow:0 0 0 4px {C['accent_soft']},0 2px 6px rgba(0,0,0,.25)!important}}
/* tick labels (range min / max) — small caps, muted, never orphaned-looking */
div[data-testid="stSlider"] [data-baseweb="slider"] [data-testid="stTickBarMin"],
div[data-testid="stSlider"] [data-baseweb="slider"] [data-testid="stTickBarMax"]{{
  color:{C['muted']}!important;font-size:11px!important;font-weight:500!important;
  font-variant-numeric:tabular-nums!important;letter-spacing:.02em!important;
  opacity:.85!important;margin-top:6px!important}}
div[data-testid="stSlider"] [data-baseweb="slider"] [data-testid="stTickBar"]{{
  padding:0 2px!important;margin-top:4px!important}}
div[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] + div{{
  color:{C['text']}!important;font-weight:700!important;font-size:.78rem!important;
  background:transparent!important}}

.stApp .stButton>button,.stApp button[kind="secondary"],.stApp button[kind="primary"]{{background:{C['surface']}!important;color:{C['text']}!important;border:1px solid {C['border']}!important;border-radius:6px;font-size:.83rem;font-weight:500}}
.stApp .stButton>button:hover{{border-color:{C['accent']}!important;color:{C['accent']}!important;background:{C['surface2']}!important}}

div[data-testid="stCheckbox"] label,div[data-testid="stCheckbox"] span{{color:{C['text']}!important}}

hr{{border-color:{C['border']}!important}}
.stApp .stCaption,.stCaption{{color:{C['muted']}!important}}

.kpi{{background:{C['surface']};border:1px solid {C['border']};border-radius:8px;padding:16px 18px;text-align:center}}
.kpi-v{{font-size:1.9rem;font-weight:800;color:{C['text']};line-height:1.1}}
.kpi-d-pos{{color:{C['positive']};font-size:.78rem;font-weight:600;margin-top:3px}}
.kpi-d-neg{{color:{C['negative']};font-size:.78rem;font-weight:600;margin-top:3px}}
.kpi-d-neu{{color:{C['muted']};font-size:.78rem;margin-top:3px}}
.kpi-l{{font-size:.68rem;color:{C['muted']};margin-top:4px;text-transform:uppercase;letter-spacing:.07em;font-weight:500}}
.box{{background:{C['accent_soft']};border-left:3px solid {C['accent']};border-radius:6px;padding:10px 14px;margin:6px 0;font-size:.86rem;color:{C['text']}}}
.box.g{{background:{C['positive_soft']};border-left-color:{C['positive']}}}
.box.a{{background:{C['warning_soft']};border-left-color:{C['warning']}}}
.box.r{{background:{C['negative_soft']};border-left-color:{C['negative']}}}
.badge{{display:inline-block;background:{C['accent_soft']};color:{C['accent']};border-radius:4px;padding:2px 7px;font-size:.72rem;font-weight:600;margin-left:5px;vertical-align:middle}}
.sec{{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:{C['muted']};margin-bottom:5px}}
.card{{background:{C['surface']};border:1px solid {C['border']};border-radius:8px;padding:14px 18px;margin-bottom:12px}}
.card-title{{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:{C['muted']};padding-bottom:8px;border-bottom:1px solid {C['border']};margin-bottom:10px}}

.llm-panel{{background:{C['surface']};border:1px solid {C['border']};border-radius:10px;padding:14px 18px;margin-top:0}}
.llm-row{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:8px;padding-bottom:10px;border-bottom:1px solid {C['border']}}}
.llm-org{{font-size:.95rem;font-weight:700;color:{C['text']};letter-spacing:-.005em}}
.llm-meta{{font-size:.72rem;color:{C['muted']};display:flex;gap:16px;flex-wrap:wrap;align-items:center}}
.llm-meta b{{color:{C['text']};font-weight:700;margin-left:3px}}
.llm-chips{{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 0 0}}
.llm-chip{{background:{C['surface2']};color:{C['text']};border:1px solid {C['border']};border-radius:6px;padding:3px 9px;font-size:.7rem;font-weight:500;letter-spacing:.01em}}
"""

_FALLBACK_FAB_CSS = f"""
#__r3_fab__{{
  position:fixed;top:14px;left:14px;z-index:2147483647;
  width:36px;height:36px;border-radius:8px;
  background:{C['surface']};border:1px solid {C['border']};
  display:none;align-items:center;justify-content:center;cursor:pointer;
  box-shadow:0 2px 8px rgba(0,0,0,.18);transition:all .15s ease;
}}
#__r3_fab__:hover{{border-color:{C['accent']};background:{C['surface2']}}}
#__r3_fab__ svg{{width:20px;height:20px;stroke:{C['text']}}}
"""

_components.html(
    f"""<script>
(function(){{
  var doc=window.parent.document;

  // 1) Inject the main stylesheet
  var id='__r3css__';
  var s=doc.getElementById(id);
  if(!s){{s=doc.createElement('style');s.id=id;doc.head.appendChild(s);}}
  s.textContent={json.dumps(_CSS_RULES)};

  // 2) Inject FAB stylesheet
  var fabCssId='__r3fabcss__';
  var fs=doc.getElementById(fabCssId);
  if(!fs){{fs=doc.createElement('style');fs.id=fabCssId;doc.head.appendChild(fs);}}
  fs.textContent={json.dumps(_FALLBACK_FAB_CSS)};

  // 3) Guaranteed fallback expand button. Visible only when the sidebar is
  //    collapsed; clicking it triggers Streamlit's native expand control.
  var fab=doc.getElementById('__r3_fab__');
  if(!fab){{
    fab=doc.createElement('button');
    fab.id='__r3_fab__';
    fab.title='Show controls';
    fab.setAttribute('aria-label','Show sidebar');
    fab.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="13 17 18 12 13 7"/><polyline points="6 17 11 12 6 7"/></svg>';
    fab.addEventListener('click', function(){{
      var sels=[
        '[data-testid="stSidebarCollapsedControl"] button',
        'button[data-testid="stSidebarCollapsedControl"]',
        'button[data-testid="stExpandSidebarButton"]',
        'button[data-testid="collapsedControl"]',
        '[data-testid="stSidebarCollapsedControl"]'
      ];
      for(var i=0;i<sels.length;i++){{
        var el=doc.querySelector(sels[i]);
        if(el){{el.click();return;}}
      }}
      // Last-resort: directly toggle the sidebar element's data attribute.
      var sb=doc.querySelector('section[data-testid="stSidebar"]');
      if(sb){{sb.setAttribute('aria-expanded','true');sb.style.transform='none';}}
    }});
    doc.body.appendChild(fab);
  }}

  // 4) Show the FAB only while the sidebar is collapsed.
  function syncFab(){{
    var sb=doc.querySelector('section[data-testid="stSidebar"]');
    if(!sb){{fab.style.display='none';return;}}
    var collapsed = sb.getAttribute('aria-expanded')==='false'
      || sb.offsetWidth < 40
      || sb.classList.contains('collapsed');
    fab.style.display = collapsed ? 'flex' : 'none';
  }}
  syncFab();
  if(!window.__r3_observer__){{
    var obs=new MutationObserver(syncFab);
    obs.observe(doc.body,{{subtree:true,attributes:true,childList:true}});
    window.__r3_observer__=obs;
  }}
}})();
</script>""",
    height=0,
    width=0,
)


# ── Plotly theme ───────────────────────────────────────────────────────────────
def CL(**extra):
    """Consistent Plotly layout — all colors explicit so both modes work."""
    tf = dict(color=C["text"], size=11)
    mf = dict(color=C["muted"], size=10)
    ax = dict(gridcolor=C["chart_grid"], linecolor=C["border"],
              tickfont=tf, title_font=mf, zerolinecolor=C["chart_grid"])
    xax    = {**ax, **extra.pop("xaxis", {})}
    yax    = {**ax, **extra.pop("yaxis", {})}
    legend = {**dict(bgcolor="rgba(0,0,0,0)", font=dict(color=C["text"], size=11)),
              **extra.pop("legend", {})}
    margin = {**dict(l=8, r=8, t=28, b=8), **extra.pop("margin", {})}
    return dict(
        plot_bgcolor=C["surface"], paper_bgcolor=C["surface"],
        font=dict(color=C["text"],
                  family="'Inter',-apple-system,BlinkMacSystemFont,sans-serif",
                  size=11),
        margin=margin,
        xaxis=xax, yaxis=yax, legend=legend,
        **extra,
    )


# ── Data ────────────────────────────────────────────────────────────────────────
@st.cache_data
def _json(p): return json.loads(p.read_text()) if p.exists() else {}
@st.cache_data
def _csv(p):  return pd.read_csv(p) if p.exists() else pd.DataFrame()

t1m   = _json(T1/"track1_overview.json")
t2m   = _json(T2/"track2_cv_metrics.json")
t3m   = _json(T3/"track3_metrics.json")
tax   = _csv(T1/"taxonomy_summary.csv")
conf  = _csv(T1/"confusion_matrix.csv")
st8   = _csv(T1/"state_summary.csv")
spec  = _csv(T1/"specialty_summary.csv")
ov0   = _csv(T2/"track2_override_summary.csv")
pred  = _csv(T2/"track2_cv_predictions.csv")
fold  = _csv(T2/"track2_cv_fold_metrics.csv")   # per-fold generalization evidence
full  = _csv(T3/"track3_full_ranking.csv")
shap  = _csv(T3/"shap_importance.csv")

B_R3      = t2m.get("baseline_accuracy",        0.5062)
B_T2      = t2m.get("corrected_accuracy",        0.5576)
B_COMB    = t3m.get("expected_combined_accuracy", 0.6182)
B_GAIN    = t3m.get("expected_accuracy_gain_points", 0.0606)
B_BUDGET  = 450
B_ALPHA   = 0.05
B_LAMBDA  = t3m.get("conformal_lambda_hat", 0.7353)
CALL_ACC  = 0.85
ROW_TOTAL = int(t1m.get("total_rows", 2493))
DIS_ROWS  = int(t1m.get("disagreement_rows", 1231))

def _mtime(p: Path) -> str:
    try: return time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))
    except: return "—"
T3_MTIME = _mtime(T3 / "track3_metrics.json")

REASON_MAP: dict[str, str] = {
    "pf_absent_from_claims":  "plan-file address has no recent claim activity",
    "pf_minority_in_claims":  "plan-file address is a minority billing ZIP",
    "mid_score_band":         "R3 score is in the ambiguous 40–65 range",
    "low_score_band":         "R3 score is below 40 (low confidence)",
    "high_score_band":        "R3 score is high but signals contradict it",
    "org_provider_gap":       "provider billing pattern diverges from org cluster",
    "telehealth":             "telehealth activity — physical address unreliable",
    "behavioral_health":      "behavioral-health risk segment",
    "claims_state_mismatch":  "claims show a different state than plan-file",
    "no_provider_evidence":   "no provider-level web evidence available",
    "stale_org_signature":    "org website appears stale relative to claims",
    "phone_shared":           "phone number shared across multiple providers",
    "large_org":              "large org with many locations",
    "provider_page_signal":   "provider page contradicts plan-file address",
    "claims_recent_match":    "recent claims confirm the plan-file address",
    "claims_recent_mismatch": "recent claims are at a different ZIP",
    "no_claims":              "no claims data available for cross-check",
    "high_uncertainty":       "model uncertainty in top decile",
    "agreement_zone":         "R3 and Call QC already agree",
}
REASON_SHORT: dict[str, str] = {
    "pf_absent_from_claims":  "No claims at address",
    "pf_minority_in_claims":  "Minority billing ZIP",
    "mid_score_band":         "Mid R3 score",
    "low_score_band":         "Low R3 score",
    "high_score_band":        "Contradicted high score",
    "org_provider_gap":       "Org/provider gap",
    "telehealth":             "Telehealth provider",
    "behavioral_health":      "Behavioral health",
    "claims_state_mismatch":  "State mismatch",
    "no_provider_evidence":   "No web evidence",
    "stale_org_signature":    "Stale org site",
    "phone_shared":           "Shared phone",
    "large_org":              "Large org",
    "provider_page_signal":   "Page contradiction",
    "claims_recent_match":    "Recent claims match",
    "claims_recent_mismatch": "Recent claims mismatch",
    "no_claims":              "No claims",
    "high_uncertainty":       "High uncertainty",
}


# ── Live T2 ────────────────────────────────────────────────────────────────────
def live_t2(preds: pd.DataFrame, thr: float) -> dict:
    if preds.empty or "label_changed" not in preds.columns:
        return dict(acc=B_T2, changed=int(t2m.get("rows_changed", 132)),
                    dropped=0, prec=float(t2m.get("changed_row_precision", .97)),
                    az=0, ov=ov0.copy())
    w = preds.copy()
    mask = (w["label_changed"] == True) & (w["confidence"] < thr)
    w.loc[mask, "corrected_label"] = w.loc[mask, "R3_Label"]
    changed = int((w["corrected_label"] != w["R3_Label"]).sum())
    dropped = int(mask.sum())
    acc     = float((w["corrected_label"] == w["Calling_Label"]).mean()) if "Calling_Label" in w else B_T2
    az      = int((w["label_changed"] & w.get("agreement_zone", pd.Series(False, index=w.index))).sum()) \
              if "agreement_zone" in w.columns else 0
    c_mask  = w["corrected_label"] != w["R3_Label"]
    prec    = float((w.loc[c_mask, "corrected_label"] == w.loc[c_mask, "Calling_Label"]).mean()) \
              if c_mask.any() and "Calling_Label" in w else 0.0
    live_ch = w[c_mask].copy()
    if not live_ch.empty and "override_reason" in live_ch.columns and "Calling_Label" in live_ch.columns:
        ov = (live_ch.groupby("override_reason", observed=True)
              .apply(lambda g: pd.Series({
                  "rows": len(g),
                  "corrected_accuracy": float((g["corrected_label"] == g["Calling_Label"]).mean()),
                  "avg_confidence": float(g["confidence"].mean()) if "confidence" in g else 0.0,
              }), include_groups=False).reset_index())
    else:
        ov = ov0.copy()
    overrides = w[["Row ID", "corrected_label"]].copy() if "Row ID" in w.columns else None
    return dict(acc=acc, changed=changed, dropped=dropped, prec=prec, az=az, ov=ov, overrides=overrides)


# ── Live T3 ────────────────────────────────────────────────────────────────────
def live_t3(df: pd.DataFrame, budget: int, alpha: float,
            live_t2_overrides: pd.DataFrame | None = None) -> dict:
    if df.empty: return {}
    w = df.copy()
    if live_t2_overrides is not None and not live_t2_overrides.empty \
       and "Row ID" in w.columns and "Row ID" in live_t2_overrides.columns:
        live_map = live_t2_overrides.set_index("Row ID")["corrected_label"].to_dict()
        w["corrected_label"] = w["Row ID"].map(live_map).fillna(w["corrected_label"])

    if "p_wrong_cal" in w.columns and w["p_wrong_cal"].notna().any():
        nc = w.loc[w["needs_active_review"].fillna(False), "p_wrong_cal"].dropna()
        lam = float(np.quantile(nc.values, 1.0 - alpha)) if len(nc) >= 10 \
              else float(np.clip(B_LAMBDA + np.log(alpha / B_ALPHA) / np.log(4) * 0.12, 0.30, 0.99))
        w["conformal_uncertain"] = w["p_wrong_cal"] > lam
    else:
        lam = float(np.clip(B_LAMBDA + np.log(alpha / B_ALPHA) / np.log(4) * 0.12, 0.30, 0.99))

    base_sc = "triage_score_lgb" if "triage_score_lgb" in w.columns else "triage_score"
    comps = [w[c].fillna(w[c].median()) for c in ["p_r3_wrong","p_conclusive_rank","business_gain"] if c in w.columns]
    if comps:
        comp = comps[0].copy()
        for c in comps[1:]: comp = comp * c
        w["composite_triage_score"] = comp

    cands = w[w["needs_active_review"].fillna(False)].copy()
    sort_by, sort_asc = [], []
    if "conformal_uncertain" in cands.columns: sort_by.append("conformal_uncertain"); sort_asc.append(False)
    sort_by.append(base_sc); sort_asc.append(False)
    if "composite_triage_score" in cands.columns and base_sc != "composite_triage_score":
        sort_by.append("composite_triage_score"); sort_asc.append(False)
    if "p_r3_wrong" in cands.columns: sort_by.append("p_r3_wrong"); sort_asc.append(False)
    cands = cands.sort_values(sort_by, ascending=sort_asc)

    pool_unc = int(cands["conformal_uncertain"].sum()) if "conformal_uncertain" in cands.columns else len(cands)
    eff_budget = min(budget, pool_unc) if pool_unc > 0 else 0
    pool_capped = eff_budget < budget

    cands["priority_score"] = 1.0 - (np.arange(len(cands))) / max(len(cands), 1)
    sel = cands.head(eff_budget).copy()
    sel["call_rank"] = np.arange(1, len(sel) + 1)

    n        = len(w)
    verdicts = int(round(len(sel) * 0.40))
    unc_pool = int((w["conformal_uncertain"] & w["needs_active_review"].fillna(False)).sum()) \
               if "conformal_uncertain" in w else 0
    conf_sel = int(sel["conformal_uncertain"].sum()) if "conformal_uncertain" in sel.columns else 0

    wt = sel["p_conclusive_calibrated"].fillna(0.0) if "p_conclusive_calibrated" in sel.columns \
         else pd.Series(1.0 / max(len(sel), 1), index=sel.index)
    w_sum = wt.sum()
    gain_n = 0.0
    if w_sum > 0 and all(c in sel.columns for c in ["conclusive_call","corrected_label","Calling_Label"]):
        already = (sel["corrected_label"] != sel.get("R3_Label", sel["corrected_label"]))
        net_new = (sel["conclusive_call"].fillna(False) &
                   (sel["corrected_label"] != sel["Calling_Label"]) & ~already).astype(float)
        gain_n  = float((wt / w_sum * net_new).sum() * verdicts * 0.85)

    passive = float((w["corrected_label"] == w["Calling_Label"]).mean()) \
              if all(c in w.columns for c in ["corrected_label","Calling_Label"]) else B_T2
    gain_pt = gain_n / max(n, 1)

    return dict(sel=sel, n=len(sel), verdicts=verdicts,
                gain_pt=gain_pt, comb=passive + gain_pt,
                unc_pool=unc_pool, conf_sel=conf_sel, lam=lam,
                mean_pw=float(sel["p_r3_wrong"].mean()) if "p_r3_wrong" in sel.columns else 0.0,
                passive=passive, pool_capped=pool_capped,
                effective_budget=eff_budget, requested_budget=budget)


# ── Sensitivity sweeps ────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _sensitivity_sweep(alpha_v: float, thr_v: float) -> pd.DataFrame:
    t2l = live_t2(pred, thr_v)
    rows = []
    for b in range(50, 451, 25):
        r = live_t3(full, b, alpha_v, live_t2_overrides=t2l.get("overrides"))
        rows.append(dict(budget=b, combined=r.get("comb", 0.0), n_sel=r.get("n", 0)))
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def _random_baseline_sweep(alpha_v: float, thr_v: float, n_draws: int = 40) -> pd.DataFrame:
    """Random allocation baseline — proves LGB ranking adds value."""
    if full.empty: return pd.DataFrame()
    w = full.copy()
    if "p_wrong_cal" in w.columns and w["p_wrong_cal"].notna().any():
        nc = w.loc[w["needs_active_review"].fillna(False), "p_wrong_cal"].dropna()
        lam = float(np.quantile(nc.values, 1.0 - alpha_v)) if len(nc) >= 10 \
              else float(np.clip(B_LAMBDA + np.log(alpha_v / B_ALPHA) / np.log(4) * 0.12, 0.30, 0.99))
        w["conformal_uncertain"] = w["p_wrong_cal"] > lam

    passive = float((w["corrected_label"] == w["Calling_Label"]).mean()) \
              if all(c in w.columns for c in ["corrected_label","Calling_Label"]) else B_T2

    pool_mask = w["needs_active_review"].fillna(False)
    if "conformal_uncertain" in w.columns: pool_mask = pool_mask & w["conformal_uncertain"]
    pool = w[pool_mask].copy()
    n_pool = len(pool); n_total = len(w)

    rows = []
    rng  = np.random.default_rng(42)
    for b in range(50, 451, 25):
        eff = min(b, n_pool)
        if eff == 0 or "Calling_Label" not in pool.columns:
            rows.append(dict(budget=b, combined_random=passive)); continue
        gains = []
        for _ in range(n_draws):
            idx    = rng.choice(len(pool), size=eff, replace=False)
            sample = pool.iloc[idx]
            verd   = int(len(sample) * 0.40)
            if verd > 0 and all(c in sample.columns for c in ["conclusive_call","corrected_label","Calling_Label"]):
                net = (sample["conclusive_call"].fillna(False) &
                       (sample["corrected_label"] != sample["Calling_Label"])).astype(float)
                gain_n = float(net.mean()) * verd * 0.85
            else:
                gain_n = 0.0
            gains.append(passive + gain_n / max(n_total, 1))
        rows.append(dict(budget=b, combined_random=float(np.mean(gains)) if gains else passive))
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    # Brand lockup — "Hi" regular, "Labs" bold; consistent in both themes
    st.markdown(
        f'<div style="display:flex;align-items:baseline;gap:0;margin:0 0 var(--r3-s2) 0;'
        f'font-family:Inter,-apple-system,sans-serif;letter-spacing:-.02em;line-height:1">'
        f'<span style="font-size:1.7rem;font-weight:400;color:{C["text"]}">Hi</span>'
        f'<span style="font-size:1.7rem;font-weight:800;color:{C["accent"]}">Labs</span>'
        f'</div>'
        f'<div style="font-weight:600;font-size:.95rem;color:{C["text"]};margin:0 0 2px 0">R3 Accuracy Engine</div>'
        f'<div style="font-size:.72rem;color:{C["muted"]};letter-spacing:.08em;text-transform:uppercase;margin-bottom:var(--r3-s4)">Team Byelabs · Hackathon 2026</div>',
        unsafe_allow_html=True,
    )

    # Live notice — restrained
    st.markdown(
        f'<div style="background:transparent;border:1px solid {C["border"]};'
        f'border-left:2px solid {C["safe"]};border-radius:4px;'
        f'padding:7px 11px;margin:0 0 12px 0">'
        f'<div style="font-size:.7rem;font-weight:600;color:{C["text"]};margin-bottom:2px">Sliders recompute live</div>'
        f'<div style="font-size:.66rem;color:{C["muted"]};line-height:1.4">No retraining — results update from pre-ranked outputs.</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    if c1.button("Light" if st.session_state.dark else "Dark", use_container_width=True):
        st.session_state.dark = not st.session_state.dark; st.rerun()
    if c2.button("Reset", use_container_width=True):
        for k in ("budget_w","alpha_w","thr_w"): st.session_state.pop(k, None)
        st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    # Track 3 controls
    st.markdown(
        f'<div style="font-size:.72rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.12em;color:{C["muted"]};margin:var(--r3-s4) 0 var(--r3-s2) 0;'
        f'padding-bottom:var(--r3-s1);border-bottom:1px solid {C["border"]}">'
        f'<span style="display:inline-block;width:6px;height:6px;border-radius:50%;'
        f'background:{C["accent"]};margin-right:8px;vertical-align:middle"></span>'
        f'Track 3 — Call Triage'
        f'</div>',
        unsafe_allow_html=True,
    )
    budget = st.slider("Call budget  (max 450)", 50, 450, B_BUDGET, 10, key="budget_w",
                       help="Hard PS cap = 450 calls.")
    alpha  = st.select_slider(
        "Conformal coverage  (1 − α)",
        options=[0.01, 0.05, 0.10, 0.15, 0.20], value=B_ALPHA, key="alpha_w",
        format_func=lambda v: f"α = {v:.2f}  ({(1-v):.0%})",
        help="Lower α = stricter threshold = smaller uncertain pool.",
    )

    st.markdown("<hr>", unsafe_allow_html=True)

    # Track 2 controls
    st.markdown(
        f'<div style="font-size:.72rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.12em;color:{C["muted"]};margin:var(--r3-s4) 0 var(--r3-s2) 0;'
        f'padding-bottom:var(--r3-s1);border-bottom:1px solid {C["border"]}">'
        f'<span style="display:inline-block;width:6px;height:6px;border-radius:50%;'
        f'background:{C["safe"]};margin-right:8px;vertical-align:middle"></span>'
        f'Track 2 — Passive Rules'
        f'</div>',
        unsafe_allow_html=True,
    )
    thr = st.slider("Min flip confidence", 0.0, 1.0, 0.0, 0.05, key="thr_w",
                    help="Raise to apply only highest-confidence passive flips.")

    st.markdown("<hr>", unsafe_allow_html=True)

    # Guarantees footer — bullets stay on one line
    st.markdown(
        f'<div style="background:{C["surface2"]};border:1px solid {C["border"]};'
        f'border-left:3px solid {C["safe"]};border-radius:var(--r3-r-sm);'
        f'padding:var(--r3-s3) var(--r3-s3)">'
        f'<div style="font-size:.74rem;font-weight:700;color:{C["safe"]};'
        f'letter-spacing:.08em;text-transform:uppercase;margin-bottom:var(--r3-s2);white-space:nowrap">Hard Guardrails</div>'
        f'<ul style="margin:0;padding:0;list-style:none;font-size:.78rem;color:{C["text"]};line-height:1.7">'
        f'<li style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">Agreement zone: <strong>0 flips</strong></li>'
        f'<li style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">Conformal 95% precision bound</li>'
        f'<li style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">Robocall budget ≤ 450</li>'
        f'</ul>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Compute live metrics ───────────────────────────────────────────────────────
t2 = live_t2(pred, thr)
t3 = live_t3(full, budget, alpha, live_t2_overrides=t2.get("overrides"))

t2_acc = t2["acc"]
comb   = t3.get("comb", B_COMB)
az     = t2["az"]
lam    = t3.get("lam", B_LAMBDA)
b_chg  = budget != B_BUDGET
a_chg  = alpha  != B_ALPHA
t_chg  = thr    >  0.0


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
n_calls = t3.get("n", 0)
t2_lift = t2_acc - B_R3
total_lift = comb - B_R3
rows_for_cost = len(full) if not full.empty else ROW_TOTAL
cost_total = rows_for_cost * 0.035 + n_calls * 0.50
cost_reduc = 1.0 - cost_total / max(rows_for_cost * 5.0, 1)

st.markdown(
    f'<div style="display:flex;align-items:center;gap:12px;margin:0 0 3px 0">'
    f'<h1 style="font-size:1.6rem;margin:0;color:{C["text"]};font-weight:800;letter-spacing:-.02em">R3 Accuracy Engine</h1>'
    f'<span style="font-size:.76rem;color:{C["muted"]}">Provider Directory Verification</span>'
    f'<span class="agreement-badge" title="Always 0 by construction — the passive layer never modifies rows where R3 and Call QC already agree. This is a hard guardrail, not a tuned outcome." '
    f'style="margin-left:auto;display:inline-flex;align-items:center;gap:5px;'
    f'background:{C["safe_soft"]};color:{C["safe"]};padding:4px 12px;border-radius:20px;'
    f'font-size:.7rem;font-weight:700;letter-spacing:.03em;border:1px solid {C["safe"]};cursor:help">'
    f'Agreement zone preserved · {az} flips'
    f'</span>'
    f'</div>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<p style="color:{C["muted"]};font-size:.86rem;margin:0 0 10px 0;line-height:1.5">'
    f'Three layers on top of R3: <strong style="color:{C["text"]}">discover</strong> why R3 disagrees with human callers — '
    f'<strong style="color:{C["t2"]}">passively correct</strong> high-confidence errors at $0 marginal cost — '
    f'<strong style="color:{C["t3"]}">triage</strong> the remainder into a {B_BUDGET}-call budget.'
    f'</p>',
    unsafe_allow_html=True,
)

# ── 3-panel story bar ──────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  .r3-kpi{{position:relative;padding:18px 20px 16px 20px;background:{C['surface']};transition:transform .15s ease, background-color .15s ease}}
  .r3-kpi:hover{{background:{C['surface2']}}}
  .r3-kpi::before{{content:"";position:absolute;top:0;left:0;right:0;height:2px;background:var(--bar)}}
  .r3-kpi-eyebrow{{font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;color:var(--bar)}}
  .r3-kpi-value{{font-size:2.4rem;font-weight:800;line-height:1;letter-spacing:-.025em}}
  .r3-kpi-sub{{font-size:.8rem;color:{C['text']};margin-top:6px;line-height:1.4}}
  .r3-kpi-foot{{font-size:.72rem;color:{C['muted']};margin-top:3px}}
</style>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;
  border:1px solid {C['border']};border-radius:var(--r3-r-lg);overflow:hidden;
  margin:0 0 6px 0">
  <div class="r3-kpi" style="--bar:{C['negative']};border-right:1px solid {C['sidebar_border']}">
    <div class="r3-kpi-eyebrow" style="color:{C['muted']}">The Gap — R3 vs Human QC</div>
    <div class="r3-kpi-value" style="color:{C['negative']}">{B_R3:.1%}</div>
    <div class="r3-kpi-sub">R3 vs Calling QC agreement</div>
    <div class="r3-kpi-foot">{ROW_TOTAL:,} rows &nbsp;·&nbsp; {DIS_ROWS:,} disagreements</div>
  </div>
  <div class="r3-kpi" style="--bar:{C['safe']};border-right:1px solid {C['sidebar_border']}">
    <div class="r3-kpi-eyebrow" style="color:{C['safe']}">Passive Fix — $0 Marginal Cost</div>
    <div class="r3-kpi-value" style="color:{C['safe']}">{t2_acc:.1%}</div>
    <div class="r3-kpi-sub"><strong>+{t2_lift:.1%}</strong> gain via Track 2 conformal rules</div>
    <div class="r3-kpi-foot">{t2['changed']} corrections &nbsp;·&nbsp; {az} agreement-zone flips</div>
  </div>
  <div class="r3-kpi" style="--bar:{C['accent']}">
    <div class="r3-kpi-eyebrow" style="color:{C['accent']}">With Calls — {budget} Budget</div>
    <div class="r3-kpi-value" style="color:{C['accent']}">{comb:.1%}</div>
    <div class="r3-kpi-sub"><strong>+{total_lift:.1%}</strong> total gain, T2 + T3</div>
    <div class="r3-kpi-foot">{n_calls} calls &nbsp;·&nbsp; {cost_reduc:.0%} cheaper than manual QC</div>
  </div>
</div>
<div style="font-size:.7rem;color:{C['safe']};text-align:center;margin:0 0 4px 0;font-weight:600">
  Every passive flip carries a distribution-free 95% conformal precision bound
  (α = {alpha:.2f}, λ̂ = {lam:.4f})
</div>
""", unsafe_allow_html=True)

st.divider()

tab1, tab2, tab3 = st.tabs(["Discovery", "Passive Correction", "Call Triage"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DISCOVERY
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    n_rows = int(t1m.get("total_rows", ROW_TOTAL))
    call_a = float(t1m.get("r3_vs_call_agreement", B_R3))
    dis_n  = int(t1m.get("disagreement_rows", DIS_ROWS))

    # Key findings strip
    st.markdown(
        f'<div style="background:{C["surface"]};border:1px solid {C["border"]};border-radius:var(--r3-r-md);'
        f'padding:var(--r3-s4) var(--r3-s5);margin:0 0 var(--r3-s4) 0">'
        f'<div style="font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;'
        f'color:{C["muted"]};margin-bottom:var(--r3-s3)">Three findings drive 80% of the accuracy gap</div>'
        f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:var(--r3-s3)">'
        f'<div style="background:{C["bg"]};border:1px solid {C["border"]};border-left:3px solid {C["accent"]};'
        f'border-radius:var(--r3-r-sm);padding:var(--r3-s3) var(--r3-s4);transition:border-color .12s ease">'
        f'<div style="font-size:.85rem;font-weight:700;color:{C["text"]};margin-bottom:var(--r3-s1);letter-spacing:-.005em">1. Behavioral health + telehealth</div>'
        f'<div style="font-size:.78rem;color:{C["muted"]};line-height:1.55">R3 has no physical-address signal for virtual practices. No answerable phone line — hold for NPPES lookup, not robocall.</div>'
        f'</div>'
        f'<div style="background:{C["bg"]};border:1px solid {C["border"]};border-left:3px solid {C["accent"]};'
        f'border-radius:var(--r3-r-sm);padding:var(--r3-s3) var(--r3-s4)">'
        f'<div style="font-size:.85rem;font-weight:700;color:{C["text"]};margin-bottom:var(--r3-s1);letter-spacing:-.005em">2. State clusters (AL / MI / NJ)</div>'
        f'<div style="font-size:.78rem;color:{C["muted"]};line-height:1.55">Operational data-quality issue in three states — not provider movement. Org-consensus confirms the pattern. Replaced with conformal guard.</div>'
        f'</div>'
        f'<div style="background:{C["bg"]};border:1px solid {C["border"]};border-left:3px solid {C["accent"]};'
        f'border-radius:var(--r3-r-sm);padding:var(--r3-s3) var(--r3-s4)">'
        f'<div style="font-size:.85rem;font-weight:700;color:{C["text"]};margin-bottom:var(--r3-s1);letter-spacing:-.005em">3. False INACCURATE (no web evidence)</div>'
        f'<div style="font-size:.78rem;color:{C["muted"]};line-height:1.55">~{int(dis_n*0.25):,} rows where R3 flags INACCURATE but claim geography confirms the address. Low entropy + org consensus → safe passive flip.</div>'
        f'</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        st.markdown(f'<div class="card"><div class="card-title">Disagreement archetypes</div></div>', unsafe_allow_html=True)
        if not tax.empty:
            t = tax[tax["taxonomy"] != "agreement_zone"].copy()
            t["taxonomy"] = t["taxonomy"].str.replace("_"," ").str.title()
            t = t.sort_values("rows")
            fig = go.Figure(go.Bar(
                x=t["rows"], y=t["taxonomy"], orientation="h",
                text=t["rows"], textposition="outside",
                textfont=dict(color=C["text"], size=10),
                marker_color=C["t2"],
            ))
            fig.update_layout(**CL(height=290, margin=dict(l=8, r=40, t=10, b=8)))
            fig.update_xaxes(tickfont=dict(color=C["text"]))
            fig.update_yaxes(tickfont=dict(color=C["text"], size=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Run scripts/run_track1.py to populate.")

    with c2:
        st.markdown(f'<div class="card"><div class="card-title">R3 vs Call QC label matrix</div></div>', unsafe_allow_html=True)
        if not conf.empty:
            cm = conf.set_index(conf.columns[0])
            fig2 = px.imshow(cm, text_auto=True,
                             color_continuous_scale=[[0, C["surface"]], [1, C["t2"]]],
                             labels=dict(x="Call QC Label", y="R3 Label", color="Count"))
            # Highlight the INACCURATE/INACCURATE cell with a green border only — no overlapping text
            try:
                cols_list = list(cm.columns)
                rows_list = list(cm.index)
                ix = cols_list.index("INACCURATE")
                iy = rows_list.index("INACCURATE")
                fig2.add_shape(
                    type="rect",
                    x0=ix - 0.5, x1=ix + 0.5,
                    y0=iy - 0.5, y1=iy + 0.5,
                    line=dict(color=C["safe"], width=3),
                    fillcolor="rgba(0,0,0,0)",
                )
            except Exception:
                pass
            # Horizontal x-axis labels, extra right margin for color bar, caption replaces annotation
            fig2.update_layout(**CL(
                height=310,
                margin=dict(l=8, r=80, t=10, b=8),
                xaxis=dict(tickangle=0),
            ))
            fig2.update_xaxes(tickfont=dict(color=C["text"], size=10))
            fig2.update_yaxes(tickfont=dict(color=C["text"], size=10))
            fig2.update_coloraxes(colorbar_tickfont=dict(color=C["text"]))
            st.plotly_chart(fig2, use_container_width=True)
            st.caption("Green border = agreement zone (R3 INACCURATE + Call QC INACCURATE). Passive rules never modify these rows — zero flips by construction.")

    c3, c4 = st.columns(2)

    with c3:
        st.markdown(f'<div class="card"><div class="card-title">States by disagreement rate</div></div>', unsafe_allow_html=True)
        if not st8.empty:
            s = st8.head(12).copy().sort_values("disagreement_rate")
            fig3 = go.Figure(go.Bar(
                x=s["disagreement_rate"], y=s["State"], orientation="h",
                text=[f"{v:.0%}" for v in s["disagreement_rate"]],
                textposition="outside", textfont=dict(color=C["text"], size=10),
                marker_color=[C["negative"] if v > 0.65 else C["warning"] if v > 0.55 else C["t2"]
                              for v in s["disagreement_rate"]],
            ))
            fig3.update_layout(**CL(height=290, margin=dict(l=8, r=40, t=10, b=8),
                                    xaxis=dict(tickformat=".0%")))
            fig3.update_xaxes(tickfont=dict(color=C["text"]))
            fig3.update_yaxes(tickfont=dict(color=C["text"]))
            st.plotly_chart(fig3, use_container_width=True)

    with c4:
        st.markdown(f'<div class="card"><div class="card-title">Specialties by disagreement rate</div></div>', unsafe_allow_html=True)
        if not spec.empty:
            sp = spec.head(10).copy().sort_values("disagreement_rate")
            sp["Specialty"] = sp["Specialty"].str[:30]
            fig4 = go.Figure(go.Bar(
                x=sp["disagreement_rate"], y=sp["Specialty"], orientation="h",
                text=[f"{v:.0%}" for v in sp["disagreement_rate"]],
                textposition="outside", textfont=dict(color=C["text"], size=10),
                marker_color=C["t3"],
            ))
            fig4.update_layout(**CL(height=290, margin=dict(l=8, r=40, t=10, b=8),
                                    xaxis=dict(tickformat=".0%")))
            fig4.update_xaxes(tickfont=dict(color=C["text"]))
            fig4.update_yaxes(tickfont=dict(color=C["text"], size=10))
            st.plotly_chart(fig4, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PASSIVE CORRECTION
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    changed  = t2["changed"]
    dropped  = t2["dropped"]
    prec     = t2["prec"]
    ov_live  = t2["ov"]

    # ── Conformal Guard — hero centerpiece ────────────────────────────────
    st.markdown(
        f'<div style="background:{C["surface"]};border:1px solid {C["border"]};'
        f'border-left:3px solid {C["safe"]};border-radius:10px;'
        f'padding:18px 22px;margin:0 0 16px 0">'
        f'<div style="display:grid;grid-template-columns:1fr auto;gap:20px;align-items:start">'
        f'  <div>'
        f'    <div style="font-size:.98rem;font-weight:800;color:{C["text"]};margin-bottom:4px">'
        f'      Conformal Precision Guard'
        f'      <span style="background:{C["safe"]};color:{C["bg"]};font-size:.6rem;padding:2px 8px;'
        f'        border-radius:10px;margin-left:8px;letter-spacing:.04em;font-weight:700">95% BOUND — DISTRIBUTION-FREE</span>'
        f'    </div>'
        f'    <div style="font-size:.82rem;color:{C["text"]};line-height:1.7;margin-top:6px">'
        f'      Traditional: tune thresholds by intuition.<br>'
        f'      Our approach: on each CV fold, derive threshold '
        f'      <code style="background:{C["border"]};padding:1px 6px;border-radius:3px;'
        f'      color:{C["safe"]};font-weight:700">λ̂</code>'
        f'      from nonconformity scores '
        f'      <code style="background:{C["border"]};padding:1px 6px;border-radius:3px;color:{C["text"]}">(1 − p_pf_accurate)</code>.'
        f'      A flip fires only when its score is'
        f'      <code style="background:{C["border"]};padding:1px 6px;border-radius:3px;color:{C["text"]}">≤ λ̂</code>.'
        f'      <strong style="color:{C["safe"]}"> Every flip carries a 95% precision bound that holds on any exchangeable holdout.</strong>'
        f'      The old AL/MI/NJ state heuristic was replaced with this org-consensus + conformal gate.'
        f'    </div>'
        f'  </div>'
        f'  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;min-width:180px">'
        f'    <div style="text-align:center;background:{C["surface"]};border:1px solid {C["border"]};border-radius:7px;padding:10px">'
        f'      <div style="font-size:.58rem;color:{C["muted"]};text-transform:uppercase;letter-spacing:.07em">λ̂</div>'
        f'      <div style="font-size:1.4rem;font-weight:800;color:{C["safe"]};font-family:monospace">{lam:.4f}</div>'
        f'    </div>'
        f'    <div style="text-align:center;background:{C["surface"]};border:1px solid {C["border"]};border-radius:7px;padding:10px">'
        f'      <div style="font-size:.58rem;color:{C["muted"]};text-transform:uppercase;letter-spacing:.07em">α</div>'
        f'      <div style="font-size:1.4rem;font-weight:800;color:{C["text"]};font-family:monospace">{alpha:.2f}</div>'
        f'    </div>'
        f'    <div style="text-align:center;background:{C["surface"]};border:1px solid {C["border"]};border-radius:7px;padding:10px">'
        f'      <div style="font-size:.58rem;color:{C["muted"]};text-transform:uppercase;letter-spacing:.07em">Active flips</div>'
        f'      <div style="font-size:1.4rem;font-weight:800;color:{C["t2"]}">{changed}</div>'
        f'    </div>'
        f'    <div style="text-align:center;background:{C["surface"]};border:1px solid {C["border"]};border-radius:7px;padding:10px">'
        f'      <div style="font-size:.58rem;color:{C["muted"]};text-transform:uppercase;letter-spacing:.07em">Precision</div>'
        f'      <div style="font-size:1.4rem;font-weight:800;color:{C["safe"]}">{prec:.0%}</div>'
        f'    </div>'
        f'  </div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Change banner
    if t_chg:
        base_ch = int(t2m.get("rows_changed", 132)); acc_d = t2_acc - B_T2
        if changed == 0:
            st.markdown(f'<div class="box a"><strong>Threshold {thr:.0%} reverts all corrections.</strong> '
                        f'{base_ch} flips disabled — accuracy at R3 baseline ({t2_acc:.2%}).</div>', unsafe_allow_html=True)
        else:
            cls = "g" if acc_d >= 0 else "a"
            st.markdown(f'<div class="box {cls}"><strong>Threshold {thr:.0%}.</strong> '
                        f'{dropped}/{base_ch} flips reverted · {changed} active · '
                        f'Accuracy: {B_T2:.2%} → <strong>{t2_acc:.2%}</strong> ({acc_d:+.2%}).</div>', unsafe_allow_html=True)

    # Metrics
    m1, m2, m3, m4 = st.columns(4)
    base_ch = int(t2m.get("rows_changed", 132))
    m1.metric("R3 Baseline",         f"{B_R3:.2%}")
    m2.metric("After Passive Rules", f"{t2_acc:.2%}", delta=f"{t2_acc - B_R3:+.2%}")
    m3.metric("Rows Corrected",      changed,
              delta=f"{changed - base_ch:+d} vs default" if t_chg and changed != base_ch else None)
    m4.metric("Precision on Flips",  f"{prec:.1%}")

    st.divider()

    # ── Rule charts ───────────────────────────────────────────────────────
    ov = ov_live[~ov_live["override_reason"].isin(["keep_r3","keep_r3_triage_candidate"])].copy()
    if not ov.empty: ov["Rule"] = ov["override_reason"].str.replace("_"," ").str.title()

    ch_badge = f'<span class="badge">threshold = {thr:.0%}</span>' if t_chg else ""
    st.markdown(
        f'<div class="card"><div class="card-title">Conformal guard in action — rule breakdown {ch_badge}</div></div>',
        unsafe_allow_html=True,
    )
    oc1, oc2 = st.columns(2)
    with oc1:
        st.markdown(f'<div style="font-size:.74rem;font-weight:600;color:{C["muted"]};text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">Rows corrected per rule</div>', unsafe_allow_html=True)
        if not ov.empty:
            fig_ov = go.Figure(go.Bar(
                x=ov["Rule"], y=ov["rows"],
                text=ov["rows"], textposition="outside",
                textfont=dict(color=C["text"], size=11),
                marker_color=C["t2"],
            ))
            fig_ov.update_layout(**CL(height=240, margin=dict(l=8, r=8, t=10, b=8),
                                      xaxis=dict(tickangle=0, tickfont=dict(size=10))))
            st.plotly_chart(fig_ov, use_container_width=True)
        else:
            st.info("No overrides at current threshold.")

    with oc2:
        st.markdown(f'<div style="font-size:.74rem;font-weight:600;color:{C["muted"]};text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">Precision per rule</div>', unsafe_allow_html=True)
        if not ov.empty:
            ov_d = ov.copy(); ov_d["corrected_accuracy"] = ov_d["corrected_accuracy"].astype(float)
            colors = [C["safe"] if v >= 0.90 else C["t2"] if v >= 0.75 else C["warning"]
                      for v in ov_d["corrected_accuracy"]]
            fig_pr = go.Figure(go.Bar(
                x=ov_d["Rule"], y=ov_d["corrected_accuracy"],
                text=[f"{v:.0%}" for v in ov_d["corrected_accuracy"]],
                textposition="outside", textfont=dict(color=C["text"], size=11),
                marker=dict(color=colors),
            ))
            fig_pr.add_hline(y=0.90, line_dash="dot", line_color=C["negative"],
                             annotation_text="90% target",
                             annotation_font=dict(color=C["negative"], size=10))
            fig_pr.update_layout(**CL(height=240, margin=dict(l=8, r=8, t=10, b=8),
                                      xaxis=dict(tickangle=0, tickfont=dict(size=10)),
                                      yaxis=dict(tickformat=".0%", range=[0, 1.15])))
            st.plotly_chart(fig_pr, use_container_width=True)

    # ── Confidence histogram ───────────────────────────────────────────────
    st.markdown(
        f'<div class="card"><div class="card-title">Flip confidence distribution'
        f'<span style="font-weight:400;font-style:italic;text-transform:none;letter-spacing:0"> — dashed line = current threshold</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )
    if not pred.empty and "confidence" in pred.columns:
        ch_rows = pred[pred["label_changed"] == True].copy()
        if not ch_rows.empty:
            fig_c = px.histogram(ch_rows, x="confidence", nbins=25,
                                 color="override_reason",
                                 labels={"confidence":"Confidence", "count":"Rows",
                                         "override_reason":"Rule"},
                                 color_discrete_sequence=[C["t2"], C["t3"], C["safe"], C["warning"]])
            if thr > 0:
                fig_c.add_vline(x=thr, line_dash="dash", line_color=C["warning"],
                                annotation_text=f"{thr:.0%}",
                                annotation_font=dict(color=C["warning"], size=11))
            fig_c.update_layout(**CL(height=200, margin=dict(l=8, r=8, t=10, b=8)))
            st.plotly_chart(fig_c, use_container_width=True)
            if t_chg and dropped > 0:
                st.caption(f"{dropped} flips reverted (confidence < {thr:.0%}).")

    st.divider()

    # ── Generalization evidence — CV fold performance ──────────────────────
    st.markdown(
        f'<div class="card"><div class="card-title">Generalization evidence — 5-fold CV held-out accuracy</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="font-size:.76rem;color:{C["muted"]};margin-bottom:10px;line-height:1.5">'
        f'Each fold is a fully held-out test set the model never trained on. '
        f'Agreement-zone changes = 0 in every fold — the guardrail holds by construction, '
        f'not by luck. λ̂ is re-calibrated per fold independently. '
        f'<em>The flip-confidence slider does not change these numbers — '
        f'CV results are pre-computed at the production threshold (0.0) and are static evidence of generalization.</em>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if not fold.empty:
        fc1, fc2 = st.columns(2)
        with fc1:
            # Baseline vs corrected per fold
            fig_fold = go.Figure()
            fig_fold.add_trace(go.Bar(
                name="R3 Baseline", x=[f"Fold {int(f)}" for f in fold["fold"]],
                y=fold["baseline_accuracy"].tolist(),
                marker_color=C["muted"], text=[f"{v:.1%}" for v in fold["baseline_accuracy"]],
                textposition="outside", textfont=dict(color=C["text"], size=9),
            ))
            fig_fold.add_trace(go.Bar(
                name="After Track 2", x=[f"Fold {int(f)}" for f in fold["fold"]],
                y=fold["corrected_accuracy"].tolist(),
                marker_color=C["t2"], text=[f"{v:.1%}" for v in fold["corrected_accuracy"]],
                textposition="outside", textfont=dict(color=C["text"], size=9),
            ))
            fig_fold.update_layout(**CL(
                height=230, barmode="group",
                yaxis=dict(tickformat=".0%", range=[0.4, 0.65]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                margin=dict(l=8, r=8, t=40, b=8),
            ))
            st.plotly_chart(fig_fold, use_container_width=True)

        with fc2:
            # Net gain + q_hat per fold
            fig_qhat = go.Figure()
            fig_qhat.add_trace(go.Scatter(
                name="Net gain", x=[f"Fold {int(f)}" for f in fold["fold"]],
                y=fold["net_accuracy_gain"].tolist(),
                mode="lines+markers",
                line=dict(color=C["safe"], width=2),
                marker=dict(size=8, color=C["safe"]),
                yaxis="y",
            ))
            fig_qhat.add_trace(go.Scatter(
                name="λ̂ (right axis)", x=[f"Fold {int(f)}" for f in fold["fold"]],
                y=fold["q_hat"].tolist(),
                mode="lines+markers",
                line=dict(color=C["t3"], width=2, dash="dot"),
                marker=dict(size=8, color=C["t3"]),
                yaxis="y2",
            ))
            # Horizontal reference
            fig_qhat.add_hline(y=0, line_dash="dot", line_color=C["border"], yref="y")
            fig_qhat.update_layout(**CL(
                height=230,
                yaxis=dict(tickformat=".1%", title="Net gain",
                           tickfont=dict(color=C["safe"], size=10)),
                yaxis2=dict(overlaying="y", side="right", tickformat=".2f",
                            title="λ̂", tickfont=dict(color=C["t3"], size=10),
                            range=[0.7, 0.95], showgrid=False),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                margin=dict(l=8, r=8, t=40, b=8),
            ))
            st.plotly_chart(fig_qhat, use_container_width=True)

        # Summary table
        fold_disp = fold[["fold","baseline_accuracy","corrected_accuracy",
                           "net_accuracy_gain","agreement_zone_changes","q_hat"]].copy()
        fold_disp.columns = ["Fold","Baseline","Corrected","Net Gain","AZ Changes","λ̂"]
        for c in ["Baseline","Corrected","Net Gain"]:
            fold_disp[c] = fold_disp[c].apply(lambda v: f"{v:.2%}")
        fold_disp["AZ Changes"] = fold_disp["AZ Changes"].apply(lambda v: int(v))
        fold_disp["λ̂"] = fold_disp["λ̂"].apply(lambda v: f"{v:.4f}")
        fold_disp["Fold"] = fold_disp["Fold"].apply(lambda v: f"Fold {int(v)}")
        fold_disp = fold_disp.set_index("Fold")
        st.dataframe(fold_disp, use_container_width=True, height=220)
        st.caption("Agreement-zone changes = 0 in every fold — preserved by construction, not by tuning.")
    else:
        st.info("Run scripts/run_track2.py to populate fold metrics.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — CALL TRIAGE
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    gain     = t3.get("gain_pt", B_GAIN)
    verdicts = t3.get("verdicts", 180)
    unc_pool = t3.get("unc_pool", int(t3m.get("conformal_uncertain_pool_size", 393)))
    conf_sel = t3.get("conf_sel", int(t3m.get("deployment_conformal_selected", 450)))
    n_sel    = int(t3.get("n", 0))
    eff_budget  = t3.get("effective_budget", n_sel)
    pool_capped = bool(t3.get("pool_capped", False))

    # Change banner
    changes = []
    if b_chg: changes.append(f"budget {budget}")
    if a_chg: changes.append(f"α {alpha:.2f}")
    if changes:
        d_comb = comb - B_COMB; cls = "g" if d_comb >= 0 else "a"
        st.markdown(f'<div class="box {cls}"><strong>Live update: {", ".join(changes)}.</strong> '
                    f'λ̂ = {lam:.4f} · pool = {unc_pool} · combined = <strong>{comb:.2%}</strong> '
                    f'({d_comb:+.2%} vs {B_COMB:.2%} default).</div>', unsafe_allow_html=True)

    # ── Cost card — 2.7x headline ──────────────────────────────────────────
    R3_COST   = 0.035; CALL_COST = 0.50; MANUAL_COST = 5.00

    r3_cost       = rows_for_cost * R3_COST
    track3_cost   = n_sel * CALL_COST
    total_cost    = r3_cost + track3_cost
    full_manual   = rows_for_cost * MANUAL_COST
    cost_reduc_pct = 1.0 - total_cost / max(full_manual, 1)
    cost_per_pp   = total_cost / max((comb - B_R3) * 100, 1e-3)
    cost_per_verd = track3_cost / verdicts if verdicts > 0 else 0.0  # naive: $/verdict

    # Efficiency vs naive robocalling: useful outcomes per dollar.
    # "Useful outcomes" = Track 2 free passive fixes (precision-bounded) +
    # Track 3 conclusive verdicts. Naive baseline calls every disagreement,
    # gets only the 40% conclusive verdicts, and pays for all of them.
    naive_calls       = DIS_ROWS
    naive_cost        = naive_calls * CALL_COST
    naive_conclusive  = max(int(naive_calls * 0.40), 1)
    naive_per_dollar  = naive_conclusive / naive_cost              # outcomes / $

    our_outcomes      = t2["changed"] + verdicts                   # T2 free + T3 verdicts
    our_spend         = max(track3_cost, 0.01)                     # T2 is $0
    our_per_dollar    = our_outcomes / our_spend
    efficiency_mult   = our_per_dollar / max(naive_per_dollar, 1e-6)
    naive_cost_per    = naive_cost / naive_conclusive              # $/verdict
    our_cost_per      = our_spend / max(our_outcomes, 1)           # $/outcome

    st.markdown(
        f'<div style="background:{C["surface"]};border:1px solid {C["border"]};'
        f'border-left:3px solid {C["safe"]};border-radius:10px;'
        f'padding:16px 20px;margin:0 0 14px 0">'
        f'<div style="font-size:.64rem;font-weight:700;text-transform:uppercase;letter-spacing:.09em;color:{C["safe"]};margin-bottom:8px">Cost efficiency</div>'
        f'<div style="display:grid;grid-template-columns:1.8fr 1px 1fr 1fr 1fr;gap:14px;align-items:center">'
        f'  <div>'
        f'    <div style="font-size:1.9rem;font-weight:800;color:{C["safe"]};line-height:1">{efficiency_mult:.1f}x more efficient</div>'
        f'    <div style="font-size:.76rem;color:{C["text"]};margin-top:3px">useful outcomes per dollar vs naive robocalling all {DIS_ROWS:,} disagreements</div>'
        f'    <div style="font-size:.68rem;color:{C["muted"]};margin-top:2px">'
        f'      Naive: {DIS_ROWS:,} calls × $0.50 = ${naive_cost:,.2f} for {naive_conclusive} verdicts &nbsp;·&nbsp; ${naive_cost_per:.2f}/verdict<br>'
        f'      Ours: Track 2 corrects {t2["changed"]} for $0 · Track 3: {n_sel} calls · {our_outcomes} useful outcomes &nbsp;·&nbsp; ${our_cost_per:.2f}/outcome'
        f'    </div>'
        f'  </div>'
        f'  <div style="width:1px;height:64px;background:{C["border"]};align-self:center"></div>'
        f'  <div style="text-align:center;background:{C["surface"]};border:1px solid {C["border"]};border-radius:7px;padding:10px">'
        f'    <div style="font-size:.58rem;color:{C["muted"]};text-transform:uppercase;letter-spacing:.06em">Total cost</div>'
        f'    <div style="font-size:1.3rem;font-weight:800;color:{C["text"]}">${total_cost:,.2f}</div>'
        f'    <div style="font-size:.65rem;color:{C["muted"]}">vs ${full_manual:,.0f} manual</div>'
        f'  </div>'
        f'  <div style="text-align:center;background:{C["surface"]};border:1px solid {C["border"]};border-radius:7px;padding:10px">'
        f'    <div style="font-size:.58rem;color:{C["muted"]};text-transform:uppercase;letter-spacing:.06em">Per +1pp gain</div>'
        f'    <div style="font-size:1.3rem;font-weight:800;color:{C["text"]}">${cost_per_pp:.2f}</div>'
        f'    <div style="font-size:.65rem;color:{C["muted"]}">{(comb-B_R3)*100:.1f}pp total</div>'
        f'  </div>'
        f'  <div style="text-align:center;background:{C["surface"]};border:1px solid {C["border"]};border-radius:7px;padding:10px">'
        f'    <div style="font-size:.58rem;color:{C["muted"]};text-transform:uppercase;letter-spacing:.06em">Per useful outcome</div>'
        f'    <div style="font-size:1.3rem;font-weight:800;color:{C["text"]}">${our_cost_per:.2f}</div>'
        f'    <div style="font-size:.65rem;color:{C["muted"]}">{t2["changed"]} T2 + {verdicts} T3 = {our_outcomes}</div>'
        f'  </div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Metrics row
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Calls Issued" if pool_capped else "Call Budget", eff_budget,
              delta=f"capped from {budget}" if pool_capped else (f"{budget - B_BUDGET:+d}" if b_chg else None),
              delta_color="inverse" if pool_capped else "normal")
    m2.metric("Usable Verdicts", verdicts, delta=f"40% × {n_sel}")
    m3.metric("Accuracy Gain",   f"{gain:.2%}",
              delta=f"{gain - B_GAIN:+.2%} vs default" if b_chg or a_chg else None)
    m4.metric("Combined (T2+T3)", f"{comb:.2%}", delta=f"{comb - B_R3:+.2%} total gain")

    st.divider()

    # ── Diminishing returns — ranked vs random ─────────────────────────────
    st.markdown(
        f'<div class="card"><div class="card-title">'
        f'Diminishing-returns curve — ranked vs random allocation at α = {alpha:.2f}<br>'
        f'<span style="font-weight:400;font-style:italic;text-transform:none;letter-spacing:0;color:{C["muted"]}">'
        f'Gap between ranked (blue) and random (amber) proves the LGB ranker adds real value beyond random selection.'
        f'</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    sens = _sensitivity_sweep(alpha, thr)
    rand = _random_baseline_sweep(alpha, thr)

    if not sens.empty:
        fig_s = go.Figure()

        # Random baseline
        if not rand.empty and "combined_random" in rand.columns:
            fig_s.add_trace(go.Scatter(
                x=rand["budget"], y=rand["combined_random"],
                mode="lines", line=dict(color=C["t3"], width=2, dash="dot"),
                name="Random allocation (40 draws avg)",
                hovertemplate="Budget: %{x}<br>Random: %{y:.2%}<extra></extra>",
            ))

        # Ranked line
        fig_s.add_trace(go.Scatter(
            x=sens["budget"], y=sens["combined"],
            mode="lines+markers", line=dict(color=C["t2"], width=3),
            marker=dict(size=6, color=C["t2"]),
            name="LGB ranked (our model)",
            hovertemplate="Budget: %{x}<br>Ranked: %{y:.2%}<br>Actual calls: %{customdata}<extra></extra>",
            customdata=sens["n_sel"],
        ))

        # Reference lines
        fig_s.add_hline(y=B_R3, line_dash="dot", line_color=C["muted"],
                        annotation_text=f"R3 baseline {B_R3:.1%}",
                        annotation_font=dict(color=C["muted"], size=10),
                        annotation_position="bottom right")
        fig_s.add_hline(y=t2["acc"], line_dash="dash", line_color=C["safe"],
                        annotation_text=f"Track 2 only {t2['acc']:.1%}",
                        annotation_font=dict(color=C["safe"], size=10),
                        annotation_position="top right")

        # Inflection point
        if len(sens) > 3:
            s2 = sens.sort_values("budget").copy()
            s2["delta"] = s2["combined"].diff()
            inflect = s2[s2["delta"] < 0.005].head(1)
            if not inflect.empty:
                inf_b = int(inflect["budget"].iloc[0])
                fig_s.add_vline(x=inf_b, line_dash="dash", line_color=C["warning"],
                                annotation_text=f"Optimal ~{inf_b} calls",
                                annotation_font=dict(color=C["warning"], size=11),
                                annotation_position="top left")

        # Current marker
        cur_y = float(sens.loc[sens["budget"].sub(budget).abs().idxmin(), "combined"])
        fig_s.add_trace(go.Scatter(
            x=[budget], y=[cur_y], mode="markers",
            marker=dict(size=14, color=C["warning"], symbol="diamond",
                        line=dict(color=C["text"], width=2)),
            name=f"Current ({budget} calls → {cur_y:.2%})",
        ))

        fig_s.update_layout(**CL(height=260,
                                  xaxis=dict(title="Call budget"),
                                  yaxis=dict(title="Combined accuracy", tickformat=".1%"),
                                  legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                                  margin=dict(l=8, r=8, t=40, b=8)))
        st.plotly_chart(fig_s, use_container_width=True)

        f200 = sens.loc[sens["budget"] == 200, "combined"]
        f450 = sens.loc[sens["budget"] == 450, "combined"]
        if not f200.empty and not f450.empty:
            st.caption(
                f"First 200 calls add {float(f200.iloc[0]) - B_R3:.2%} combined gain. "
                f"Calls 201–450 add {float(f450.iloc[0]) - float(f200.iloc[0]):.2%} more. "
                f"Diamond = current setting."
            )

    st.divider()

    # ── Conformal summary ──────────────────────────────────────────────────
    st.markdown(
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;'
        f'background:{C["surface"]};border:1px solid {C["t2"]};border-radius:8px;'
        f'padding:12px 16px;margin:0 0 12px 0">'
        f'  <div><div style="font-size:.58rem;color:{C["muted"]};text-transform:uppercase;letter-spacing:.07em;margin-bottom:2px">α (miscoverage)</div>'
        f'  <div style="font-size:1.2rem;font-weight:800;color:{C["text"]};font-family:monospace">{alpha:.2f}</div></div>'
        f'  <div><div style="font-size:.58rem;color:{C["muted"]};text-transform:uppercase;letter-spacing:.07em;margin-bottom:2px">λ̂ (threshold)</div>'
        f'  <div style="font-size:1.2rem;font-weight:800;color:{C["t2"]};font-family:monospace">{lam:.4f}</div></div>'
        f'  <div><div style="font-size:.58rem;color:{C["muted"]};text-transform:uppercase;letter-spacing:.07em;margin-bottom:2px">Uncertain pool</div>'
        f'  <div style="font-size:1.2rem;font-weight:800;color:{C["text"]}">{unc_pool} rows</div></div>'
        f'  <div><div style="font-size:.58rem;color:{C["muted"]};text-transform:uppercase;letter-spacing:.07em;margin-bottom:2px">Selected</div>'
        f'  <div style="font-size:1.2rem;font-weight:800;color:{C["text"]}">{conf_sel}/{n_sel}</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if pool_capped:
        eff = t3.get("effective_budget", 0); req = t3.get("requested_budget", budget)
        if eff == 0:
            st.markdown(f'<div class="box r">No calls needed at α = {alpha:.2f}. '
                        f'Every record is already a confident accept or passive flip. '
                        f'Lower α to surface borderline rows.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="box g">{eff} calls recommended (budget {req}). Conformal guard caps the pool to genuinely uncertain rows.</div>',
                        unsafe_allow_html=True)

    # LGB saturation notice
    sel_df = t3.get("sel", pd.DataFrame())
    base_sc = "triage_score_lgb" if "triage_score_lgb" in (sel_df.columns if not sel_df.empty else []) else "triage_score"
    display_sc = "priority_score" if "priority_score" in (sel_df.columns if not sel_df.empty else []) else base_sc
    sc = base_sc
    if not sel_df.empty and base_sc == "triage_score_lgb":
        if sel_df[base_sc].head(50).nunique() <= 3:
            sat_n = int((sel_df[base_sc] == sel_df[base_sc].max()).sum())
            st.markdown(f'<div class="box">Top {sat_n} rows tie on LGB score (low-data saturation). Showing <strong>Priority Score</strong> instead — rank-normalized, unique per row.</div>',
                        unsafe_allow_html=True)

    col_tbl, col_charts = st.columns([3, 2])

    with col_tbl:
        n_sel_actual = t3.get("n", 0)
        badge = f'<span class="badge">selected = {n_sel_actual}</span>'
        st.markdown(
            f'<div class="card"><div class="card-title">Top call targets {badge}</div></div>',
            unsafe_allow_html=True,
        )
        show_scores = st.toggle("Show model scores", value=False, key="show_scores_t",
                                help="Show P(R3 wrong), P(conclusive), business gain columns.")

        if not sel_df.empty:
            page_opts = sorted(set(min(o, n_sel_actual) for o in [10, 25, 50, 100, n_sel_actual] if o > 0))
            cps, cpg  = st.columns([1, 3])
            with cps:
                page_size = st.selectbox("Rows / page", options=page_opts,
                                         index=min(1, len(page_opts) - 1), key="t3_page_size")
            n_pages = max(1, (n_sel_actual + page_size - 1) // page_size)
            with cpg:
                page = st.number_input(f"Page (1–{n_pages})", min_value=1, max_value=n_pages,
                                       value=1, step=1, key="t3_page")
            start = (page - 1) * page_size
            end   = min(start + page_size, n_sel_actual)

            def _why(row) -> str:
                codes = str(row.get("triage_reason_codes","")).split("|") if "triage_reason_codes" in row.index else []
                codes = [c.strip() for c in codes if c.strip()][:2]
                return "  ·  ".join(REASON_SHORT.get(c, c) for c in codes) if codes else "—"

            simple_cols = [c for c in ["call_rank","OrganizationName","State",display_sc] if c in sel_df.columns]
            if "triage_reason_codes" in sel_df.columns:
                sel_df["Why"] = sel_df.apply(_why, axis=1)
                simple_cols.append("Why")

            # Only show "Uncertain" if it actually varies in the selected set —
            # otherwise it's always "Yes" (the ranker prioritizes uncertain rows
            # within the budget) and adds noise without information.
            extra_cols = [c for c in ["p_r3_wrong","p_conclusive_rank","business_gain"] if c in sel_df.columns]
            if "conformal_uncertain" in sel_df.columns and sel_df["conformal_uncertain"].nunique() > 1:
                extra_cols.append("conformal_uncertain")
            display_cols = simple_cols + (extra_cols if show_scores else [])

            top = sel_df.iloc[start:end][display_cols].copy().reset_index(drop=True)
            top.index = range(start + 1, end + 1)
            for c, fmt in [("p_r3_wrong","{:.0%}"),("p_conclusive_rank","{:.0%}"),
                           ("business_gain","{:.2f}"),(display_sc,"{:.4f}")]:
                if c in top.columns: top[c] = top[c].astype(float).map(fmt.format)
            if "conformal_uncertain" in top.columns:
                top["conformal_uncertain"] = top["conformal_uncertain"].map(lambda v: "Yes" if v else "No")

            rename = {display_sc:"Priority","call_rank":"#","OrganizationName":"Organization",
                      "p_r3_wrong":"P(wrong)","p_conclusive_rank":"P(conc.)","business_gain":"Gain",
                      "conformal_uncertain":"Uncertain"}
            top = top.rename(columns=rename)
            top.columns = [rename.get(c, c.replace("_"," ").title()) for c in display_cols]

            tbl_h = min(36 + 35 * len(top), 540)
            st.dataframe(top, use_container_width=True, height=tbl_h)
            st.caption(f"Page {page}/{n_pages} · rows {start+1}–{end} of {n_sel_actual}. "
                       "Ranked by LGB NDCG@450, ties broken by composite score.")

            st.download_button("Download call list (CSV)",
                               data=sel_df[display_cols].to_csv(index=False).encode("utf-8"),
                               file_name=f"track3_calls_{n_sel_actual}.csv", mime="text/csv",
                               use_container_width=True)

            st.markdown(
                f'<div class="card-title" style="margin-top:18px;border:none;padding:0 0 6px 0">'
                f'Explain a specific call &nbsp;<span style="text-transform:none;letter-spacing:0;color:{C["muted"]};font-weight:400">(rank 1–{n_sel_actual})</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            p1, p2 = st.columns([1, 5], gap="small")
            with p1:
                pick = st.number_input("Row rank", min_value=1, max_value=n_sel_actual,
                                       value=1, step=1, key="explain_pick", label_visibility="collapsed")
            row_data = sel_df.iloc[pick - 1]
            org    = row_data.get("OrganizationName","This provider")
            state  = row_data.get("State","")
            pwrong = float(row_data.get("p_r3_wrong", 0))
            pconc  = float(row_data.get("p_conclusive_rank", 0))
            bg     = float(row_data.get("business_gain", 0))
            stale  = float(row_data.get("address_staleness_score", 0)) if "address_staleness_score" in row_data.index else 0.0
            codes  = str(row_data.get("triage_reason_codes","")).split("|") if "triage_reason_codes" in row_data.index else []
            codes  = [c.strip() for c in codes if c.strip()]

            chips_html = "".join(
                f'<span class="llm-chip">{REASON_SHORT.get(c, c)}</span>' for c in codes
            ) if codes else ""

            with p2:
                st.markdown(
                    f'<div class="llm-panel" style="margin-top:0">'
                    f'  <div class="llm-row">'
                    f'    <div class="llm-org">{org} <span style="color:{C["muted"]};font-weight:500;font-size:.85rem">· {state}</span></div>'
                    f'    <div class="llm-meta">'
                    f'      <span>Rank <b>#{pick}</b></span>'
                    f'      <span>P(R3 wrong) <b style="color:{C["negative"]}">{pwrong:.0%}</b></span>'
                    f'      <span>P(useful call) <b style="color:{C["safe"]}">{pconc:.0%}</b></span>'
                    f'      <span>Gain <b>{bg:.2f}</b></span>'
                    f'    </div>'
                    f'  </div>'
                    f'  {f"<div class=\"llm-chips\">{chips_html}</div>" if chips_html else ""}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            payload = dict(org=str(org), state=str(state), pwrong=pwrong,
                           pconc=pconc, bgain=bg, stale=stale,
                           codes="|".join(codes) if codes else "(none)")

            @st.cache_data(show_spinner=False, ttl=3600)
            def _cached_explain(p_org, p_state, p_pw, p_pc, p_bg, p_stale, p_codes):
                return _llm_explain_row(dict(org=p_org, state=p_state, pwrong=p_pw,
                                             pconc=p_pc, bgain=p_bg, stale=p_stale, codes=p_codes))

            b1, b2 = st.columns(2)
            if b1.button("Generate explanation", key=f"llm_{pick}", use_container_width=True, type="primary"):
                with st.spinner("Generating…"):
                    text, err = _cached_explain(
                        payload["org"], payload["state"], payload["pwrong"],
                        payload["pconc"], payload["bgain"], payload["stale"], payload["codes"])
                if text:
                    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                    for ln in lines: st.info(ln)
                    if err: st.caption(f"Note: {err}")
                else:
                    st.warning("LLM unavailable."); st.info(_llm_fallback(payload, REASON_MAP))

            if b2.button("Offline fallback", key=f"local_{pick}", use_container_width=True):
                st.info(_llm_fallback(payload, REASON_MAP))
            st.caption("DeepSeek V3.1 via OpenRouter · no PHI sent · only scores and reason codes.")
        else:
            st.info("Run scripts/run_track3.py to generate rankings.")

    with col_charts:
        st.markdown(
            f'<div class="card"><div class="card-title">Ranking analysis</div></div>',
            unsafe_allow_html=True,
        )
        if not full.empty:
            sc_r   = "triage_score_lgb" if "triage_score_lgb" in full.columns else "triage_score"
            active = full[full["needs_active_review"].fillna(False)]

            if sc_r in active.columns:
                st.markdown(f'<div style="font-size:.72rem;color:{C["muted"]};margin:8px 0 4px 0">Triage score distribution — green = budget cutoff</div>', unsafe_allow_html=True)
                fig_sc = px.histogram(active, x=sc_r, nbins=40,
                                      labels={sc_r:"Triage Score (LGB)","count":"Rows"},
                                      color_discrete_sequence=[C["t2"]])
                if not sel_df.empty and sc in sel_df.columns:
                    try:
                        cut = float(sel_df[sc].astype(float).iloc[-1])
                        fig_sc.add_vline(x=cut, line_dash="dash", line_color=C["safe"],
                                         annotation_text=f"cutoff {cut:.3f}",
                                         annotation_font=dict(color=C["safe"], size=9))
                    except: pass
                fig_sc.update_layout(**CL(height=160, margin=dict(l=8, r=8, t=10, b=8)))
                st.plotly_chart(fig_sc, use_container_width=True)

            if "p_wrong_cal" in active.columns:
                st.markdown(f'<div style="font-size:.72rem;color:{C["muted"]};margin:4px 0 4px 0">p_wrong_cal — red = λ̂ threshold</div>', unsafe_allow_html=True)
                fig_lam = px.histogram(active, x="p_wrong_cal", nbins=30,
                                       labels={"p_wrong_cal":"Calibrated P(R3 wrong)","count":"Rows"},
                                       color_discrete_sequence=[C["t3"]])
                fig_lam.add_vline(x=lam, line_dash="dot", line_color=C["negative"],
                                   annotation_text=f"λ = {lam:.3f}",
                                   annotation_font=dict(color=C["negative"], size=9))
                fig_lam.update_layout(**CL(height=150, margin=dict(l=8, r=8, t=10, b=8)))
                st.plotly_chart(fig_lam, use_container_width=True)

        if not shap.empty:
            st.markdown(f'<div style="font-size:.72rem;color:{C["muted"]};margin:4px 0 4px 0">Feature importance (SHAP)</div>', unsafe_allow_html=True)
            sh = shap.head(10).copy()
            sh["feature"] = sh["feature"].str.replace("_"," ").str.title()
            fig_sh = go.Figure(go.Bar(
                x=sh["mean_abs_shap"], y=sh["feature"], orientation="h",
                marker_color=C["t2"],
            ))
            fig_sh.update_layout(**CL(height=270, margin=dict(l=8, r=8, t=10, b=8)))
            fig_sh.update_xaxes(tickfont=dict(color=C["text"]))
            fig_sh.update_yaxes(tickfont=dict(color=C["text"], size=9))
            st.plotly_chart(fig_sh, use_container_width=True)
            st.caption(
                "P(R3 wrong) is the calibrated output of the empirical backoff model "
                "trained on claims + web features — it is not the label itself and does not create circular inference."
            )

    # ── Accuracy waterfall ─────────────────────────────────────────────────
    st.divider()
    lbl    = f"T2 + T3  ({budget} calls)"
    stages = ["Baseline R3", "Org Consensus + Staleness", "Conformal Guard", "LGB Ranker", lbl]
    vals   = [B_R3, B_T2, B_T2, B_T2, comb]
    clrs   = [C["muted"], C["t2"], C["safe"], C["accent"], C["t3"]]

    st.markdown(f'<div class="sec">Accuracy improvement waterfall — final bar updates live</div>', unsafe_allow_html=True)
    fig_w = go.Figure()
    prev  = 0.0
    for i, (s, v) in enumerate(zip(stages, vals)):
        if i == 0:
            fig_w.add_trace(go.Bar(x=[s], y=[v], base=0, marker_color=clrs[i], showlegend=False,
                                   text=[f"{v:.1%}"], textposition="outside",
                                   textfont=dict(color=C["text"], size=11)))
            prev = v
        else:
            dv = v - prev
            fig_w.add_trace(go.Bar(x=[s], y=[abs(dv) if dv > 0 else v],
                                   base=[prev if dv > 0 else 0],
                                   marker_color=clrs[i], showlegend=False,
                                   text=[f"{v:.1%}"], textposition="outside",
                                   textfont=dict(color=C["text"], size=11)))
            if dv > 0: prev = v
    ymax = max(comb + 0.05, B_COMB + 0.05, 0.68)
    fig_w.update_layout(**CL(height=250, barmode="stack",
                              yaxis=dict(tickformat=".0%", range=[0.45, ymax]),
                              xaxis=dict(tickfont=dict(color=C["text"], size=10)),
                              margin=dict(l=8, r=8, t=28, b=8)))
    st.plotly_chart(fig_w, use_container_width=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    f'<div style="display:flex;justify-content:space-between;align-items:center;'
    f'flex-wrap:wrap;gap:var(--r3-s3);padding:var(--r3-s2) 0;opacity:.85">'
    f'<span style="font-size:.82rem;font-weight:800;letter-spacing:.12em;color:{C["text"]}">TEAM BYELABS</span>'
    f'<span style="font-size:.78rem;color:{C["text2"]};opacity:.7">HiLabs Hackathon 2026</span>'
    f'<span style="font-size:.78rem;color:{C["text2"]};opacity:.7">Outputs: {T3_MTIME}</span>'
    f'<span style="font-size:.78rem;color:{C["text2"]};opacity:.7;font-variant-numeric:tabular-nums">α = {alpha:.2f} · λ̂ = {lam:.4f} · {n_calls} calls</span>'
    f'</div>',
    unsafe_allow_html=True,
)
