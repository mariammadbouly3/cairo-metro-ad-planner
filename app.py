"""مخطط إعلانات مترو القاهرة - entry point.

Run locally:   streamlit run app.py   (or double-click run_app.bat)
Cloud:         Streamlit Community Cloud with DATABASE_URL and ADMIN_PASSWORD in the app secrets.
"""
import streamlit as st

import common as cm

st.set_page_config(page_title="مخطط إعلانات مترو القاهرة", page_icon="🚇", layout="wide",
                   initial_sidebar_state="collapsed")
cm.inject_style()

pages = [
    st.Page("views/dashboard.py", title="لوحة المؤشرات", icon="📊", default=True),
    st.Page("views/planner.py", title="خطّط واحجز", icon="📋"),
    st.Page("views/network.py", title="شبكة المترو", icon="🗺️"),
    st.Page("views/station.py", title="تفاصيل محطة", icon="🔎"),
    st.Page("views/prices.py", title="الأسعار", icon="💰"),
    st.Page("views/admin.py", title="الإدارة", icon="🔐"),
]
try:
    nav = st.navigation(pages, position="top")
except TypeError:  # older Streamlit without top navigation
    nav = st.navigation(pages)

if not cm.database_url():
    cm.local_connect_form()
    cm.header("مخطط إعلانات مترو القاهرة", "اتصل بقاعدة البيانات الأول.")
    st.info("اكتب كلمة مرور PostgreSQL في القائمة الجانبية (السهم اللي فوق على اليمين) واضغط **اتصال**.")
    st.stop()

try:
    cm.data()
except Exception as e:  # noqa: BLE001
    cm.local_connect_form()
    cm.header("مخطط إعلانات مترو القاهرة", "تعذّر الاتصال بقاعدة البيانات.")
    st.error(f"اتأكد إن بيانات الاتصال صح وإن قاعدة البيانات شغالة.\n\n{e}")
    st.stop()

nav.run()
