from __future__ import annotations

import html

import streamlit as st


CSS = r"""
<style>
:root {
  --ink: #102a2a;
  --ink-soft: #294544;
  --muted: #647674;
  --line: #dce5e1;
  --line-strong: #c7d5cf;
  --canvas: #f4f7f3;
  --panel: #ffffff;
  --panel-soft: #edf4ef;
  --brand: #087f5b;
  --brand-strong: #056245;
  --brand-soft: #e4f3eb;
  --navy: #0b2527;
  --lime: #b8db66;
  --amber: #b96a18;
  --red: #b84343;
  --shadow: 0 10px 30px rgba(16, 42, 42, 0.07);
  --radius: 14px;
  --font: "Aptos", "Segoe UI Variable", "Microsoft YaHei UI", sans-serif;
}

html, body, [class*="css"] {font-family: var(--font);}
body {color: var(--ink); background: var(--canvas);}
::selection {background: #c9ead9; color: var(--navy);}
*:focus-visible {outline: 3px solid rgba(8, 127, 91, .28) !important; outline-offset: 2px !important;}
* {scrollbar-width: thin; scrollbar-color: #94aaa3 transparent;}
*::-webkit-scrollbar {width: 9px; height: 9px;}
*::-webkit-scrollbar-thumb {background: #94aaa3; border: 2px solid transparent; border-radius: 10px; background-clip: padding-box;}

[data-testid="stAppViewContainer"] {background: var(--canvas);}
[data-testid="stHeader"] {background: rgba(244, 247, 243, .94); border-bottom: 1px solid rgba(199, 213, 207, .7);}
.block-container {padding-top: 4.8rem; padding-bottom: 4rem; max-width: 1420px;}
#MainMenu, footer {visibility: hidden;}
h1, h2, h3 {color: var(--ink); letter-spacing: -.025em;}
p, li {color: var(--ink-soft);}
a {color: var(--brand-strong); text-decoration-thickness: 1px; text-underline-offset: 3px;}
hr {border-color: var(--line) !important; margin: 1.2rem 0 !important;}

[data-testid="stSidebar"] {background: var(--navy); border-right: 0; box-shadow: 10px 0 32px rgba(7, 30, 31, .08);}
[data-testid="stSidebar"] .block-container {padding: 1.35rem 1.05rem 1.8rem;}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {color: #a9c0ba !important;}
[data-testid="stSidebar"] hr {border-color: rgba(211, 232, 223, .13) !important;}
.brand-lockup {display: flex; align-items: center; gap: .72rem; margin: .1rem 0 1rem;}
.brand-mark {width: 38px; height: 38px; display: grid; place-items: center; border-radius: 12px; color: #d9f2a8; background: #123638; box-shadow: 0 8px 20px rgba(0,0,0,.18);}
.brand-mark svg {width: 23px; height: 23px; display: block;}
.sidebar-brand {font-size: 1.18rem; line-height: 1.1; font-weight: 760; color: #f5fbf8; letter-spacing: -.025em;}
.sidebar-sub {font-size: .71rem; color: #89a8a1; margin-top: .25rem; letter-spacing: .02em;}
.sidebar-label {margin: 1.1rem 0 .35rem; color: #6f918a; font-size: .68rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;}
.engine {display: flex; align-items: center; gap: .48rem; font-size: .74rem; color: #dff5e9; background: rgba(83, 148, 119, .17); border-radius: 10px; padding: .62rem .68rem; margin: .6rem 0 .45rem;}
.engine::before {content: ""; width: 8px; height: 8px; flex: 0 0 8px; border-radius: 50%; background: var(--lime); box-shadow: 0 0 0 4px rgba(184, 219, 102, .11);}
.sidebar-foot {margin-top: .5rem; padding-top: .45rem; font-size: .69rem; line-height: 1.65; color: #789890;}
[data-testid="stSidebar"] [role="radiogroup"] {gap: .3rem;}
[data-testid="stSidebar"] [role="radiogroup"] label {min-height: 42px; padding: .55rem .62rem; border-radius: 10px; transition: background-color .16s ease, color .16s ease;}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {background: rgba(230, 246, 239, .08);}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {background: rgba(184, 219, 102, .14);}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {color: #effbd8 !important; font-weight: 680;}
[data-testid="stSidebar"] [data-testid="stExpander"] {background: rgba(255,255,255,.035); border: 1px solid rgba(211,232,223,.1);}
[data-testid="stSidebar"] .stButton > button {background: transparent; color: #dcebe6; border-color: rgba(211,232,223,.25);}
[data-testid="stSidebar"] .stButton > button:hover {background: rgba(255,255,255,.07); border-color: rgba(211,232,223,.45); color: #fff;}

.page-head {padding: .2rem 0 1.25rem; border-bottom: 1px solid var(--line); margin-bottom: 1.2rem;}
.hero-title {max-width: 960px; font-size: clamp(2rem, 3vw, 3.15rem); line-height: 1.08; font-weight: 770; color: var(--ink); letter-spacing: -.035em; text-wrap: balance; margin: 0;}
.hero-sub {max-width: 76ch; color: var(--muted); margin: .68rem 0 0; font-size: .98rem; line-height: 1.72;}
.meta-row {display: flex; flex-wrap: wrap; gap: .42rem; margin-top: .85rem;}
.badge, .meta-pill {display: inline-flex; align-items: center; min-height: 26px; padding: .2rem .58rem; border: 1px solid var(--line-strong); border-radius: 999px; font-size: .7rem; font-weight: 620; color: #3c5752; background: rgba(255,255,255,.65);}
.meta-pill.blue {border-color: #b7daca; background: var(--brand-soft); color: var(--brand-strong);}
.meta-pill.green {border-color: #cce0a2; background: #f2f7df; color: #526c16;}
.section-title {font-size: 1.12rem; font-weight: 750; color: var(--ink); letter-spacing: -.018em; margin-top: 1.65rem; margin-bottom: .16rem;}
.section-sub {max-width: 82ch; font-size: .82rem; color: var(--muted); line-height: 1.65; margin-bottom: .72rem;}

.decision {border-radius: var(--radius); padding: 1rem 1.08rem; background: var(--panel-soft); margin: .35rem 0 1rem; overflow: hidden;}
.decision .d-title {font-size: .73rem; font-weight: 750; color: var(--brand-strong); letter-spacing: .05em; margin-bottom: .28rem;}
.decision .d-body {font-size: .92rem; color: var(--ink-soft); line-height: 1.72; max-width: 105ch;}
.signal-strip {display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .72rem; margin: .35rem 0 1.15rem;}
.signal {background: var(--panel); border-radius: 12px; padding: .82rem .88rem; box-shadow: 0 3px 18px rgba(16,42,42,.045);}
.signal-k {font-size: .7rem; color: var(--muted); margin-bottom: .24rem;}
.signal-v {font-size: .97rem; font-weight: 720; color: var(--ink); font-variant-numeric: tabular-nums; overflow-wrap: anywhere;}
.node-card {border-radius: var(--radius); padding: 1rem; background: var(--panel); min-height: 196px; box-shadow: var(--shadow);}
.node-name {font-size: 1rem; font-weight: 740; color: var(--ink); margin-bottom: .08rem;}
.node-sub {font-size: .7rem; color: #7a8d89; margin-bottom: .68rem;}
.node-grid {display: grid; grid-template-columns: 1fr 1fr; gap: .42rem .8rem; font-size: .79rem; color: var(--muted);}
.node-grid b {color: var(--ink-soft); font-weight: 680; text-align: right; font-variant-numeric: tabular-nums;}
.status-ok {color: var(--brand-strong); font-weight: 700;}
.status-warn {color: var(--amber); font-weight: 700;}
.status-risk {color: var(--red); font-weight: 700;}
.small-muted {font-size: .76rem; color: var(--muted);}
.proof-card {border-radius: 12px; background: var(--panel); padding: .9rem; min-height: 108px; box-shadow: 0 4px 20px rgba(16,42,42,.05);}
.proof-card .p-num {font-size: 1.45rem; font-weight: 780; color: var(--ink); line-height: 1.1; font-variant-numeric: tabular-nums;}
.proof-card .p-label {font-size: .75rem; color: var(--muted); margin-top: .25rem;}
.note, .source-box {border-radius: 12px; padding: .82rem .92rem; font-size: .82rem; line-height: 1.65; color: var(--ink-soft); background: #edf3f0;}
.source-box {background: transparent; border: 1px dashed var(--line-strong);}

[data-testid="stMetric"] {background: var(--panel); border: 0; border-radius: 12px; padding: .78rem .82rem; box-shadow: 0 4px 20px rgba(16,42,42,.055); min-height: 96px;}
[data-testid="stMetricLabel"] {font-size: .74rem; color: var(--muted);}
[data-testid="stMetricValue"] {font-size: 1.34rem; color: var(--ink); font-weight: 760; font-variant-numeric: tabular-nums;}
[data-testid="stMetricDelta"] {font-size: .72rem;}
.stButton > button, .stDownloadButton > button {min-height: 42px; border-radius: 10px; font-weight: 680; border-color: var(--line-strong); transition: transform .16s ease, box-shadow .16s ease, background-color .16s ease;}
.stButton > button:hover, .stDownloadButton > button:hover {border-color: var(--brand); color: var(--brand-strong); transform: translateY(-1px); box-shadow: 0 7px 18px rgba(8,127,91,.12);}
.stButton > button[kind="primary"] {background: var(--brand); border-color: var(--brand); color: white;}
.stButton > button[kind="primary"]:hover {background: var(--brand-strong); color: white;}
.stButton > button:disabled {transform: none; box-shadow: none; opacity: .55;}
[data-baseweb="select"] > div, [data-testid="stNumberInput"] input, [data-testid="stTextInput"] input {border-radius: 10px !important; border-color: var(--line-strong) !important; background: var(--panel) !important;}
[data-testid="stSlider"] [role="slider"] {background: var(--brand) !important; border-color: white !important; box-shadow: 0 0 0 2px var(--brand) !important;}
[data-testid="stDataFrame"] {border: 0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 22px rgba(16,42,42,.055);}
[data-testid="stPlotlyChart"] {background: var(--panel); border-radius: var(--radius); padding: .35rem; box-shadow: 0 5px 24px rgba(16,42,42,.05);}
[data-testid="stExpander"] {border-color: var(--line) !important; border-radius: 12px !important; background: rgba(255,255,255,.55); overflow: hidden;}
[data-testid="stAlert"] {border-radius: 12px; border: 0;}
[data-baseweb="tab-list"] {gap: .3rem; border-bottom: 1px solid var(--line);}
[data-baseweb="tab"] {height: 2.7rem; border-radius: 9px 9px 0 0; padding: 0 .9rem; color: var(--muted);}
[data-baseweb="tab"][aria-selected="true"] {color: var(--brand-strong); font-weight: 700; background: var(--brand-soft);}
[data-baseweb="tab-highlight"] {background-color: var(--brand) !important;}
[data-testid="stProgress"] > div > div > div {background-color: var(--brand);}

@media (max-width: 1100px) {
  .signal-strip {grid-template-columns: repeat(2, minmax(0, 1fr));}
  .block-container {padding-left: 1.4rem; padding-right: 1.4rem;}
}
@media (max-width: 640px) {
  .block-container {padding: 4.5rem 1rem 3rem;}
  .hero-title {font-size: 1.8rem;}
  .hero-sub {font-size: .9rem; line-height: 1.62;}
  .signal-strip {grid-template-columns: 1fr; gap: .55rem;}
  .node-grid {grid-template-columns: 1fr auto;}
  .decision {padding: .9rem .95rem;}
  [data-testid="stMetric"] {min-height: 88px;}
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important;}
}
</style>
"""


