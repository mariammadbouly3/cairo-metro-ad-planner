import datetime as dt
import hmac

import pandas as pd
import streamlit as st

import common as cm
import writes
from common import T
from recommender import AUDIENCES, INDUSTRY_AUDIENCE

cm.header(T("الإدارة", "Admin"),
          T("راجع الحجوزات، وضيف حملات وحجوزات، وعدّل الأسعار. أي تغيير بيظهر على طول في كل الصفحات وفي Power BI.",
            "Review bookings, add campaigns and bookings, and edit prices. Every change shows up straight away on "
            "every page and in Power BI."))

# ---------------------------------------------------------------- password gate
expected = cm.admin_password()
if not expected:
    st.warning(T("صفحة الإدارة مقفولة لحد ما تحدد كلمة مرور لها. ضيف ADMIN_PASSWORD في الـ Secrets بتاعة التطبيق "
                 "(أو في ملف .streamlit/secrets.toml لو شغالة على اللاب).",
                 "The admin page stays locked until it has a password. Add ADMIN_PASSWORD to the app secrets "
                 "(or to .streamlit/secrets.toml when running on a laptop)."))
    st.stop()

if not st.session_state.get("is_admin"):
    with st.form("login"):
        pw = st.text_input(T("كلمة مرور الإدارة", "Admin password"), type="password")
        if st.form_submit_button(T("دخول", "Sign in"), type="primary"):
            if hmac.compare_digest(pw, expected):
                st.session_state["is_admin"] = True
                st.rerun()
            else:
                st.error(T("كلمة المرور غلط.", "Wrong password."))
    st.stop()

if st.button(T("خروج", "Sign out")):
    st.session_state["is_admin"] = False
    st.rerun()

import verify  # noqa: E402

if not verify.configured():
    st.info(T("تأكيد الإيميل مش شغال لسه: ضيف SMTP_USER و SMTP_PASSWORD في الـ Secrets (شوف verify.py). "
              "لحد ما تضيفهم، الحجوزات بتتبعت من غير تأكيد.",
              "Email verification is off: add SMTP_USER and SMTP_PASSWORD to the app secrets (see verify.py). "
              "Until then, bookings are sent without verification."), icon="📧")

eng = cm.engine()
d = cm.data()
profile, spaces, campaigns, bk = d["profile"], d["spaces"], d["campaigns"], d["bookings"]
station_name = profile.set_index("station_id")["name_l"]
L = cm.lang()  # editor keys include the language so switching never mixes saved edits

BOOKING_COLS = {  # internal column -> displayed label
    "sel": T("اختيار", "Select"), "id": T("رقم الحجز", "Booking #"), "adv": T("المعلن", "Advertiser"),
    "camp": T("الحملة", "Campaign"), "station": T("المحطة", "Station"), "fmt": T("نوع الإعلان", "Format"),
    "from": T("من", "From"), "to": T("لحد", "To"), "value": T("القيمة", "Value"), "status": T("الحالة", "Status"),
    "src": T("جه من", "Source"), "contact": T("التواصل", "Contact"), "notes": T("ملاحظات", "Notes"),
}
SOURCES = {"web": ("المخطط", "Planner"), "request": ("فورم الطلب", "Request form"), "admin": ("الإدارة", "Admin"),
           "seed": ("بيانات تجريبية", "Demo data")}
BOOKING_CFG = {k: st.column_config.Column(v) for k, v in BOOKING_COLS.items()}
BOOKING_CFG["value"] = st.column_config.NumberColumn(BOOKING_COLS["value"], format="%d")
BOOKING_CFG["sel"] = st.column_config.CheckboxColumn(BOOKING_COLS["sel"])


