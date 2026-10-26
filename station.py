import pandas as pd
import streamlit as st

import common as cm

d = cm.data()
profile, spaces = d["profile"], d["spaces"]
bk = cm.active_bookings(d["bookings"])

cm.header("تفاصيل محطة", "كل اللي محتاج تعرفه عن محطة، وحالة أماكنها الإعلانية النهارده.")

ordered = profile.sort_values("rank").set_index("station_id")
pick = st.selectbox("اختار المحطة", ordered.index.tolist(),
                    format_func=lambda i: f"{ordered.loc[i, 'name_ar']} ({ordered.loc[i, 'name_en']})")
row = ordered.loc[pick]

with st.container(border=True):
    cm.html(f"""
    <div class="station-card">
      <h3>{row['name_ar']}</h3>
      <span class="chip">{row['lines_ar']}</span>
      <span class="chip">فئة {row['tier_ar']}</span>
      <span class="chip">{cm.AR_AREA.get(row['area_type'], row['area_type'])}</span>
      <span class="chip">{cm.AR_TYPE.get(row['station_type'], row['station_type'])}</span>
      <span class="chip">{row['district']}، {cm.AR_GOV.get(row['governorate'], row['governorate'])}</span>
      <span class="chip">افتتحت {int(row['opened_year'])}</span>
    </div>""")
    cm.kpis([(f"#{int(row['rank'])}", "الترتيب من 84 محطة"),
             (f"{row['ad_score']:.1f}", "الدرجة الإعلانية من 100"),
             (f"{int(row['avg_daily_riders']):,}", "ركاب يوميًا (تقدير)")])
    cm.html(f"<p><b>الجمهور:</b> {cm.ar_list(row['target_audience'], cm.AR_AUD)}</p>"
            f"<p><b>أنسب المعلنين:</b> {cm.ar_list(row['best_advertisers'], cm.AR_IND)}</p>")

sp = spaces[spaces["station_id"] == pick].copy()
today = pd.Timestamp(cm.today())
now = bk[(bk["start_date"] <= today) & (bk["end_date"] >= today)]
until = bk[bk["end_date"] >= today].groupby("ad_space_id")["end_date"].max()
status = sp["ad_space_id"].isin(now["ad_space_id"]).map({True: "محجوز دلوقتي", False: "متاح دلوقتي"})
status[~sp["is_active"].astype(bool)] = "متوقف"

with st.container(border=True):
    st.markdown(f"#### الأماكن الإعلانية في المحطة ({len(sp)})")
    st.dataframe(pd.DataFrame({
        "رقم المكان": sp["ad_space_id"],
        "نوع الإعلان": sp["format_ar"],
        "المكان": sp["zone"].map(cm.AR_ZONE),
        "المقاس (م)": sp["width_m"].astype(str) + " × " + sp["height_m"].astype(str),
        "السعر الشهري": sp["monthly_price_egp"],
        "الحالة": status,
        "محجوز لحد": sp["ad_space_id"].map(until).dt.strftime("%d/%m/%Y"),
        "الإيراد لحد دلوقتي": sp["ad_space_id"].map(bk.groupby("ad_space_id")["price_egp"].sum()).fillna(0),
    }), hide_index=True, use_container_width=True, column_config={
        "السعر الشهري": st.column_config.NumberColumn(format="%d"),
        "الإيراد لحد دلوقتي": st.column_config.NumberColumn(format="%d"),
    })
