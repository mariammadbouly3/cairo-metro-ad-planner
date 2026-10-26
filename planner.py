import datetime as dt

import pandas as pd
import plotly.express as px
import streamlit as st

import common as cm
import writes
from recommender import AUDIENCES, INDUSTRY_AUDIENCE, recommend

d = cm.data()
profile, spaces, bookings = d["profile"], d["spaces"], cm.active_bookings(d["bookings"])

cm.header("خطّط حملتك واحجزها",
          "اختار الجمهور والميزانية والمدة، والمخطط يرشّح لك أحسن أماكن فاضية، وتقدر تحجزها على طول. "
          "الأسعار شهرية قبل ضريبة القيمة المضافة 14%.")

with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        industry = st.selectbox("مجال الشركة", ["—"] + list(INDUSTRY_AUDIENCE),
                                format_func=lambda x: "اختار المجال" if x == "—" else cm.AR_IND.get(x, x))
        audiences = st.multiselect("الجمهور المستهدف", AUDIENCES, default=INDUSTRY_AUDIENCE.get(industry, []),
                                   format_func=lambda x: cm.AR_AUD.get(x, x), placeholder="كل الجماهير",
                                   help="بيتملا تلقائي حسب المجال. سيبه فاضي لو عايز توصل لكل الناس.")
    with c2:
        budget = st.number_input("الميزانية الكلية (جنيه)", min_value=10_000, max_value=50_000_000,
                                 value=500_000, step=50_000, format="%d")
        months = st.slider("مدة الحملة (شهور)", 1, 6, 2)
        next_month = (cm.today().replace(day=1) + dt.timedelta(days=32)).replace(day=1)
        start = st.date_input("تاريخ البداية", next_month, min_value=cm.today(), format="DD/MM/YYYY")
    with c3:
        lines = st.multiselect("الخطوط", ["L1", "L2", "L3"], format_func=cm.AR_LINE.get, placeholder="كل الخطوط")
        fmt_names = spaces.drop_duplicates("format_name").set_index("format_name")["format_ar"].to_dict()
        formats = st.multiselect("أنواع الإعلانات", sorted(fmt_names), format_func=lambda x: fmt_names.get(x, x),
                                 placeholder="كل الأنواع")
        max_per_station = st.slider("أقصى عدد أماكن في المحطة الواحدة", 1, 5, 2)

plan = recommend(profile, spaces, bookings, audiences, float(budget), start, months,
                 lines or None, formats or None, max_per_station)

if plan.spaces.empty:
    st.warning("مفيش أماكن فاضية تناسب الميزانية والاختيارات دي. جرّب تزوّد الميزانية، أو تقلّل مدة الحملة، "
               "أو تشيل بعض الفلاتر، أو تغيّر التاريخ.")
    st.stop()

cm.kpis([
    (cm.short_egp(plan.total_cost), f"تكلفة الخطة ({plan.total_cost / budget:.0%} من الميزانية)"),
    (len(plan.stations), "محطة"),
    (len(plan.spaces), "مكان إعلاني"),
    (f"{plan.impressions / 1e6:,.1f} مليون", "مشاهدة متوقعة من الركاب"),
    (f"{plan.cpm:,.2f} جنيه", "تكلفة الوصول لكل 1000 راكب"),
], accent_first=True)

m1, m2 = st.columns([1.35, 1])
with m1, st.container(border=True):
    st.markdown("#### المحطات اللي في الخطة")
    mp = profile.dropna(subset=["latitude"]).copy()
    chosen = set(plan.stations["station_id"])
    mp["الحالة"] = mp["station_id"].isin(chosen).map({True: "في الخطة", False: "محطات أخرى"})
    mp["size"] = mp["الحالة"].map({"في الخطة": 15, "محطات أخرى": 5})
    fig = px.scatter_map(
        mp, lat="latitude", lon="longitude", color="الحالة", size="size", size_max=15,
        hover_name="name_ar", hover_data={"lines_ar": True, "tier_ar": True, "avg_daily_riders": ":,",
                                          "size": False, "latitude": False, "longitude": False, "الحالة": False},
        labels={"lines_ar": "الخطوط", "tier_ar": "الفئة", "avg_daily_riders": "ركاب يوميًا"},
        color_discrete_map={"في الخطة": cm.GOLD, "محطات أخرى": "#6C7891"},
        zoom=10.2, center={"lat": 30.06, "lon": 31.27}, map_style="carto-darkmatter",
    )
    st.plotly_chart(cm.style_fig(fig, 440), use_container_width=True)
    missing = int(plan.stations["latitude"].isna().sum())
    if missing:
        cm.html(f'<p class="note">{missing} محطة في الخطة مالهاش إحداثيات منشورة، فمش ظاهرة على الخريطة.</p>')
