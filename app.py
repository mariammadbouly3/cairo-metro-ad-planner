"""Cairo Metro Ad Planner / مخطط إعلانات مترو القاهرة - entry point.

Run locally:   streamlit run app.py   (or double-click run_app.bat)
Cloud:         Streamlit Community Cloud with DATABASE_URL and ADMIN_PASSWORD in the app secrets.
Language:      Arabic by default; add ?lang=en to the link for English.
"""
import streamlit as st

import common as cm
from common import T

ICON = next((str(p) for p in (cm.HERE / "assets" / "icon.png", cm.HERE / "icon.png") if p.exists()), "🚇")
st.set_page_config(page_title=T("مخطط إعلانات مترو القاهرة", "Cairo Metro Ad Planner"), page_icon=ICON,
                   layout="wide", initial_sidebar_state="auto")
cm.inject_style()
cm.home_screen_icon()


def page_file(name):
    """Pages live in views/ on the laptop, but next to app.py in the GitHub repo. Support both."""
    nested = cm.HERE / "views" / name
    return str(nested if nested.exists() else cm.HERE / name)


PAGE_LIST = [  # file, arabic title, english title, icon
    ("dashboard.py", "لوحة المؤشرات", "Dashboard", "📊"),
    ("planner.py", "خطّط واحجز", "Plan & book", "📋"),
    ("request.py", "اطلب مكان", "Request a space", "🙋"),
    ("insights.py", "تحليلات", "Insights", "🔬"),
    ("forecast.py", "التوقعات", "Forecasts", "📈"),
    ("network.py", "شبكة المترو", "Network", "🗺️"),
    ("station.py", "تفاصيل محطة", "Station", "🔎"),
    ("prices.py", "الأسعار", "Prices", "💰"),
    ("admin.py", "الإدارة", "Admin", "🔐"),
]
pages = []
for i, (f, ar, en, icon) in enumerate(PAGE_LIST):
    pg = st.Page(page_file(f), title=T(ar, en), icon=icon, default=i == 0)
    cm.PAGES[f] = pg
    pages.append(pg)
try:
    nav = st.navigation(pages, position="top")
except TypeError:  # older Streamlit without top navigation
    nav = st.navigation(pages)

title = T("مخطط إعلانات مترو القاهرة", "Cairo Metro Ad Planner")
if not cm.database_url():
    cm.local_connect_form()
    cm.header(title, T("اتصل بقاعدة البيانات الأول.", "Connect to the database first."))
    st.info(T("اكتب كلمة مرور PostgreSQL في القائمة الجانبية واضغط **اتصال**. لو التطبيق شغال على Streamlit Cloud، "
              "ضيف DATABASE_URL في الـ Secrets بدل كده.",
              "Enter the PostgreSQL password in the sidebar and press **Connect**. On Streamlit Cloud, add "
              "DATABASE_URL to the app secrets instead."))
    st.stop()

try:
    cm.data()
except Exception as e:  # noqa: BLE001
    cm.local_connect_form()
    cm.header(title, T("تعذّر الاتصال بقاعدة البيانات.", "Could not reach the database."))
    st.error(T("اتأكد إن بيانات الاتصال صح وإن قاعدة البيانات شغالة.", "Check the connection details and that the database is running.")
             + f"\n\n{e}")
    st.stop()

nav.run()
