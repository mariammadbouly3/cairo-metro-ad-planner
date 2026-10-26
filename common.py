"""Shared pieces for every page: Arabic labels, style, database connection and data loading."""
from __future__ import annotations

import base64
import datetime as dt
import os
import re
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

HERE = Path(__file__).parent

# ---------------------------------------------------------------- palette (from the Power BI dashboard)
L1, L2, L3, INTER = "#2A78D6", "#E3572E", "#1B9E6B", "#6250D6"
NAVY, INK, MUTED = "#0E1630", "#F3F5FA", "#AEB7C8"
GOLD = "#F2C14E"
LINE_COLORS = {"L1": L1, "L2": L2, "L3": L3}
TIER_COLORS = {"مميزة": GOLD, "عالية": "#7FB3F0", "عادية": "#8E9AB3"}
FONT = "Readex Pro"

# ---------------------------------------------------------------- Arabic labels
AR_TIER = {"Premium": "مميزة", "High": "عالية", "Standard": "عادية"}
AR_AUD = {
    "Students": "الطلاب",
    "Upper-middle class": "الطبقة المتوسطة العليا",
    "Office workers & shoppers": "الموظفون والمتسوقون",
    "Commuters / intercity travellers": "الركاب اليوميون والمسافرون",
    "Mass-market shoppers": "المتسوقون (السوق العام)",
    "Tourists & visitors": "السياح والزوار",
    "Local residents (mass market)": "سكان المنطقة",
}
AR_IND = {
    "Telecom": "الاتصالات", "EdTech/courses": "التعليم والكورسات", "Fintech wallets": "المحافظ الإلكترونية",
    "Banks": "البنوك", "Real estate": "العقارات", "Cars": "السيارات", "Government awareness": "التوعية الحكومية",
    "FMCG": "السلع الاستهلاكية", "Retail & fashion": "الملابس والتجزئة", "Food delivery": "توصيل الطعام",
    "Ride-hailing": "تطبيقات التوصيل", "Tourism & hospitality": "السياحة والفنادق", "Local retail": "المحلات المحلية",
}
AR_ZONE = {"platform": "الرصيف", "concourse": "صالة المحطة", "entrance": "المدخل", "stairs": "السلالم", "exit": "المخرج"}
AR_LINE = {"L1": "الخط الأول", "L2": "الخط الثاني", "L3": "الخط الثالث"}
AR_TYPE = {"underground": "تحت الأرض", "elevated": "علوية", "surface": "سطحية"}
AR_AREA = {"CBD": "وسط البلد / منطقة أعمال", "Commercial": "تجارية", "Upscale Residential": "سكنية راقية",
           "Dense Residential": "سكنية مزدحمة", "Suburban": "أطراف المدينة", "Industrial": "صناعية"}
AR_GOV = {"Cairo": "القاهرة", "Giza": "الجيزة", "Qalyubia": "القليوبية"}
AR_STATUS = {"confirmed": "مؤكد", "pending": "في انتظار المراجعة", "cancelled": "ملغي"}
AR_BASIS = {"published": "سعر سوق منشور", "estimate": "تقدير"}
MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]


CAIRO = ZoneInfo("Africa/Cairo")


def now():
    """Cairo time, also on the cloud server (which runs on UTC)."""
    return dt.datetime.now(CAIRO)


def today():
    return now().date()


def ar_lines(s):
    return " و".join(AR_LINE.get(x, x) for x in str(s).split("/"))


def ar_list(s, mapping):
    return "، ".join(mapping.get(x.strip(), x.strip()) for x in str(s).split(","))


def short_egp(x):
    x = float(x or 0)
    if x >= 1e6:
        return f"{x / 1e6:,.2f} مليون جنيه"
    if x >= 1e3:
        return f"{x / 1e3:,.0f} ألف جنيه"
    return f"{x:,.0f} جنيه"


# ---------------------------------------------------------------- style
def html(markup: str):
    """Render raw HTML/CSS. Strips comments, indentation and blank lines so Markdown never shows it as text."""
    markup = re.sub(r"/\*.*?\*/", "", markup, flags=re.S)
    st.markdown("\n".join(line.strip() for line in markup.splitlines() if line.strip()), unsafe_allow_html=True)


def _bg_css():
    p = HERE / "assets" / "bg.jpg"
    if not p.exists():
        p = HERE / "bg.jpg"  # flat layout in the GitHub repo
    if not p.exists():
        return f"background:{NAVY};"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return (f"background: linear-gradient(rgba(8,12,28,.55), rgba(8,12,28,.82)), "
            f"url('data:image/jpeg;base64,{b64}') center/cover fixed;")


