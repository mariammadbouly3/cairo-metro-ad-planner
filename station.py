import pandas as pd
import streamlit as st

import common as cm
from common import T

d = cm.data()
profile, spaces = d["profile"], d["spaces"]
bk = cm.active_bookings(d["bookings"])

cm.header(T("تفاصيل محطة", "Station details"),
          T("كل اللي محتاج تعرفه عن محطة، وحالة أماكنها الإعلانية النهارده.",
            "Everything about one station, and the status of its ad spaces today."))

ordered = profile.sort_values("rank").set_index("station_id")
other_name = "name_en" if cm.is_ar() else "name_ar"
pick = st.selectbox(T("اختار المحطة", "Choose a station"), ordered.index.tolist(),
                    format_func=lambda i: f"{ordered.loc[i, 'name_l']} ({ordered.loc[i, other_name]})")
row = ordered.loc[pick]
n_subs = int((cm.active_subs(d["subscriptions"])["home_station_id"] == pick).sum())

with st.container(border=True):
    cm.html(f"""
    <div class="station-card">
      <h3>{row['name_l']}</h3>
      <span class="chip">{row['lines_l']}</span>
      <span class="chip">{T('فئة', 'Tier')} {row['tier_l']}</span>
      <span class="chip">{cm.lbl('area', row['area_type'])}</span>
      <span class="chip">{cm.lbl('type', row['station_type'])}</span>
      <span class="chip">{row['district']}{T('، ', ', ')}{cm.lbl('gov', row['governorate'])}</span>
      <span class="chip">{T('افتتحت', 'Opened')} {int(row['opened_year'])}</span>
      <span class="chip">🎫 {n_subs:,} {T('مشترك سنوي ساكن جنبها', 'annual pass holders live nearby')}</span>
    </div>""")
    cm.kpis([(f"#{int(row['rank'])}", T("الترتيب من 84 محطة", "Rank out of 84 stations")),
             (f"{row['ad_score']:.1f}", T("الدرجة الإعلانية من 100", "Ad score out of 100")),
             (f"{int(row['avg_daily_riders']):,}", T("ركاب يوميًا (تقدير)", "Daily riders (estimate)"))])
    cm.html(f"<p><b>{T('الجمهور:', 'Audience:')}</b> {cm.list_label(row['target_audience'], 'aud')}</p>"
            f"<p><b>{T('أنسب المعلنين:', 'Best advertisers:')}</b> {cm.list_label(row['best_advertisers'], 'ind')}</p>")

if st.button(T("🙋 اطلب مكان في المحطة دي", "🙋 Request a space at this station"), type="primary"):
    st.session_state["req_station"] = pick
    cm.go("request.py")

sp = spaces[spaces["station_id"] == pick].copy()
today = pd.Timestamp(cm.today())
now = bk[(bk["start_date"] <= today) & (bk["end_date"] >= today)]
until = bk[bk["end_date"] >= today].groupby("ad_space_id")["end_date"].max()
status = sp["ad_space_id"].isin(now["ad_space_id"]).map({True: T("محجوز دلوقتي", "Booked now"),
                                                         False: T("متاح دلوقتي", "Available now")})
status[~sp["is_active"].astype(bool)] = T("متوقف", "Inactive")

with st.container(border=True):
    st.markdown(T(f"#### الأماكن الإعلانية في المحطة ({len(sp)})", f"#### Ad spaces at this station ({len(sp)})"))
    c_price, c_rev = T("السعر الشهري", "Monthly price"), T("الإيراد لحد دلوقتي", "Revenue to date")
    st.dataframe(pd.DataFrame({
        T("رقم المكان", "Space #"): sp["ad_space_id"],
        T("نوع الإعلان", "Format"): sp["format_l"],
        T("المكان", "Zone"): sp["zone"].map(lambda x: cm.lbl("zone", x)),
        T("المقاس (م)", "Size (m)"): sp["width_m"].astype(str) + " × " + sp["height_m"].astype(str),
        c_price: sp["monthly_price_egp"],
        T("الحالة", "Status"): status,
        T("محجوز لحد", "Booked until"): sp["ad_space_id"].map(until).dt.strftime("%d/%m/%Y"),
        c_rev: sp["ad_space_id"].map(bk.groupby("ad_space_id")["price_egp"].sum()).fillna(0),
    }), hide_index=True, use_container_width=True, column_config={
        c_price: st.column_config.NumberColumn(format="%d"),
        c_rev: st.column_config.NumberColumn(format="%d"),
    })

# ---------------------------------------------------------------- booking calendar
import plotly.express as px  # noqa: E402

with st.container(border=True):
    st.markdown(T("#### تقويم الحجوزات", "#### Booking calendar"))
    st.markdown(T("كل سطر مكان إعلاني، وكل شريط حجز. المسافات الفاضية هي فرص بيع.",
                  "Each row is an ad space and each bar a booking. The gaps are what's left to sell."))
    w_from, w_to = today - pd.Timedelta(days=30), today + pd.Timedelta(days=180)
    cal = bk[bk["ad_space_id"].isin(sp["ad_space_id"]) & (bk["end_date"] >= w_from) & (bk["start_date"] <= w_to)]
    cal = cal.merge(d["campaigns"][["campaign_id", "company_name"]], on="campaign_id", how="left")
    labels = {r.ad_space_id: f"#{r.ad_space_id} {r.format_l}" for r in sp.itertuples()}
    if cal.empty:
        st.success(T("كل أماكن المحطة فاضية في الـ 6 شهور الجاية.", "Every space here is free for the next 6 months."))
    else:
        cal = cal.assign(space=cal["ad_space_id"].map(labels), status_l=cal["status"].map(lambda x: cm.lbl("status", x)),
                         start=cal["start_date"].clip(lower=w_from), end=cal["end_date"].clip(upper=w_to) + pd.Timedelta(days=1))
        gantt = px.timeline(cal, x_start="start", x_end="end", y="space", color="status_l", hover_name="company_name",
                            hover_data={"start_date": "|%d/%m/%Y", "end_date": "|%d/%m/%Y", "price_egp": ":,.0f",
                                        "start": False, "end": False, "space": False, "status_l": False},
                            color_discrete_map={cm.lbl("status", "confirmed"): cm.L1, cm.lbl("status", "pending"): cm.GOLD},
                            labels={"status_l": "", "space": "", "start_date": T("من", "From"), "end_date": T("لحد", "To"),
                                    "price_egp": T("القيمة", "Value")},
                            category_orders={"space": [labels[i] for i in sp["ad_space_id"]]})
        gantt.add_vline(x=today, line=dict(color="#FFFFFF", width=1, dash="dot"))
        gantt.update_xaxes(range=[w_from, w_to], tickformat="%d %b")
        gantt.update_yaxes(side=cm.y_side(), autorange="reversed")
        st.plotly_chart(cm.style_fig(gantt, max(220, 42 * len(sp) + 90)), use_container_width=True)
        ahead = cal[(cal["end_date"] >= today) & (cal["start_date"] <= w_to)]
        used = ((ahead["end_date"].clip(upper=w_to) - ahead["start_date"].clip(lower=today)).dt.days + 1).sum()
        free_days = int(((w_to - today).days + 1) * len(sp) - used)
        cm.html('<p class="note">' + T(f"الخط المنقط = النهارده. في الـ 6 شهور الجاية فيه حوالي {max(free_days, 0):,} يوم-مكان فاضي في المحطة دي.",
                                       f"Dotted line = today. Over the next 6 months this station has about {max(free_days, 0):,} free space-days.")
                + "</p>")
