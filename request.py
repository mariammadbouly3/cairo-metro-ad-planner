import datetime as dt
import re

import pandas as pd
import streamlit as st

import common as cm
import writes
from common import T
from recommender import INDUSTRY_AUDIENCE

d = cm.data()
profile, spaces = d["profile"], d["spaces"]
bk = cm.active_bookings(d["bookings"])

cm.header(T("اطلب مكان إعلاني", "Request an ad space"),
          T("اختار المحطة والمدة والأماكن اللي عاجباك، وابعت بياناتك. الإدارة هتراجع الطلب وتتواصل معاك.",
            "Pick a station, dates and the spaces you like, then send your details. The team reviews the request "
            "and gets back to you."))

ordered = profile.sort_values("rank").set_index("station_id")
ids = ordered.index.tolist()
pre = st.session_state.pop("req_station", None)
other = "name_en" if cm.is_ar() else "name_ar"

with st.container(border=True):
    c1, c2, c3 = st.columns([2, 1, 1])
    station = c1.selectbox(T("المحطة", "Station"), ids, index=ids.index(pre) if pre in ids else 0,
                           format_func=lambda i: f"{ordered.loc[i, 'name_l']} ({ordered.loc[i, other]})")
    next_month = (cm.today().replace(day=1) + dt.timedelta(days=32)).replace(day=1)
    start = c2.date_input(T("تاريخ البداية", "Start date"), next_month, min_value=cm.today(), format="DD/MM/YYYY")
    months = c3.number_input(T("عدد الشهور", "Months"), min_value=1, max_value=12, value=1, step=1)
    end = start + dt.timedelta(days=30 * int(months) - 1)
    row = ordered.loc[station]
    cm.html(f'<span class="chip">{row["lines_l"]}</span><span class="chip">{T("فئة", "Tier")} {row["tier_l"]}</span>'
            f'<span class="chip">{int(row["avg_daily_riders"]):,} {T("راكب يوميًا", "riders a day")}</span>'
            f'<span class="chip">{T("لحد", "Until")} {end:%d/%m/%Y}</span>')

    here = spaces[(spaces["station_id"] == station) & spaces["is_active"].astype(bool)].copy()
    s_ts, e_ts = pd.Timestamp(start), pd.Timestamp(end)
    clash = bk[(bk["start_date"] <= e_ts) & (bk["end_date"] >= s_ts)]
    here["free"] = ~here["ad_space_id"].isin(clash["ad_space_id"])
    here["total"] = (here["monthly_price_egp"] * int(months)).round()
    free = here[here["free"]].set_index("ad_space_id")

    st.markdown(T(f"#### الأماكن في المحطة ({len(free)} متاح من {len(here)})",
                  f"#### Spaces at this station ({len(free)} of {len(here)} available)"))
    c_m, c_t = T("السعر الشهري", "Monthly price"), T(f"إجمالي {int(months)} شهر", f"Total for {int(months)} month(s)")
    st.dataframe(pd.DataFrame({
        T("رقم المكان", "Space #"): here["ad_space_id"], T("نوع الإعلان", "Format"): here["format_l"],
        T("المكان", "Zone"): here["zone"].map(lambda x: cm.lbl("zone", x)),
        T("المقاس (م)", "Size (m)"): here["width_m"].astype(str) + " × " + here["height_m"].astype(str),
        c_m: here["monthly_price_egp"], c_t: here["total"],
        T("الحالة", "Status"): here["free"].map({True: T("✅ متاح", "✅ Available"), False: T("⛔ محجوز", "⛔ Booked")}),
    }), hide_index=True, use_container_width=True,
        column_config={c_m: st.column_config.NumberColumn(format="%d"), c_t: st.column_config.NumberColumn(format="%d")})

    if free.empty:
        st.warning(T("كل الأماكن في المحطة دي محجوزة في التواريخ دي. جرّب تاريخ تاني أو محطة تانية، أو استخدم صفحة "
                     "**خطّط واحجز** عشان تلاقي بدائل.",
                     "Every space here is booked for these dates. Try other dates or another station, or use "
                     "**Plan & book** to find alternatives."))
        st.stop()

    picked = st.multiselect(T("اختار الأماكن اللي عايزها", "Choose the spaces you want"), free.index.tolist(),
                            default=free.index.tolist()[:1],
                            format_func=lambda i: f"#{i} {free.loc[i, 'format_l']} · {cm.short_egp(free.loc[i, 'total'])}")
    total = float(free.loc[picked, "total"].sum()) if picked else 0.0
    cm.kpis([(cm.short_egp(total), T("قبل الضريبة", "Before VAT")),
             (cm.short_egp(total * 1.14), T("شامل ضريبة 14%", "Incl. 14% VAT")),
             (f"{len(picked)}", T("مكان", "Spaces"))], accent_first=True)

