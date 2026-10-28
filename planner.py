import datetime as dt

import pandas as pd
import plotly.express as px
import streamlit as st

import common as cm
import verify
import writes
from common import T
from recommender import AUDIENCES, INDUSTRY_AUDIENCE, recommend

d = cm.data()
profile, spaces, bookings = d["profile"], d["spaces"], cm.active_bookings(d["bookings"])
NAME = "name_ar" if cm.is_ar() else "name_en"
EGP = T("جنيه", "EGP")

cm.header(T("خطّط حملتك واحجزها", "Plan and book a campaign"),
          T("اختار الجمهور والميزانية والمدة، والمخطط يرشّح لك أحسن أماكن فاضية، وتقدر تحجزها على طول. "
            "الأسعار شهرية قبل ضريبة القيمة المضافة 14%.",
            "Pick an audience, budget and dates. The planner recommends the best available ad spaces, and you can "
            "book them straight away. Prices are monthly, before 14% VAT."))

with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        industry = st.selectbox(T("مجال الشركة", "Your industry"), ["—"] + list(INDUSTRY_AUDIENCE),
                                format_func=lambda x: T("اختار المجال", "Choose an industry") if x == "—" else cm.lbl("ind", x))
        audiences = st.multiselect(T("الجمهور المستهدف", "Target audience"), AUDIENCES,
                                   default=INDUSTRY_AUDIENCE.get(industry, []),
                                   format_func=lambda x: cm.lbl("aud", x), placeholder=T("كل الجماهير", "Everyone"),
                                   help=T("بيتملا تلقائي حسب المجال. سيبه فاضي لو عايز توصل لكل الناس.",
                                          "Filled in from your industry. Leave empty to reach everyone."))
    with c2:
        budget = st.number_input(T("الميزانية الكلية (جنيه)", "Total budget (EGP)"), min_value=10_000,
                                 max_value=50_000_000, value=500_000, step=50_000, format="%d")
        months = st.slider(T("مدة الحملة (شهور)", "Campaign length (months)"), 1, 6, 2)
        next_month = (cm.today().replace(day=1) + dt.timedelta(days=32)).replace(day=1)
        start = st.date_input(T("تاريخ البداية", "Start date"), next_month, min_value=cm.today(), format="DD/MM/YYYY")
    with c3:
        lines = st.multiselect(T("الخطوط", "Lines"), ["L1", "L2", "L3"], format_func=lambda x: cm.lbl("line", x),
                               placeholder=T("كل الخطوط", "All lines"))
        fmts = sorted(spaces["format_name"].unique())
        formats = st.multiselect(T("أنواع الإعلانات", "Ad formats"), fmts, format_func=lambda x: cm.lbl("format", x),
                                 placeholder=T("كل الأنواع", "All formats"))
        max_per_station = st.slider(T("أقصى عدد أماكن في المحطة الواحدة", "Max spaces per station"), 1, 5, 2)

plan = recommend(profile, spaces, bookings, audiences, float(budget), start, months,
                 lines or None, formats or None, max_per_station)

if plan.spaces.empty:
    st.warning(T("مفيش أماكن فاضية تناسب الميزانية والاختيارات دي. جرّب تزوّد الميزانية، أو تقلّل مدة الحملة، "
                 "أو تشيل بعض الفلاتر، أو تغيّر التاريخ.",
                 "No available spaces fit this budget and these filters. Try a bigger budget, a shorter campaign, "
                 "fewer filters, or other dates."))
    st.stop()

cm.kpis([
    (cm.short_egp(plan.total_cost), T(f"تكلفة الخطة ({plan.total_cost / budget:.0%} من الميزانية)",
                                      f"Plan cost ({plan.total_cost / budget:.0%} of budget)")),
    (len(plan.stations), T("محطة", "Stations")),
    (len(plan.spaces), T("مكان إعلاني", "Ad spaces")),
    (T(f"{plan.impressions / 1e6:,.1f} مليون", f"{plan.impressions / 1e6:,.1f}M"), T("مشاهدة متوقعة من الركاب", "Expected rider impressions")),
    (T(f"{plan.cpm:,.2f} جنيه", f"EGP {plan.cpm:,.2f}"), T("تكلفة الوصول لكل 1000 راكب", "Cost per 1,000 riders")),
], accent_first=True)