PLOTLY_CONFIG = {
    "displayModeBar": False,
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": False,
}


def page_header(title: str, subtitle: str, meta: list[tuple[str, str]] | None = None):
    meta = meta or [("Web 原型", "blue"), ("公开参数校准 · 情景仿真", "")]
    pills = "".join(
        f'<span class="meta-pill {html.escape(cls)}">{html.escape(label)}</span>'
        for label, cls in meta
    )
    st.markdown(
        f'<header class="page-head"><div class="hero-title">{html.escape(title)}</div>'
        f'<div class="hero-sub">{html.escape(subtitle)}</div>'
        f'<div class="meta-row">{pills}</div></header>',
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
        font=dict(family="Aptos, Microsoft YaHei UI, sans-serif", color="#294544", size=12),
        colorway=["#087f5b", "#d28a2e", "#2f6f8f", "#8d6b9f", "#69a653", "#c85555"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
        margin=dict(l=24, r=24, t=56, b=24),
        title=dict(font=dict(size=15, color="#102a2a"), x=0.01, xanchor="left"),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor="#c7d5cf", font_size=12, font_color="#102a2a"),
        hovermode="closest",
    )
    if height:
        layout["height"] = height
    if legend_horizontal:
        layout["legend"] = dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            title_text="", font=dict(size=11, color="#506965"),
        )
    fig.update_layout(**layout)
    fig.update_xaxes(
        showgrid=False, linecolor="#dce5e1", tickfont=dict(color="#647674"),
        title_font=dict(color="#506965"), automargin=True,
    )
    fig.update_yaxes(
        gridcolor="#edf2ef", zerolinecolor="#c7d5cf", tickfont=dict(color="#647674"),
        title_font=dict(color="#506965"), automargin=True,
    )
    return fig
