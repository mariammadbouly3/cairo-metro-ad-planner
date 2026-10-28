import pandas as pd
import plotly.express as px
import streamlit as st

import common as cm
from common import T

cm.header(T("لوحة المؤشرات", "Dashboard"),
          T("إيرادات الإعلانات والإشغال في المترو، بتتحدّث لوحدها من قاعدة البيانات.",
            "Metro advertising revenue and occupancy, updated live from the database."))


@st.fragment(run_every="60s")
def live_dashboard():
    d = cm.data()
    profile, spaces, campaigns = d["profile"], d["spaces"], d["campaigns"]
    bk_all = d["bookings"]
    bk = cm.active_bookings(bk_all)
    EGP = T("جنيه", "EGP")

    t = f"{cm.now():%H:%M}"
    cm.html(f'<span class="live">{T(f"آخر تحديث {t}، وبتتحدّث كل دقيقة", f"Last update {t}, refreshes every minute")}</span>')

    c1, c2 = st.columns([1, 3])
    with c1:
        years = sorted(bk["start_date"].dt.year.unique().tolist()) or [cm.today().year]
        year = st.selectbox(T("السنة", "Year"), years, index=len(years) - 1)
    with c2:
        if st.button(T("🔄 تحديث دلوقتي", "🔄 Refresh now")):
            cm.refresh()
            st.rerun(scope="fragment")

    today = pd.Timestamp(cm.today())
    ybk = bk[bk["start_date"].dt.year == year]
    prev = bk[bk["start_date"].dt.year == year - 1]["price_egp"].sum()
    rev = ybk["price_egp"].sum()
    growth = (f"{(rev - prev) / prev:+.0%} {T('عن', 'vs')} {year - 1}") if prev else T("أول سنة", "first year")

    active = spaces[spaces["is_active"].astype(bool)]
    booked_now = bk[(bk["start_date"] <= today) & (bk["end_date"] >= today)]["ad_space_id"].nunique()
    occ = booked_now / len(active) if len(active) else 0
    live_campaigns = campaigns[(campaigns["start_date"] <= today) & (campaigns["end_date"] >= today)]["campaign_id"].nunique()
    pending = (bk_all["status"] == "pending").sum()

    cm.kpis([
        (cm.short_egp(rev), T(f"إيرادات {year} ({growth})", f"Revenue {year} ({growth})")),
        (f"{occ:.0%}", T(f"إشغال النهارده ({booked_now} من {len(active)} مكان)",
                         f"Occupied today ({booked_now} of {len(active)} spaces)")),
        (f"{live_campaigns}", T("حملة شغالة دلوقتي", "Campaigns running now")),
        (f"{ybk['campaign_id'].nunique()}", T(f"حملة في {year}", f"Campaigns in {year}")),
        (f"{pending}", T("حجز من الموقع مستني المراجعة", "Web bookings awaiting review")),
    ], accent_first=True)

    # ---- monthly revenue
    with st.container(border=True):
        st.markdown(T("#### الإيرادات الشهرية", "#### Monthly revenue"))
        m = ybk.groupby(ybk["start_date"].dt.month)["price_egp"].sum().reindex(range(1, 13), fill_value=0).reset_index()
        m.columns = ["month", "revenue"]
        m["m"] = m["month"].map(cm.month)
        fig = px.bar(m, x="m", y="revenue", labels={"revenue": f"{T('الإيراد', 'Revenue')} ({EGP})", "m": T("الشهر", "Month")},
                     color_discrete_sequence=[cm.L1])
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(cm.style_fig(fig, 340), use_container_width=True)

    # ---- joins for the breakdowns
    j = (ybk.merge(spaces[["ad_space_id", "station_id", "format_l"]], on="ad_space_id")
            .merge(profile[["station_id", "name_l", "lines", "tier_l"]], on="station_id")
            .merge(campaigns[["campaign_id", "company_name", "industry"]], on="campaign_id"))

    a, b = st.columns(2)
    with a, st.container(border=True):
        st.markdown(T("#### الإيراد حسب الخط", "#### Revenue by line"))
        jl = j.assign(line=j["lines"].str.split("/")).explode("line")
        byl = jl.groupby("line", as_index=False)["price_egp"].sum()
        byl["l"] = byl["line"].map(lambda x: cm.lbl("line", x))
        pie = px.pie(byl, names="l", values="price_egp", hole=.6, color="l", color_discrete_map=cm.line_colors())
        st.plotly_chart(cm.style_fig(pie, 330), use_container_width=True)
        cm.html(f'<p class="note">{T("محطات التحويل بتتحسب على كل خط بتخدمه.", "Interchange stations count on every line they serve.")}</p>')
    with b, st.container(border=True):
        st.markdown(T("#### الإيراد حسب نوع الإعلان", "#### Revenue by ad format"))
        byf = j.groupby("format_l", as_index=False)["price_egp"].sum().sort_values("price_egp")
        fb = px.bar(byf, x="price_egp", y="format_l", orientation="h", labels={"price_egp": EGP, "format_l": ""},
                    color_discrete_sequence=[cm.L3])
        fb.update_yaxes(side=cm.y_side())
        st.plotly_chart(cm.style_fig(fb, 330), use_container_width=True)

    a, b = st.columns(2)
    with a, st.container(border=True):
        st.markdown(T("#### أعلى 10 محطات في الإيراد", "#### Top 10 stations by revenue"))
        bys = j.groupby(["name_l", "tier_l"], as_index=False)["price_egp"].sum().nlargest(10, "price_egp").sort_values("price_egp")
        sb = px.bar(bys, x="price_egp", y="name_l", color="tier_l", orientation="h", color_discrete_map=cm.tier_colors(),
                    labels={"price_egp": EGP, "name_l": "", "tier_l": T("الفئة", "Tier")})
        sb.update_yaxes(side=cm.y_side())
        st.plotly_chart(cm.style_fig(sb, 380), use_container_width=True)
    with b, st.container(border=True):
        st.markdown(T("#### أعلى المعلنين صرفًا", "#### Top advertisers by spend"))
        bya = j.groupby(["company_name", "industry"], as_index=False)["price_egp"].sum().nlargest(10, "price_egp")
        c_adv, c_ind, c_spend = T("المعلن", "Advertiser"), T("المجال", "Industry"), T("الصرف", "Spend")
        st.dataframe(pd.DataFrame({c_adv: bya["company_name"], c_ind: bya["industry"].map(lambda x: cm.lbl("ind", x)),
                                   c_spend: bya["price_egp"]}),
                     hide_index=True, use_container_width=True,
                     column_config={c_spend: st.column_config.ProgressColumn(
                         format="%d", min_value=0, max_value=float(bya["price_egp"].max() or 1))})

    # ---- bookings ending soon (renewal opportunities)
    with st.container(border=True):
        st.markdown(T("#### حجوزات بتخلص خلال 30 يوم", "#### Bookings ending in the next 30 days"))
        soon = bk[(bk["end_date"] >= today) & (bk["end_date"] <= today + pd.Timedelta(days=30))]
        soon = (soon.merge(spaces[["ad_space_id", "station_id", "format_l"]], on="ad_space_id")
                    .merge(profile[["station_id", "name_l"]], on="station_id")
                    .merge(campaigns[["campaign_id", "company_name"]], on="campaign_id").sort_values("end_date"))
        if soon.empty:
            st.markdown(T("مفيش حجوزات بتخلص الشهر ده.", "No bookings end this month."))
        else:
            c_val = T("القيمة", "Value")
            st.dataframe(pd.DataFrame({
                T("بينتهي", "Ends"): soon["end_date"].dt.strftime("%d/%m/%Y"), T("المحطة", "Station"): soon["name_l"],
                T("نوع الإعلان", "Format"): soon["format_l"], T("المعلن", "Advertiser"): soon["company_name"],
                c_val: soon["price_egp"]}),
                hide_index=True, use_container_width=True, column_config={c_val: st.column_config.NumberColumn(format="%d")})
            cm.html(f'<p class="note">{T("دي فرص تجديد: كلّم المعلن قبل ما المكان يفضى.", "Renewal opportunities: contact the advertiser before the space frees up.")}</p>')


live_dashboard()