def inject_style():
    html(f"""
    <link href="https://fonts.googleapis.com/css2?family=Readex+Pro:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
    html, body, .stApp, [class*="st-"], button, input, textarea, select {{ font-family: '{FONT}', sans-serif !important; }}
    [data-testid="stIconMaterial"], .material-symbols-rounded, [class*="material-symbols"] {{ font-family: 'Material Symbols Rounded' !important; }}
    .stApp {{ direction: rtl; {_bg_css()} }}
    [data-testid="stHeader"] {{ background: rgba(8,12,28,.55); backdrop-filter: blur(10px); }}
    [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {{ display: none; }}
    .block-container {{ padding-top: 4.2rem; max-width: 1500px; }}
    h1, h2, h3, h4, p, label, li, .stMarkdown {{ text-align: right; }}
    /* sidebar */
    [data-testid="stSidebar"] > div:first-child {{ background: rgba(14,22,48,.94); border-left: 1px solid rgba(255,255,255,.12); }}
    [data-testid="stSidebar"] * {{ direction: rtl; }}
    /* top navigation */
    [data-testid="stTopNavLinkContainer"] a, [data-testid="stSidebarNavLink"] {{ border-radius: 999px; }}
    [data-testid="stTopNavLinkContainer"] a[aria-current="page"] {{ background: rgba(42,120,214,.85); }}
    /* glass panels */
    [data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{
        background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.20) !important;
        border-radius: 22px; backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
    }}
    [data-testid="stForm"] {{ background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.18); border-radius: 22px; }}
    /* widgets */
    [data-baseweb="select"] > div, [data-baseweb="input"] > div, .stDateInput input, .stNumberInput input, textarea {{
        background: rgba(9,14,32,.55) !important; border-color: rgba(255,255,255,.18) !important;
    }}
    [data-testid="stSlider"], [data-testid="stDataFrame"], [data-testid="stDataEditor"], .js-plotly-plot {{ direction: ltr; }}
    [data-baseweb="tag"] {{ background: {L1} !important; }}
    .stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {{
        border-radius: 999px; font-weight: 600; border: 1px solid rgba(255,255,255,.25);
    }}
    [data-baseweb="tab-list"] {{ gap: .4rem; flex-wrap: wrap; }}
    [data-baseweb="tab"] {{ background: rgba(255,255,255,.06); border-radius: 999px; padding: .45rem 1.1rem; font-weight: 500; }}
    [data-baseweb="tab"][aria-selected="true"] {{ background: rgba(42,120,214,.85); }}
    [data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {{ display: none; }}
    /* header strip */
    .route {{ display:flex; flex-direction:column; gap:.45rem; margin-bottom: 1.1rem; }}
    .route h1 {{ font-size: 2.5rem; font-weight: 700; margin: 0; line-height: 1.15; color: {INK}; padding: 0; }}
    .route p {{ color: {MUTED}; margin: 0; font-size: 1rem; max-width: 70ch; }}
    .bars {{ display:flex; gap:.45rem; align-items:center; margin:.1rem 0 .2rem; }}
    .bars span {{ height: 8px; border-radius: 99px; display:block; }}
    .bars i {{ font-style: normal; font-size: .82rem; color: {MUTED}; margin-inline-start:.35rem; }}
    /* KPI cards */
    .kpis {{ display:grid; grid-template-columns: repeat(var(--n,5), minmax(0,1fr)); gap: .8rem; margin: .4rem 0 1rem; }}
    .kpi {{ background: rgba(255,255,255,.09); border:1px solid rgba(255,255,255,.20); border-radius: 18px;
            padding: .9rem 1.1rem; backdrop-filter: blur(14px); }}
    .kpi b {{ display:block; font-size: 1.45rem; font-weight: 600; color: {INK}; line-height:1.3; }}
    .kpi small {{ color: {MUTED}; font-size: .85rem; }}
    .kpi.accent {{ border-color: {GOLD}; }}
    .station-card h3 {{ margin: 0 0 .2rem; font-size: 1.6rem; }}
    .chip {{ display:inline-block; padding:.15rem .7rem; border-radius:99px; font-size:.85rem; margin: 0 0 .3rem .3rem;
             background: rgba(255,255,255,.12); }}
    .note {{ color:{MUTED}; font-size:.85rem; }}
    .live {{ display:inline-flex; align-items:center; gap:.4rem; color:{MUTED}; font-size:.85rem; }}
    .live::before {{ content:""; width:8px; height:8px; border-radius:50%; background:{L3}; box-shadow:0 0 0 4px rgba(27,158,107,.25); }}
    /* phones */
    @media (max-width: 760px) {{
        .block-container {{ padding: 3.6rem .8rem 2rem; }}
        .route h1 {{ font-size: 1.75rem; }}
        .route p {{ font-size: .92rem; }}
        .kpis {{ grid-template-columns: repeat(2, minmax(0,1fr)) !important; gap: .55rem; }}
        .kpi {{ padding: .7rem .85rem; border-radius: 14px; }}
        .kpi b {{ font-size: 1.15rem; }}
        [data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{ border-radius: 16px; }}
    }}
    @media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; animation: none !important; }} }}
    </style>""")


def header(title: str, subtitle: str = ""):
    html(f"""
    <div class="route">
      <div class="bars">
        <span style="width:90px;background:{L1}"></span>
        <span style="width:60px;background:{L2}"></span>
        <span style="width:80px;background:{L3}"></span>
        <i>مترو القاهرة، 3 خطوط و84 محطة</i>
      </div>
      <h1>{title}</h1>
      {f'<p>{subtitle}</p>' if subtitle else ''}
    </div>""")