# ---------------------------------------------------------------- contact form
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
with st.form("request"):
    st.markdown(T("#### بياناتك", "#### Your details"))
    f1, f2 = st.columns(2)
    company = f1.text_input(T("اسم الشركة *", "Company name *"))
    industry = f2.selectbox(T("المجال", "Industry"), list(INDUSTRY_AUDIENCE), format_func=lambda x: cm.lbl("ind", x))
    name = f1.text_input(T("اسم المسؤول *", "Contact person *"))
    phone = f2.text_input(T("رقم الموبايل", "Mobile number"), placeholder="01xxxxxxxxx")
    email = f1.text_input(T("الإيميل", "Email"), placeholder="name@company.com")
    campaign = f2.text_input(T("اسم الحملة", "Campaign name"),
                             value=T(f"حملة {cm.month(start.month)} {start.year}", f"{cm.month(start.month)} {start.year} campaign"))
    notes = st.text_area(T("ملاحظات (اختياري)", "Notes (optional)"), max_chars=500,
                         placeholder=T("مثلًا: محتاجين التركيب قبل رمضان", "e.g. we need it installed before Ramadan"))
    cm.html('<p class="note">' + T("لازم رقم موبايل أو إيميل عشان نقدر نتواصل معاك. الطلب بيقفل الأماكن عليك لحد ما الإدارة تراجعه.",
                                   "Give a mobile number or an email so we can reach you. The request holds the spaces "
                                   "for you until the team reviews it.") + "</p>")
    sent = st.form_submit_button(T("ابعت الطلب", "Send request"), type="primary", use_container_width=True)

if sent:
    digits = re.sub(r"\D", "", phone or "")
    problems = []
    if not company.strip() or not name.strip():
        problems.append(T("اكتب اسم الشركة واسم المسؤول.", "Enter the company name and the contact person."))
    if not digits and not (email or "").strip():
        problems.append(T("اكتب رقم موبايل أو إيميل.", "Enter a mobile number or an email."))
    if digits and not 8 <= len(digits) <= 15:
        problems.append(T("رقم الموبايل شكله مش مظبوط.", "The mobile number doesn't look right."))
    if (email or "").strip() and not EMAIL.match(email.strip()):
        problems.append(T("الإيميل شكله مش مظبوط.", "The email doesn't look right."))
    if not picked:
        problems.append(T("اختار مكان واحد على الأقل.", "Choose at least one space."))
    if problems:
        for p in problems:
            st.error(p)
    else:
        items = [(i, float(free.loc[i, "total"])) for i in picked]
        try:
            cid = writes.book_plan(cm.engine(), company, industry, campaign or company, "Request form", total,
                                   start, end, items, status="pending", source="request",
                                   contact={"name": name, "phone": phone, "email": email, "notes": notes})
        except writes.BookingConflict:
            cm.refresh()
            st.error(T("حد حجز مكان من دول دلوقتي. حدّثت الصفحة، اختار تاني وابعت.",
                       "Someone just booked one of these spaces. The page is refreshed: choose again and send."))
        else:
            cm.refresh()
            st.success(T(f"وصل طلبك (رقم {cid}). هنراجعه ونتواصل معاك قريب.",
                         f"Request received (#{cid}). We'll review it and get back to you soon."))
            st.balloons()