IN_PLAN, OTHER = T("في الخطة", "In plan"), T("محطات أخرى", "Other stations")
m1, m2 = st.columns([1.35, 1])
with m1, st.container(border=True):
    st.markdown(T("#### المحطات اللي في الخطة", "#### Stations in the plan"))
    mp = profile.dropna(subset=["latitude"]).copy()
    chosen = set(plan.stations["station_id"])
    mp["state"] = mp["station_id"].isin(chosen).map({True: IN_PLAN, False: OTHER})
    mp["size"] = mp["state"].map({IN_PLAN: 15, OTHER: 5})
    fig = px.scatter_map(
        mp, lat="latitude", lon="longitude", color="state", size="size", size_max=15,
        hover_name="name_l", hover_data={"lines_l": True, "tier_l": True, "avg_daily_riders": ":,",
                                         "size": False, "latitude": False, "longitude": False, "state": False},
        labels={"lines_l": T("الخطوط", "Lines"), "tier_l": T("الفئة", "Tier"),
                "avg_daily_riders": T("ركاب يوميًا", "Daily riders"), "state": ""},
        color_discrete_map={IN_PLAN: cm.GOLD, OTHER: "#6C7891"},
        zoom=10.2, center={"lat": 30.06, "lon": 31.27}, map_style="carto-darkmatter",
    )
    st.plotly_chart(cm.style_fig(fig, 440), use_container_width=True)
    missing = int(plan.stations["latitude"].isna().sum())
    if missing:
        cm.html('<p class="note">' + T(f"{missing} محطة في الخطة مالهاش إحداثيات منشورة، فمش ظاهرة على الخريطة.",
                                       f"{missing} station(s) in the plan have no published coordinates, so they are not on the map.")
                + "</p>")
with m2, st.container(border=True):
    st.markdown(T("#### التكلفة حسب المحطة", "#### Cost by station"))
    sb = plan.stations.head(12).copy()
    sb["tier_l"] = sb["tier"].map(lambda x: cm.lbl("tier", x))
    bar = px.bar(sb.sort_values("cost"), x="cost", y=NAME, orientation="h", color="tier_l",
                 color_discrete_map=cm.tier_colors(),
                 labels={"cost": f"{T('التكلفة', 'Cost')} ({EGP})", NAME: "", "tier_l": T("الفئة", "Tier")})
    bar.update_yaxes(side=cm.y_side())
    st.plotly_chart(cm.style_fig(bar, 440), use_container_width=True)

with st.container(border=True):
    st.markdown(T("#### الأماكن الإعلانية المقترحة", "#### Recommended ad spaces"))
    c_month, c_total, c_riders, c_fit = (T("السعر الشهري", "Monthly price"), T("التكلفة الكلية", "Total cost"),
                                         T("ركاب يوميًا", "Daily riders"), T("تطابق الجمهور", "Audience fit"))
    show = pd.DataFrame({
        T("الأولوية", "Priority"): plan.spaces["priority"],
        T("المحطة", "Station"): plan.spaces[NAME],
        T("الخطوط", "Lines"): plan.spaces["lines"].map(cm.lines_label),
        T("الفئة", "Tier"): plan.spaces["tier"].map(lambda x: cm.lbl("tier", x)),
        T("نوع الإعلان", "Format"): plan.spaces["format_name"].map(lambda x: cm.lbl("format", x)),
        T("المكان", "Zone"): plan.spaces["zone"].map(lambda x: cm.lbl("zone", x)),
        c_month: plan.spaces["monthly_price_egp"],
        c_total: plan.spaces["cost"],
        c_riders: plan.spaces["avg_daily_riders"],
        c_fit: plan.spaces["audience_fit"],
        T("أساس السعر", "Price basis"): plan.spaces["price_basis"].map(lambda x: cm.lbl("basis", x)),
    })
    st.dataframe(show, hide_index=True, use_container_width=True, column_config={
        c_month: st.column_config.NumberColumn(format="%d"),
        c_total: st.column_config.NumberColumn(format="%d"),
        c_riders: st.column_config.NumberColumn(format="%d"),
        c_fit: st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
    })
    st.download_button(T("⬇️ تحميل الخطة (CSV)", "⬇️ Download plan (CSV)"), show.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"metro_ad_plan_{start}.csv", mime="text/csv")

with st.expander(T("المخطط بيختار الأماكن إزاي؟", "How does the planner choose?")):
    st.markdown(T(
        "- **المتاح بس**: الأماكن الشغالة اللي مفيش عليها حجز في نفس تواريخ حملتك.\n"
        "- **درجة الملاءمة** = 50% تطابق الجمهور + 30% درجة المحطة الإعلانية + 20% عدد الركاب.\n"
        "- **القيمة** = 50% ملاءمة + 50% عدد الناس اللي توصلهم بكل جنيه.\n"
        f"- بيختار بالترتيب لحد ما الميزانية تخلص، بحد أقصى {max_per_station} أماكن و35% من الميزانية في المحطة الواحدة.\n"
        "- المشاهدات = ركاب المحطة يوميًا × أيام الحملة (كل محطة بتتحسب مرة واحدة).",
        "- **Available only**: active spaces with no booking overlapping your dates.\n"
        "- **Fit** = 50% audience match + 30% station ad score + 20% reach.\n"
        "- **Value** = 50% fit + 50% riders reached per EGP.\n"
        f"- Spaces are picked by value until the budget runs out, with at most {max_per_station} spaces and 35% of "
        "the budget per station.\n"
        "- Impressions = station daily riders × campaign days (each station counted once)."))

