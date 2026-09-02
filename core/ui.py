from __future__ import annotations
import html
import streamlit as st

CSS = r"""
<style>
:root {
  --ink:#0f172a; --muted:#64748b; --line:#e2e8f0; --panel:#ffffff;
  --blue:#2563eb; --blue-soft:#eff6ff; --green:#15803d; --amber:#b45309; --red:#b91c1c;
}
.block-container {padding-top: 1.05rem; padding-bottom: 2.6rem; max-width: 1480px;}
[data-testid="stSidebar"] {border-right: 1px solid var(--line); background:#f8fafc;}
[data-testid="stSidebar"] .block-container {padding-top:1.2rem;}
#MainMenu {visibility:hidden;} footer {visibility:hidden;}
h1, h2, h3 {letter-spacing: -0.022em; color:var(--ink);}
hr {border-color:#e8edf3;}
.kicker {font-size:.73rem; color:#64748b; text-transform:uppercase; letter-spacing:.11em; margin-bottom:.28rem; font-weight:650;}
.hero-title {font-size:2.05rem; line-height:1.12; font-weight:760; color:var(--ink); margin:0;}
.hero-sub {color:#475569; margin:.25rem 0 .62rem 0; font-size:.97rem;}
.meta-row {display:flex; flex-wrap:wrap; gap:.38rem; margin:.15rem 0 .95rem 0;}
.badge, .meta-pill {display:inline-block; padding:.18rem .54rem; border:1px solid #cbd5e1; border-radius:999px; font-size:.71rem; color:#334155; background:#fff;}
.meta-pill.blue {border-color:#bfdbfe; background:#eff6ff; color:#1d4ed8;}
.meta-pill.green {border-color:#bbf7d0; background:#f0fdf4; color:#166534;}
.section-title {font-size:1.08rem; font-weight:720; color:var(--ink); margin-top:.3rem; margin-bottom:.06rem;}
.section-sub {font-size:.82rem; color:var(--muted); margin-bottom:.58rem;}
.note {padding:.78rem .92rem; border:1px solid var(--line); border-radius:10px; background:#fff; color:#475569; font-size:.86rem;}
.decision {border:1px solid #bfdbfe; border-left:4px solid var(--blue); border-radius:10px; padding:.82rem 1rem; background:linear-gradient(90deg,#eff6ff 0%,#ffffff 64%); margin:.25rem 0 .85rem 0;}
.decision .d-title {font-size:.78rem; font-weight:740; color:#1d4ed8; letter-spacing:.04em; text-transform:uppercase; margin-bottom:.16rem;}
.decision .d-body {font-size:.94rem; color:#1e293b; line-height:1.6;}
.signal-strip {display:grid; grid-template-columns:repeat(4,1fr); gap:.55rem; margin:.2rem 0 .85rem 0;}
.signal {border:1px solid var(--line); border-radius:9px; background:white; padding:.65rem .78rem;}
.signal-k {font-size:.72rem;color:var(--muted);margin-bottom:.12rem;}
.signal-v {font-size:.94rem;font-weight:720;color:var(--ink);}
.node-card {border:1px solid var(--line); border-radius:11px; padding:.88rem .95rem; background:white; min-height:196px; box-shadow:0 1px 2px rgba(15,23,42,.025);}
.node-name {font-size:1rem; font-weight:730; color:var(--ink); margin-bottom:.08rem;}
.node-sub {font-size:.7rem;color:#94a3b8;margin-bottom:.58rem;}
.node-grid {display:grid; grid-template-columns:1fr 1fr; gap:.34rem .7rem; font-size:.79rem; color:#64748b;}
.node-grid b {color:#1e293b; font-weight:670; text-align:right;}
.status-ok {color:#166534; font-weight:680}.status-warn {color:#b45309; font-weight:680}.status-risk {color:#b91c1c; font-weight:680}
.small-muted {font-size:.76rem;color:#64748b;}
.proof-card {border:1px solid var(--line); border-radius:10px; background:#fff; padding:.78rem .88rem; min-height:104px;}
.proof-card .p-num {font-size:1.38rem; font-weight:780; color:var(--ink); line-height:1.1;}
.proof-card .p-label {font-size:.75rem; color:#64748b; margin-top:.16rem;}
.source-box {border:1px dashed #cbd5e1; border-radius:9px; background:#f8fafc; padding:.72rem .85rem; font-size:.8rem; color:#475569;}
[data-testid="stMetric"] {background:#fff; border:1px solid #e2e8f0; border-radius:10px; padding:.65rem .72rem; box-shadow:0 1px 2px rgba(15,23,42,.02);}
[data-testid="stMetricLabel"] {font-size:.76rem; color:#64748b;}
[data-testid="stMetricValue"] {font-size:1.28rem; color:#0f172a;}
.stButton > button, .stDownloadButton > button {border-radius:8px; font-weight:650;}
[data-testid="stDataFrame"] {border:1px solid #e2e8f0; border-radius:9px; overflow:hidden;}
[data-baseweb="tab-list"] {gap:.3rem;}
[data-baseweb="tab"] {height:2.45rem; border-radius:7px 7px 0 0; padding:0 .85rem;}
.sidebar-brand {font-size:1.35rem;font-weight:790;color:#0f172a;letter-spacing:-.03em;margin-bottom:.08rem;}
.sidebar-sub {font-size:.76rem;color:#64748b;margin-bottom:.52rem;}
.engine {font-size:.74rem;color:#166534;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:.48rem .58rem;margin:.35rem 0 .55rem;}
@media (max-width: 900px) {.signal-strip{grid-template-columns:repeat(2,1fr)} .hero-title{font-size:1.7rem}}
</style>
"""

PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}


def page_header(title: str, subtitle: str, meta: list[tuple[str, str]] | None = None):
    meta = meta or [("Web原型", "blue"), ("公开参数校准 + 情景仿真", "")]
    pills = "".join(
        f'<span class="meta-pill {html.escape(cls)}">{html.escape(label)}</span>'
        for label, cls in meta
    )
    st.markdown(
        f'<div class="kicker">碳算智调 · Carbon-aware Compute Dispatch</div>'
        f'<div class="hero-title">{html.escape(title)}</div>'
        f'<div class="hero-sub">{html.escape(subtitle)}</div>'
        f'<div class="meta-row">{pills}</div>',
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str | None = None):
    sub = f'<div class="section-sub">{html.escape(subtitle)}</div>' if subtitle else ""
    st.markdown(f'<div class="section-title">{html.escape(title)}</div>{sub}', unsafe_allow_html=True)


def decision_callout(title: str, body: str):
    st.markdown(
        f'<div class="decision"><div class="d-title">{html.escape(title)}</div>'
        f'<div class="d-body">{html.escape(body)}</div></div>',
        unsafe_allow_html=True,
    )


def signal_strip(items: list[tuple[str, str]]):
    cards = "".join(
        f'<div class="signal"><div class="signal-k">{html.escape(k)}</div><div class="signal-v">{html.escape(v)}</div></div>'
        for k, v in items
    )
    st.markdown(f'<div class="signal-strip">{cards}</div>', unsafe_allow_html=True)


def style_plot(fig, height: int | None = None, legend_horizontal: bool = True):
    layout = dict(
        font=dict(family="Arial, Microsoft YaHei, sans-serif", color="#334155", size=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
        margin=dict(l=18, r=18, t=52, b=18),
        title=dict(font=dict(size=15, color="#0f172a"), x=0.01, xanchor="left"),
        hoverlabel=dict(bgcolor="white", font_size=12),
    )
    if height:
        layout["height"] = height
    if legend_horizontal:
        layout["legend"] = dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title_text="")
    fig.update_layout(**layout)
    fig.update_xaxes(showgrid=False, linecolor="#e2e8f0", tickfont=dict(color="#64748b"))
    fig.update_yaxes(gridcolor="#eef2f7", zerolinecolor="#cbd5e1", tickfont=dict(color="#64748b"))
    return fig
