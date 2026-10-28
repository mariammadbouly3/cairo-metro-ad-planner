import pandas as pd
import plotly.express as px
import streamlit as st

import common as cm
import models
from common import T

d = cm.data()
profile, spaces, campaigns = d["profile"], d["spaces"], d["campaigns"]
daily = cm.daily(d["bookings"])
EGP = T("جنيه", "EGP")
today = pd.Timestamp(cm.today())

cm.header(T("تحليلات الإشغال والمعلنين", "Occupancy and advertiser insights"),
          T("الإشغال بيتحسب بالأيام: كل حجز بيتوزّع على الأيام اللي شغال فيها فعلًا، والإيراد كمان.",
            "Occupancy is counted in days: each booking, and its revenue, is spread over the days it actually runs."))

window = st.radio(T("الفترة", "Period"), [12, 6, 3], horizontal=True,
                  format_func=lambda n: T(f"آخر {n} شهور" if n < 11 else f"آخر {n} شهر", f"Last {n} months"))
w_end = today.to_period("M").to_timestamp() - pd.Timedelta(days=1)  # end of last complete month
w_start = (w_end + pd.Timedelta(days=1)) - pd.DateOffset(months=window)
active = spaces[spaces["is_active"].astype(bool)]
occ = models.space_occupancy(daily, w_start, w_end)
sp = active.merge(profile[["station_id", "name_l", "tier", "tier_l", "lines"]], on="station_id")
sp["occupancy"] = sp["ad_space_id"].map(occ["occupancy"]).fillna(0)
sp["revenue"] = sp["ad_space_id"].map(occ["revenue"]).fillna(0)
months_in = window

idle = sp[sp["occupancy"] < .10]
win_rev = daily[(daily["day"] >= w_start) & (daily["day"] <= w_end)]
spend = win_rev.merge(campaigns[["campaign_id", "company_name", "industry"]], on="campaign_id")
top_share = (spend.groupby("company_name")["revenue"].sum().max() / spend["revenue"].sum()) if len(spend) else 0

cm.html(f'<p class="note">{T("من", "From")} {w_start:%d/%m/%Y} {T("لحد", "to")} {w_end:%d/%m/%Y}</p>')
cm.kpis([
    (f"{sp['occupancy'].mean():.0%}", T("متوسط إشغال الأماكن", "Average space occupancy")),
    (cm.short_egp(sp["revenue"].sum() / max(len(sp), 1) / months_in), T("إيراد المكان في الشهر", "Revenue per space per month")),
    (f"{len(idle)}", T(f"مكان شبه فاضي (أقل من 10%) من {len(sp)}", f"Near-empty spaces (under 10%) of {len(sp)}")),
    (f"{top_share:.0%}", T("نصيب أكبر معلن من الإيراد", "Biggest advertiser's revenue share")),
], accent_first=True)

# ---------------------------------------------------------------- occupancy over time
with st.container(border=True):
    st.markdown(T("#### الإشغال شهر بشهر", "#### Occupancy month by month"))
    m = models.monthly_occupancy(daily, len(active))
    m = m[m["month_start"] <= today + pd.DateOffset(months=3)]
    m["kind"] = (m["month_start"] < today.to_period("M").to_timestamp()).map(
        {True: T("فعلي", "Actual"), False: T("محجوز لحد دلوقتي", "Booked so far")})
    m["m"] = m["month_start"].dt.month.map(cm.month) + " " + m["month_start"].dt.year.astype(str)
    fig = px.bar(m, x="m", y="occupancy", color="kind",
                 color_discrete_map={T("فعلي", "Actual"): cm.L1, T("محجوز لحد دلوقتي", "Booked so far"): "#6C7891"},
                 labels={"occupancy": T("نسبة الإشغال", "Occupancy"), "m": "", "kind": ""})
    fig.update_yaxes(tickformat=".0%")
    fig.update_xaxes(categoryorder="array", categoryarray=m["m"].tolist())
    st.plotly_chart(cm.style_fig(fig, 340), use_container_width=True)
    cm.html('<p class="note">' + T("الإشغال = أيام الحجز ÷ (عدد الأماكن الشغالة × أيام الشهر). الشهور الجاية لسه بتتملى.",
                                   "Occupancy = booked space-days ÷ (active spaces × days in month). Upcoming months are still filling up.")
            + "</p>")

a, b = st.columns(2)
with a, st.container(border=True):
    st.markdown(T("#### الإشغال حسب نوع الإعلان وفئة المحطة", "#### Occupancy by format and station tier"))
    hm = sp.groupby(["format_l", "tier_l"])["occupancy"].mean().unstack()
    order = [cm.lbl("tier", t) for t in ("Premium", "High", "Standard") if cm.lbl("tier", t) in hm.columns]
    hm = hm[order].sort_values(order[0], ascending=False)
    heat = px.imshow(hm, text_auto=".0%", aspect="auto", color_continuous_scale=["#16213F", cm.L1, cm.GOLD],
                     labels={"color": T("الإشغال", "Occupancy"), "x": "", "y": ""}, zmin=0, zmax=1)
    heat.update_coloraxes(showscale=False)
    heat.update_yaxes(side=cm.y_side())
    st.plotly_chart(cm.style_fig(heat, 420), use_container_width=True)