# ---------------------------------------------------------------- quote + booking
end = start + dt.timedelta(days=30 * months - 1)
with st.container(border=True):
    st.markdown(T("#### عرض السعر والحجز", "#### Quote and booking"))
    cm.html('<p class="note">' + T(
        f'الخطة: {len(plan.spaces)} مكان من {start:%d/%m/%Y} لحد {end:%d/%m/%Y} بإجمالي {cm.short_egp(plan.total_cost)} قبل الضريبة. '
        'نزّل عرض السعر PDF، أو احجز على طول: الحجز بيتسجّل "في انتظار المراجعة" والأماكن بتتقفل عليك من دلوقتي.',
        f'The plan: {len(plan.spaces)} spaces from {start:%d/%m/%Y} to {end:%d/%m/%Y} for {cm.short_egp(plan.total_cost)} before VAT. '
        'Download the PDF quote, or book straight away: the booking is saved as "pending review" and the spaces are held for you.')
        + "</p>")
    f1, f2, f3 = st.columns(3)
    company = f1.text_input(T("اسم الشركة *", "Company name *"))
    campaign_name = f2.text_input(T("اسم الحملة", "Campaign name"),
                                  value=T(f"حملة {cm.month(start.month)} {start.year}", f"{cm.month(start.month)} {start.year} campaign"))
    ind_choice = f3.selectbox(T("المجال", "Industry"), list(INDUSTRY_AUDIENCE),
                              index=list(INDUSTRY_AUDIENCE).index(industry) if industry in INDUSTRY_AUDIENCE else 0,
                              format_func=lambda x: cm.lbl("ind", x))
    contact_name = f1.text_input(T("اسم المسؤول (اختياري)", "Contact person (optional)"))
    phone = f2.text_input(T("رقم الموبايل (اختياري)", "Mobile number (optional)"), placeholder="01xxxxxxxxx")
    email, email_ok = verify.email_field("plan", T("الإيميل * (لازم يتأكد قبل الحجز)", "Email * (verified before booking)"))

    aud_text = cm.list_label(", ".join(audiences), "aud") if audiences else T("كل الجماهير", "Everyone")
    q_rows = [dict(station=r[NAME], lines=cm.lines_short(r["lines"]), format=cm.lbl("format", r["format_name"]),
                   zone=cm.lbl("zone", r["zone"]), monthly=float(r["monthly_price_egp"]), months=months,
                   total=float(r["cost"])) for _, r in plan.spaces.iterrows()]
    q_meta = dict(company=company.strip(), campaign=campaign_name.strip(), start=start, end=end, audience=aud_text,
                  impressions=float(plan.impressions), cpm=float(plan.cpm))
    try:
        import quote
        pdf = quote.build_quote(q_rows, q_meta, ar=cm.is_ar())
    except Exception as e:  # noqa: BLE001  (missing PDF libraries should never break the planner)
        pdf = None
        st.caption(T(f"عرض السعر PDF مش متاح دلوقتي: {e}", f"The PDF quote isn't available right now: {e}"))

    agree = st.checkbox(T("راجعت الأماكن والأسعار وموافق على الحجز", "I reviewed the spaces and prices and agree to book"))
    b1, b2 = st.columns(2)
    if pdf:
        b1.download_button(T("📄 تحميل عرض السعر (PDF)", "📄 Download quote (PDF)"), pdf, use_container_width=True,
                           file_name=f"metro_quote_{start:%Y%m%d}.pdf", mime="application/pdf")
    submitted = b2.button(T("احجز الخطة", "Book plan"), type="primary", use_container_width=True)

if submitted:
    if not company.strip() or not campaign_name.strip():
        st.error(T("اكتب اسم الشركة واسم الحملة.", "Enter the company name and the campaign name."))
    elif not email or not verify.EMAIL_RE.match(email):
        st.error(T("اكتب إيميل صحيح.", "Enter a valid email."))
    elif email_ok is False:
        st.error(T("أكّد الإيميل الأول: دوس «ابعت كود التأكيد» واكتب الكود اللي وصلك.",
                   "Verify the email first: press “Send code” and enter the code you receive."))
    elif not agree:
        st.error(T("علّم على خانة الموافقة الأول.", "Tick the agreement box first."))
    else:
        items = list(zip(plan.spaces["ad_space_id"], plan.spaces["cost"]))
        audience = ", ".join(audiences) if audiences else "All"
        try:
            cid = writes.book_plan(cm.engine(), company, ind_choice, campaign_name, audience, float(budget),
                                   start, end, items, status="pending", source="web",
                                   contact={"name": contact_name, "phone": phone, "email": email,
                                            "verified": bool(email_ok)})
        except writes.BookingConflict:
            cm.refresh()
            st.error(T("مكان أو أكتر من الخطة اتحجز من حد تاني دلوقتي. حدّثت البيانات، اضغط احجز تاني على الخطة الجديدة.",
                       "Someone just booked one or more of these spaces. The data is refreshed: press Book plan again on the new plan."))
        else:
            cm.refresh()
            st.success(T(f"اتحجزت الحملة رقم {cid} ({len(items)} مكان). هتظهر في لوحة المؤشرات وفي صفحة الإدارة للمراجعة.",
                         f"Booked campaign #{cid} ({len(items)} spaces). It now shows on the dashboard and in Admin for review."))