def kpis(items, n=None, accent_first=False):
    """items: list of (value, label)."""
    cells = "".join(
        f'<div class="kpi{" accent" if accent_first and i == 0 else ""}"><b>{v}</b><small>{lbl}</small></div>'
        for i, (v, lbl) in enumerate(items))
    html(f'<div class="kpis" style="--n:{n or len(items)}">{cells}</div>')


def style_fig(fig, height=None):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=INK, size=13), margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", y=1.1, x=1, xanchor="right", bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(font_family=FONT), title=dict(x=1, xanchor="right"),
    )
    if height:
        fig.update_layout(height=height)
    fig.update_xaxes(gridcolor="rgba(255,255,255,.08)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,.08)", zeroline=False)
    return fig


# ---------------------------------------------------------------- database
def _secret(name):
    try:
        return st.secrets.get(name)
    except Exception:  # noqa: BLE001  (no secrets.toml on a local run)
        return None


def database_url():
    """Cloud: DATABASE_URL in Streamlit secrets. Local: env var, or the sidebar form."""
    url = _secret("DATABASE_URL") or os.getenv("DATABASE_URL")
    if url:
        return url
    return st.session_state.get("local_url")


def admin_password():
    return _secret("ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD")


@st.cache_resource(show_spinner=False)
def get_engine(url: str):
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    eng = create_engine(url, pool_pre_ping=True, pool_recycle=300)
    with eng.connect() as c:
        c.execute(text("SELECT 1"))
    return eng


def local_connect_form():
    """Only shown when no DATABASE_URL is configured (running on the laptop)."""
    with st.sidebar:
        st.markdown("### 🔌 الاتصال بقاعدة البيانات")
        host = st.text_input("الخادم", os.getenv("PGHOST", "localhost"))
        port = st.text_input("المنفذ", os.getenv("PGPORT", "5432"))
        db = st.text_input("قاعدة البيانات", os.getenv("PGDATABASE", "cairo_metro_db"))
        user = st.text_input("اسم المستخدم", os.getenv("PGUSER", "postgres"))
        pw = st.text_input("كلمة المرور", os.getenv("PGPASSWORD", ""), type="password")
        if st.button("اتصال", type="primary", use_container_width=True):
            from urllib.parse import quote_plus
            st.session_state["local_url"] = f"postgresql://{quote_plus(user)}:{quote_plus(pw)}@{host}:{port}/{db}"
            st.rerun()


def engine():
    url = database_url()
    if not url:
        return None
    return get_engine(url)


def _floats(df):
    for col in df.columns:
        if df[col].dtype == object and df[col].dropna().map(lambda v: isinstance(v, Decimal)).any():
            df[col] = df[col].astype(float)
    return df


QUERIES = {
    "profile": "SELECT * FROM cairo_metro.station_ad_profile",
    "spaces": """SELECT a.ad_space_id, a.station_id, f.format_id, f.format_name,
                        COALESCE(f.name_ar, f.format_name) AS format_ar, f.price_basis, f.price_min, f.price_max,
                        f.price_source, f.is_digital, a.zone, a.width_m, a.height_m, a.monthly_price_egp, a.is_active
                 FROM cairo_metro.ad_spaces a JOIN cairo_metro.ad_formats f USING (format_id)""",
    "bookings": """SELECT b.booking_id, b.ad_space_id, b.campaign_id, b.start_date, b.end_date, b.price_egp,
                          COALESCE(b.status, 'confirmed') AS status, b.created_at
                   FROM cairo_metro.bookings b""",
    "campaigns": """SELECT c.campaign_id, c.campaign_name, c.target_audience, c.start_date, c.end_date, c.budget_egp,
                           a.advertiser_id, a.company_name, a.industry
                    FROM cairo_metro.campaigns c JOIN cairo_metro.advertisers a USING (advertiser_id)""",
    "line_order": """SELECT l.line_number, ls.stop_order, ls.branch, s.station_id, s.name_en, s.name_ar,
                            s.latitude, s.longitude
                     FROM cairo_metro.line_stations ls
                     JOIN cairo_metro.lines l USING (line_id)
                     JOIN cairo_metro.stations s USING (station_id)
                     ORDER BY l.line_number, ls.stop_order""",
}


@st.cache_data(ttl=60, show_spinner="جاري تحميل البيانات...")
def load_data(_eng, url_key: str):
    with _eng.connect() as c:
        out = {k: _floats(pd.read_sql(text(v), c)) for k, v in QUERIES.items()}
    p = out["profile"]
    p["tier_ar"] = p["tier"].map(AR_TIER)
    p["lines_ar"] = p["lines"].map(ar_lines)
    for col in ("start_date", "end_date"):
        out["bookings"][col] = pd.to_datetime(out["bookings"][col])
        out["campaigns"][col] = pd.to_datetime(out["campaigns"][col])
    return out


def data():
    eng = engine()
    return load_data(eng, str(hash(database_url())))


def refresh():
    """Call after any write so every page shows the change straight away."""
    load_data.clear()


def active_bookings(bk):
    return bk[bk["status"] != "cancelled"]