with m2, st.container(border=True):
    st.markdown("#### التكلفة حسب المحطة")
    sb = plan.stations.head(12).copy()
    sb["الفئة"] = sb["tier"].map(cm.AR_TIER)
    bar = px.bar(sb.sort_values("cost"), x="cost", y="name_ar", orientation="h", color="الفئة",
                 color_discrete_map=cm.TIER_COLORS, labels={"cost": "التكلفة (جنيه)", "name_ar": ""})
    bar.update_yaxes(side="right")
    st.plotly_chart(cm.style_fig(bar, 440), use_container_width=True)

with st.container(border=True):
    st.markdown("#### الأماكن الإعلانية المقترحة")
    show = pd.DataFrame({
        "الأولوية": plan.spaces["priority"],
        "المحطة": plan.spaces["name_ar"],
        "الخطوط": plan.spaces["lines"].map(cm.ar_lines),
        "الفئة": plan.spaces["tier"].map(cm.AR_TIER),
        "نوع الإعلان": plan.spaces["format_ar"],
        "المكان": plan.spaces["zone"].map(cm.AR_ZONE),
        "السعر الشهري": plan.spaces["monthly_price_egp"],
        "التكلفة الكلية": plan.spaces["cost"],
        "ركاب يوميًا": plan.spaces["avg_daily_riders"],
        "تطابق الجمهور": plan.spaces["audience_fit"],
        "أساس السعر": plan.spaces["price_basis"].map(cm.AR_BASIS),
    })
    st.dataframe(show, hide_index=True, use_container_width=True, column_config={
        "السعر الشهري": st.column_config.NumberColumn(format="%d"),
        "التكلفة الكلية": st.column_config.NumberColumn(format="%d"),
        "ركاب يوميًا": st.column_config.NumberColumn(format="%d"),
        "تطابق الجمهور": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
    })
    st.download_button("⬇️ تحميل الخطة (CSV)", show.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"metro_ad_plan_{start}.csv", mime="text/csv")

# ---------------------------------------------------------------- booking
end = start + dt.timedelta(days=30 * months - 1)
with st.form("book"):
    st.markdown("#### احجز الخطة دي")
    st.markdown(f'<p class="note">هيتحجز {len(plan.spaces)} مكان من {start:%d/%m/%Y} لحد {end:%d/%m/%Y} '
                f'بإجمالي {cm.short_egp(plan.total_cost)}. الحجز بيتسجّل "في انتظار المراجعة" لحد ما الإدارة توافق عليه، '
                'والأماكن بتتقفل عليك من دلوقتي.</p>', unsafe_allow_html=True)
    f1, f2 = st.columns(2)
    company = f1.text_input("اسم الشركة")
    campaign_name = f2.text_input("اسم الحملة", value=f"حملة {cm.MONTHS_AR[start.month - 1]} {start.year}")
    ind_choice = f1.selectbox("المجال", list(INDUSTRY_AUDIENCE), index=list(INDUSTRY_AUDIENCE).index(industry)
                              if industry in INDUSTRY_AUDIENCE else 0, format_func=lambda x: cm.AR_IND.get(x, x))
    agree = f2.checkbox("راجعت الأماكن والأسعار وموافق على الحجز")
    submitted = st.form_submit_button("احجز الخطة", type="primary", use_container_width=True)

if submitted:
    if not company.strip() or not campaign_name.strip():
        st.error("اكتب اسم الشركة واسم الحملة.")
    elif not agree:
        st.error("علّم على خانة الموافقة الأول.")
    else:
        items = list(zip(plan.spaces["ad_space_id"], plan.spaces["cost"]))
        audience = ", ".join(audiences) if audiences else "All"
        try:
            cid = writes.book_plan(cm.engine(), company, ind_choice, campaign_name, audience, float(budget),
                                   start, end, items, status="pending")
        except writes.BookingConflict:
            cm.refresh()
            st.error("مكان أو أكتر من الخطة اتحجز من حد تاني دلوقتي. حدّثت البيانات، اضغط احجز تاني على الخطة الجديدة.")
        else:
            cm.refresh()
            st.success(f"اتحجزت الحملة رقم {cid} ({len(items)} مكان). هتظهر في لوحة المؤشرات وفي صفحة الإدارة للمراجعة.")