def booking_table(df):
    j = (df.merge(spaces[["ad_space_id", "station_id", "format_l"]], on="ad_space_id")
           .merge(campaigns[["campaign_id", "campaign_name", "company_name", "contact_name", "contact_phone",
                             "contact_email", "notes", "email_verified"]], on="campaign_id"))
    j["contact_email"] = [f"{e} ✅" if pd.notna(e) and str(e).strip() and bool(v) else e
                          for e, v in zip(j["contact_email"], j["email_verified"].fillna(False))]
    contact = j[["contact_name", "contact_phone", "contact_email"]].apply(
        lambda r: " · ".join(str(v) for v in r if pd.notna(v) and str(v).strip()), axis=1)
    return pd.DataFrame({
        "sel": False, "id": j["booking_id"], "adv": j["company_name"], "camp": j["campaign_name"],
        "station": j["station_id"].map(station_name), "fmt": j["format_l"],
        "from": j["start_date"].dt.date, "to": j["end_date"].dt.date, "value": j["price_egp"],
        "status": j["status"].map(lambda x: cm.lbl("status", x)),
        "src": j["source"].map(lambda x: SOURCES.get(x, (x, x))[0 if cm.is_ar() else 1]),
        "contact": contact, "notes": j["notes"].fillna(""),
    })


def editor(df, key):
    return st.data_editor(df, hide_index=True, use_container_width=True, key=f"{key}_{L}",
                          disabled=[c for c in df.columns if c != "sel"], column_config=BOOKING_CFG)


t_review, t_all, t_new, t_prices = st.tabs([
    T("📥 حجوزات للمراجعة", "📥 To review"), T("📚 كل الحجوزات", "📚 All bookings"),
    T("➕ حملة أو حجز جديد", "➕ New campaign or booking"), T("🏷️ الأسعار والأماكن", "🏷️ Prices & spaces")])

# ---------------------------------------------------------------- review pending web bookings
with t_review:
    pend = bk[bk["status"] == "pending"].sort_values("created_at", ascending=False)
    if pend.empty:
        st.success(T("مفيش حجوزات مستنية مراجعة.", "No bookings waiting for review."))
    else:
        st.markdown(T(f"**{len(pend)}** حجز جه من الموقع. علّم على اللي عايز توافق عليه أو تلغيه.",
                      f"**{len(pend)}** bookings came in from the website. Tick the ones to approve or cancel."))
        ed = editor(booking_table(pend), "pend")
        ids = ed.loc[ed["sel"], "id"].tolist()
        a, b, c = st.columns(3)
        if a.button(T(f"✅ موافقة ({len(ids)})", f"✅ Approve ({len(ids)})"), disabled=not ids,
                    use_container_width=True, type="primary"):
            writes.set_booking_status(eng, ids, "confirmed")
            cm.refresh()
            st.rerun()
        if b.button(T(f"❌ إلغاء ({len(ids)})", f"❌ Cancel ({len(ids)})"), disabled=not ids, use_container_width=True):
            writes.set_booking_status(eng, ids, "cancelled")
            cm.refresh()
            st.rerun()
        if c.button(T("✅ موافقة على الكل", "✅ Approve all"), use_container_width=True):
            writes.set_booking_status(eng, pend["booking_id"].tolist(), "confirmed")
            cm.refresh()
            st.rerun()

