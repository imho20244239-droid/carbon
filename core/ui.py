import streamlit as st

CSS = r"""
<style>
.block-container {padding-top: 1.4rem; padding-bottom: 2.5rem; max-width: 1450px;}
[data-testid="stSidebar"] {border-right: 1px solid #e5e7eb;}
h1, h2, h3 {letter-spacing: -0.02em;}
.kicker {font-size:.78rem; color:#64748b; text-transform:uppercase; letter-spacing:.08em; margin-bottom:.2rem;}
.hero-title {font-size:2.0rem; font-weight:720; color:#0f172a; margin:0;}
.hero-sub {color:#475569; margin:.15rem 0 .8rem 0;}
.badge {display:inline-block; padding:.18rem .55rem; border:1px solid #cbd5e1; border-radius:999px; font-size:.72rem; color:#334155; background:#f8fafc;}
.note {padding:.75rem .9rem; border:1px solid #e2e8f0; border-radius:8px; background:#f8fafc; color:#475569; font-size:.88rem;}
.node-card {border:1px solid #e2e8f0; border-radius:10px; padding:.9rem 1rem; background:white; min-height:180px;}
.node-name {font-size:1rem; font-weight:700; color:#0f172a; margin-bottom:.55rem;}
.node-grid {display:grid; grid-template-columns:1fr 1fr; gap:.38rem .8rem; font-size:.82rem; color:#475569;}
.node-grid b {color:#0f172a; font-weight:650;}
.status-ok {color:#166534; font-weight:650}.status-warn {color:#b45309; font-weight:650}.status-risk {color:#b91c1c; font-weight:650}
.small-muted {font-size:.78rem;color:#64748b;}
</style>
"""

def page_header(title: str, subtitle: str):
    st.markdown(f'<div class="kicker">碳算智调 · Web Prototype</div><div class="hero-title">{title}</div><div class="hero-sub">{subtitle}</div>', unsafe_allow_html=True)