with b, st.container(border=True):
    st.markdown(T("#### الصرف حسب المجال والمعلن", "#### Spend by industry and advertiser"))
    tm = spend.groupby(["industry", "company_name"], as_index=False)["revenue"].sum()
    tm["industry_l"] = tm["industry"].map(lambda x: cm.lbl("ind", x))
    tree = px.treemap(tm, path=["industry_l", "company_name"], values="revenue",
                      color="industry_l", color_discrete_sequence=[cm.L1, cm.L2, cm.L3, cm.INTER, cm.GOLD, "#7FB3F0",
                                                                     "#F08A6A", "#5CC79C", "#9C8CF0", "#8E9AB3"])
    tree.update_traces(hovertemplate="%{label}<br>%{value:,.0f} " + EGP + "<extra></extra>", root_color="rgba(0,0,0,0)")
    st.plotly_chart(cm.style_fig(tree, 420), use_container_width=True)

# ---------------------------------------------------------------- advertisers table
with st.container(border=True):
    st.markdown(T("#### المعلنين", "#### Advertisers"))
    j = spend.merge(spaces[["ad_space_id", "station_id"]], on="ad_space_id")
    adv = j.groupby(["company_name", "industry"]).agg(
        spend=("revenue", "sum"), campaigns=("campaign_id", "nunique"), stations=("station_id", "nunique"),
        spaces=("ad_space_id", "nunique")).reset_index().sort_values("spend", ascending=False)
    c_sp = T("الصرف في الفترة", "Spend in period")
    st.dataframe(pd.DataFrame({
        T("المعلن", "Advertiser"): adv["company_name"], T("المجال", "Industry"): adv["industry"].map(lambda x: cm.lbl("ind", x)),
        c_sp: adv["spend"].round(), T("حملات", "Campaigns"): adv["campaigns"], T("محطات", "Stations"): adv["stations"],
        T("أماكن", "Spaces"): adv["spaces"]}),
        hide_index=True, use_container_width=True, column_config={c_sp: st.column_config.ProgressColumn(
            format="%d", min_value=0, max_value=float(adv["spend"].max() if len(adv) else 1))})

# ---------------------------------------------------------------- idle spaces
with st.container(border=True):
    st.markdown(T("#### أماكن محتاجة اهتمام", "#### Spaces that need attention"))
    st.markdown(T("أقل 15 مكان في الإشغال في الفترة دي، ومعاها اقتراح عملي.",
                  "The 15 least-booked spaces in this period, each with a practical suggestion."))
    low = sp.nsmallest(15, "occupancy").copy()
    rng = (low["price_max"] - low["price_min"]).replace(0, 1)
    pos = (low["monthly_price_egp"] - low["price_min"]) / rng
    low["tip"] = [
        T("السعر في أعلى نطاق السوق: جرّب تنزّله", "Priced at the top of the market range: try a lower price") if p > .6 else
        T("حطه في باكدج مع محطة قوية على نفس الخط", "Bundle it with a strong station on the same line") if t != "Premium" else
        T("محطة مميزة: اعرضه على معلنين المجال المناسب", "Premium station: pitch it to the right industries")
        for p, t in zip(pos, low["tier"])]
    c_occ, c_price = T("الإشغال", "Occupancy"), T("السعر الشهري", "Monthly price")
    table = pd.DataFrame({
        T("رقم المكان", "Space #"): low["ad_space_id"], T("المحطة", "Station"): low["name_l"],
        T("الخطوط", "Lines"): low["lines"].map(cm.lines_short), T("نوع الإعلان", "Format"): low["format_l"],
        T("المكان", "Zone"): low["zone"].map(lambda x: cm.lbl("zone", x)), c_price: low["monthly_price_egp"],
        c_occ: (low["occupancy"] * 100).round(), T("الاقتراح", "Suggestion"): low["tip"]})
    st.dataframe(table, hide_index=True, use_container_width=True, column_config={
        c_price: st.column_config.NumberColumn(format="%d"),
        c_occ: st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d%%")})
    st.download_button(T("⬇️ تحميل كل الأماكن بالإشغال (CSV)", "⬇️ Download all spaces with occupancy (CSV)"),
                       sp[["ad_space_id", "name_l", "format_l", "zone", "monthly_price_egp", "occupancy", "revenue"]]
                       .sort_values("occupancy").to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"space_occupancy_{w_start:%Y%m}_{w_end:%Y%m}.csv", mime="text/csv")
