import datetime as dt

import pandas as pd
import plotly.express as px
import streamlit as st

import common as cm

cm.header("لوحة المؤشرات", "إيرادات الإعلانات والإشغال في المترو، بتتحدّث لوحدها من قاعدة البيانات.")


@st.fragment(run_every="60s")
def live_dashboard():
    d = cm.data()
    profile, spaces, campaigns = d["profile"], d["spaces"], d["campaigns"]
    bk_all = d["bookings"]
    bk = cm.active_bookings(bk_all)

    cm.html(f'<span class="live">آخر تحديث {cm.now():%H:%M}، وبتتحدّث كل دقيقة</span>')

    c1, c2 = st.columns([1, 3])
    with c1:
        years = sorted(bk["start_date"].dt.year.unique().tolist()) or [cm.today().year]
        year = st.selectbox("السنة", years, index=len(years) - 1)
    with c2:
        if st.button("🔄 تحديث دلوقتي"):
            cm.refresh()
            st.rerun(scope="fragment")

    today = pd.Timestamp(cm.today())
    ybk = bk[bk["start_date"].dt.year == year]
    prev = bk[bk["start_date"].dt.year == year - 1]["price_egp"].sum()
    rev = ybk["price_egp"].sum()
    growth = f"{(rev - prev) / prev:+.0%} عن {year - 1}" if prev else "أول سنة"

    active = spaces[spaces["is_active"].astype(bool)]
    booked_now = bk[(bk["start_date"] <= today) & (bk["end_date"] >= today)]["ad_space_id"].nunique()
    occ = booked_now / len(active) if len(active) else 0
    live_campaigns = campaigns[(campaigns["start_date"] <= today) & (campaigns["end_date"] >= today)]["campaign_id"].nunique()
    pending = (bk_all["status"] == "pending").sum()

    cm.kpis([
        (cm.short_egp(rev), f"إيرادات {year} ({growth})"),
        (f"{occ:.0%}", f"إشغال النهارده ({booked_now} من {len(active)} مكان)"),
        (f"{live_campaigns}", "حملة شغالة دلوقتي"),
        (f"{ybk['campaign_id'].nunique()}", f"حملة في {year}"),
        (f"{pending}", "حجز من الموقع مستني المراجعة"),
    ], accent_first=True)

    # ---- monthly revenue
    with st.container(border=True):
        st.markdown("#### الإيرادات الشهرية")
        m = ybk.groupby(ybk["start_date"].dt.month)["price_egp"].sum().reindex(range(1, 13), fill_value=0).reset_index()
        m.columns = ["month", "revenue"]
        m["الشهر"] = m["month"].map(lambda i: cm.MONTHS_AR[i - 1])
        fig = px.bar(m, x="الشهر", y="revenue", labels={"revenue": "الإيراد (جنيه)"}, color_discrete_sequence=[cm.L1])
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(cm.style_fig(fig, 340), use_container_width=True)

    # ---- joins for the breakdowns
    j = (ybk.merge(spaces[["ad_space_id", "station_id", "format_ar"]], on="ad_space_id")
            .merge(profile[["station_id", "name_ar", "lines", "tier_ar"]], on="station_id")
            .merge(campaigns[["campaign_id", "company_name", "industry"]], on="campaign_id"))

    a, b = st.columns(2)
    with a, st.container(border=True):
        st.markdown("#### الإيراد حسب الخط")
        jl = j.assign(line=j["lines"].str.split("/")).explode("line")
        byl = jl.groupby("line", as_index=False)["price_egp"].sum()
        byl["الخط"] = byl["line"].map(cm.AR_LINE)
        pie = px.pie(byl, names="الخط", values="price_egp", hole=.6, color="الخط",
                     color_discrete_map={cm.AR_LINE[k]: v for k, v in cm.LINE_COLORS.items()})
        st.plotly_chart(cm.style_fig(pie, 330), use_container_width=True)
        cm.html('<p class="note">محطات التحويل بتتحسب على كل خط بتخدمه.</p>')
    with b, st.container(border=True):
        st.markdown("#### الإيراد حسب نوع الإعلان")
        byf = j.groupby("format_ar", as_index=False)["price_egp"].sum().sort_values("price_egp")
        fb = px.bar(byf, x="price_egp", y="format_ar", orientation="h", labels={"price_egp": "جنيه", "format_ar": ""},
                    color_discrete_sequence=[cm.L3])
        fb.update_yaxes(side="right")
        st.plotly_chart(cm.style_fig(fb, 330), use_container_width=True)

    a, b = st.columns(2)
    with a, st.container(border=True):
        st.markdown("#### أعلى 10 محطات في الإيراد")
        bys = j.groupby(["name_ar", "tier_ar"], as_index=False)["price_egp"].sum().nlargest(10, "price_egp").sort_values("price_egp")
        sb = px.bar(bys, x="price_egp", y="name_ar", color="tier_ar", orientation="h", color_discrete_map=cm.TIER_COLORS,
                    labels={"price_egp": "جنيه", "name_ar": "", "tier_ar": "الفئة"})
        sb.update_yaxes(side="right")
        st.plotly_chart(cm.style_fig(sb, 380), use_container_width=True)
    with b, st.container(border=True):
        st.markdown("#### أعلى المعلنين صرفًا")
        bya = j.groupby(["company_name", "industry"], as_index=False)["price_egp"].sum().nlargest(10, "price_egp")
        bya["المجال"] = bya["industry"].map(lambda x: cm.AR_IND.get(x, x))
        st.dataframe(pd.DataFrame({"المعلن": bya["company_name"], "المجال": bya["المجال"], "الصرف": bya["price_egp"]}),
                     hide_index=True, use_container_width=True,
                     column_config={"الصرف": st.column_config.ProgressColumn(
                         format="%d", min_value=0, max_value=float(bya["price_egp"].max() or 1))})

    # ---- bookings ending soon (renewal opportunities)
    with st.container(border=True):
        st.markdown("#### حجوزات بتخلص خلال 30 يوم")
        soon = bk[(bk["end_date"] >= today) & (bk["end_date"] <= today + pd.Timedelta(days=30))]
        soon = (soon.merge(spaces[["ad_space_id", "station_id", "format_ar"]], on="ad_space_id")
                    .merge(profile[["station_id", "name_ar"]], on="station_id")
                    .merge(campaigns[["campaign_id", "company_name"]], on="campaign_id").sort_values("end_date"))
        if soon.empty:
            st.markdown("مفيش حجوزات بتخلص الشهر ده.")
        else:
            st.dataframe(pd.DataFrame({
                "بينتهي": soon["end_date"].dt.strftime("%d/%m/%Y"), "المحطة": soon["name_ar"], "نوع الإعلان": soon["format_ar"],
                "المعلن": soon["company_name"], "القيمة": soon["price_egp"]}),
                hide_index=True, use_container_width=True, column_config={"القيمة": st.column_config.NumberColumn(format="%d")})
            cm.html('<p class="note">دي فرص تجديد: كلّم المعلن قبل ما المكان يفضى.</p>')


live_dashboard()