# ---------------------------------------------------------------- all bookings
with t_all:
    f1, f2, f3 = st.columns(3)
    status_pick = f1.multiselect(T("الحالة", "Status"), ["confirmed", "pending", "cancelled"],
                                 default=["confirmed", "pending"], format_func=lambda x: cm.lbl("status", x))
    ALL = "__all__"
    adv_pick = f2.selectbox(T("المعلن", "Advertiser"), [ALL] + sorted(campaigns["company_name"].unique()),
                            format_func=lambda x: T("الكل", "All") if x == ALL else x)
    only_future = f3.checkbox(T("الحالية والجاية بس", "Current and upcoming only"), value=True)
    view = bk[bk["status"].isin(status_pick)]
    if adv_pick != ALL:
        view = view[view["campaign_id"].isin(campaigns.loc[campaigns["company_name"] == adv_pick, "campaign_id"])]
    if only_future:
        view = view[view["end_date"] >= pd.Timestamp(cm.today())]
    view = view.sort_values("start_date", ascending=False).head(500)
    st.caption(T(f"{len(view)} حجز (بيظهر أول 500)", f"{len(view)} bookings (first 500 shown)"))
    ed2 = editor(booking_table(view), "all")
    ids2 = ed2.loc[ed2["sel"], "id"].tolist()
    a, b = st.columns(2)
    if a.button(T(f"❌ إلغاء المختار ({len(ids2)})", f"❌ Cancel selected ({len(ids2)})"), disabled=not ids2,
                use_container_width=True):
        writes.set_booking_status(eng, ids2, "cancelled")
        cm.refresh()
        st.rerun()
    if b.button(T(f"↩️ رجّع المختار لمؤكد ({len(ids2)})", f"↩️ Restore selected to confirmed ({len(ids2)})"),
                disabled=not ids2, use_container_width=True):
        try:
            writes.set_booking_status(eng, ids2, "confirmed")
        except writes.BookingConflict:
            st.error(T("مقدرش أرجّع الحجز: المكان اتحجز لحد تاني في نفس الفترة.",
                       "Can't restore: the space was booked by someone else for the same dates."))
        else:
            cm.refresh()
            st.rerun()

# ---------------------------------------------------------------- new campaign / booking
with t_new:
    left, right = st.columns(2)
    with left, st.form("new_campaign", clear_on_submit=True):
        st.markdown(T("#### حملة جديدة", "#### New campaign"))
        company = st.text_input(T("اسم الشركة", "Company name"))
        industry = st.selectbox(T("المجال", "Industry"), list(INDUSTRY_AUDIENCE), format_func=lambda x: cm.lbl("ind", x))
        cname = st.text_input(T("اسم الحملة", "Campaign name"))
        aud = st.selectbox(T("الجمهور", "Audience"), AUDIENCES, format_func=lambda x: cm.lbl("aud", x))
        s1, s2 = st.columns(2)
        cstart = s1.date_input(T("من", "From"), cm.today(), format="DD/MM/YYYY")
        cend = s2.date_input(T("لحد", "To"), cm.today() + dt.timedelta(days=29), format="DD/MM/YYYY")
        cbudget = st.number_input(T("الميزانية (جنيه)", "Budget (EGP)"), min_value=0, value=200_000, step=10_000, format="%d")
        if st.form_submit_button(T("ضيف الحملة", "Add campaign"), type="primary"):
            if not company.strip() or not cname.strip() or cend < cstart:
                st.error(T("اكتب اسم الشركة والحملة، واتأكد إن تاريخ النهاية بعد البداية.",
                           "Enter the company and campaign names, and make sure the end date is after the start."))
            else:
                cid = writes.add_campaign(eng, company, industry, cname, aud, cstart, cend, cbudget)
                cm.refresh()
                st.success(T(f"اتضافت الحملة رقم {cid}. تقدر تحجز لها أماكن من الجنب.",
                             f"Added campaign #{cid}. Book spaces for it on the right."))

    with right, st.container(border=True):
        st.markdown(T("#### حجز مكان لحملة", "#### Book a space for a campaign"))
        camp_opts = campaigns.sort_values("campaign_id", ascending=False).set_index("campaign_id")
        cid = st.selectbox(T("الحملة", "Campaign"), camp_opts.index.tolist(),
                           format_func=lambda i: f"#{i} {camp_opts.loc[i, 'campaign_name']}")
        st_id = st.selectbox(T("المحطة", "Station"), profile.sort_values("rank")["station_id"].tolist(),
                             format_func=station_name.get)
        sp_here = spaces[(spaces["station_id"] == st_id) & spaces["is_active"].astype(bool)].set_index("ad_space_id")
        per_month = T("جنيه/شهر", "EGP/month")
        sp_id = st.selectbox(T("المكان الإعلاني", "Ad space"), sp_here.index.tolist(),
                             format_func=lambda i: f"#{i} {sp_here.loc[i, 'format_l']} "
                                                   f"({sp_here.loc[i, 'monthly_price_egp']:,.0f} {per_month})")
        c = camp_opts.loc[cid]
        b1, b2 = st.columns(2)
        bstart = b1.date_input(T("من ", "From "), c["start_date"].date(), format="DD/MM/YYYY")
        bend = b2.date_input(T("لحد ", "To "), c["end_date"].date(), format="DD/MM/YYYY")
        monthly = float(sp_here.loc[sp_id, "monthly_price_egp"]) if sp_id is not None else 0.0
        suggested = round(monthly * max(1, ((bend - bstart).days + 1) / 30) / 500) * 500
        price = st.number_input(T("القيمة (جنيه)", "Value (EGP)"), min_value=0, value=int(suggested), step=500, format="%d")
        if st.button(T("احجز المكان", "Book space"), type="primary", disabled=sp_id is None):
            if bend < bstart:
                st.error(T("تاريخ النهاية لازم يكون بعد البداية.", "The end date must be after the start date."))
            else:
                try:
                    bid = writes.add_booking(eng, int(cid), int(sp_id), bstart, bend, float(price))
                except writes.BookingConflict:
                    st.error(T("المكان ده محجوز في جزء من الفترة دي. اختار تواريخ تانية أو مكان تاني.",
                               "This space is booked for part of that period. Pick other dates or another space."))
                else:
                    cm.refresh()
                    st.success(T(f"اتسجّل الحجز رقم {bid}.", f"Saved booking #{bid}."))

