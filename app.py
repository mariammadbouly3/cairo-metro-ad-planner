"""Cairo Metro Ad Planner / مخطط إعلانات مترو القاهرة - entry point.

Run locally:   streamlit run app.py   (or double-click run_app.bat)
Cloud:         Streamlit Community Cloud with DATABASE_URL and ADMIN_PASSWORD in the app secrets.
Language:      Arabic by default; add ?lang=en to the link for English.
"""
import streamlit as st

import common as cm
from common import T

st.set_page_config(page_title=T("مخطط إعلانات مترو القاهرة", "Cairo Metro Ad Planner"), page_icon="🚇",
                   layout="wide", initial_sidebar_state="auto")
cm.inject_style()


def page_file(name):
    """Pages live in views/ on the laptop, but next to app.py in the GitHub repo. Support both."""
    nested = cm.HERE / "views" / name
    return str(nested if nested.exists() else cm.HERE / name)


pages = [
    st.Page(page_file("dashboard.py"), title=T("لوحة المؤشرات", "Dashboard"), icon="📊", default=True),
    st.Page(page_file("planner.py"), title=T("خطّط واحجز", "Plan & book"), icon="📋"),
    st.Page(page_file("network.py"), title=T("شبكة المترو", "Network"), icon="🗺️"),
    st.Page(page_file("station.py"), title=T("تفاصيل محطة", "Station"), icon="🔎"),
    st.Page(page_file("prices.py"), title=T("الأسعار", "Prices"), icon="💰"),
    st.Page(page_file("admin.py"), title=T("الإدارة", "Admin"), icon="🔐"),
]
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