# ---------------------------------------------------------------- prices & spaces
with t_prices:
    st.markdown(T("عدّل السعر الشهري أو وقّف مكان، وبعدين اضغط **احفظ التعديلات**. الأماكن المتوقفة مش بتظهر في الترشيحات.",
                  "Edit a monthly price or switch a space off, then press **Save changes**. Inactive spaces are "
                  "left out of recommendations."))
    ALL = "__all__"
    pst = st.selectbox(T("المحطة ", "Station "), [ALL] + profile.sort_values("rank")["station_id"].tolist(),
                       format_func=lambda i: T("كل المحطات", "All stations") if i == ALL else station_name.get(i))
    sv = spaces if pst == ALL else spaces[spaces["station_id"] == pst]
    base = pd.DataFrame({
        "id": sv["ad_space_id"], "station": sv["station_id"].map(station_name), "fmt": sv["format_l"],
        "range": sv["price_min"].map("{:,.0f}".format) + " – " + sv["price_max"].map("{:,.0f}".format),
        "price": sv["monthly_price_egp"], "active": sv["is_active"].astype(bool),
    }).reset_index(drop=True)
    edited = st.data_editor(base, hide_index=True, use_container_width=True, key=f"prices_{L}_{pst}",
                            disabled=["id", "station", "fmt", "range"], column_config={
                                "id": st.column_config.Column(T("رقم المكان", "Space #")),
                                "station": st.column_config.Column(T("المحطة", "Station")),
                                "fmt": st.column_config.Column(T("نوع الإعلان", "Format")),
                                "range": st.column_config.Column(T("نطاق السوق", "Market range")),
                                "price": st.column_config.NumberColumn(T("السعر الشهري", "Monthly price"), format="%d",
                                                                       min_value=0, step=500),
                                "active": st.column_config.CheckboxColumn(T("شغال", "Active")),
                            })
    changed = edited[(edited["price"] != base["price"]) | (edited["active"] != base["active"])]
    if st.button(T(f"💾 احفظ التعديلات ({len(changed)})", f"💾 Save changes ({len(changed)})"), type="primary",
                 disabled=changed.empty):
        n = writes.update_spaces(eng, [{"ad_space_id": r["id"], "monthly_price_egp": r["price"], "is_active": r["active"]}
                                       for _, r in changed.iterrows()])
        cm.refresh()
        st.success(T(f"اتحفظ {n} تعديل.", f"Saved {n} change(s)."))
        st.rerun()
