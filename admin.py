import datetime as dt
import hmac

import pandas as pd
import streamlit as st

import common as cm
import writes
from recommender import AUDIENCES, INDUSTRY_AUDIENCE

cm.header("الإدارة", "راجع الحجوزات، وضيف حملات وحجوزات، وعدّل الأسعار. أي تغيير بيظهر على طول في كل الصفحات وفي Power BI.")

# ---------------------------------------------------------------- password gate
expected = cm.admin_password()
if not expected:
    st.warning("صفحة الإدارة مقفولة لحد ما تحدد كلمة مرور لها. ضيف ADMIN_PASSWORD في الـ Secrets بتاعة التطبيق "
               "(أو في ملف .streamlit/secrets.toml لو شغالة على اللاب).")
    st.stop()

if not st.session_state.get("is_admin"):
    with st.form("login"):
        pw = st.text_input("كلمة مرور الإدارة", type="password")
        if st.form_submit_button("دخول", type="primary"):
            if hmac.compare_digest(pw, expected):
                st.session_state["is_admin"] = True
                st.rerun()
            else:
                st.error("كلمة المرور غلط.")
    st.stop()

if st.button("خروج"):
    st.session_state["is_admin"] = False
    st.rerun()

eng = cm.engine()
d = cm.data()
profile, spaces, campaigns, bk = d["profile"], d["spaces"], d["campaigns"], d["bookings"]
station_name = profile.set_index("station_id")["name_ar"]


def booking_table(df):
    j = (df.merge(spaces[["ad_space_id", "station_id", "format_ar"]], on="ad_space_id")
           .merge(campaigns[["campaign_id", "campaign_name", "company_name"]], on="campaign_id"))
    return pd.DataFrame({
        "اختيار": False,
        "رقم الحجز": j["booking_id"],
        "المعلن": j["company_name"],
        "الحملة": j["campaign_name"],
        "المحطة": j["station_id"].map(station_name),
        "نوع الإعلان": j["format_ar"],
        "من": j["start_date"].dt.date,
        "لحد": j["end_date"].dt.date,
        "القيمة": j["price_egp"],
        "الحالة": j["status"].map(cm.AR_STATUS),
    })


t_review, t_all, t_new, t_prices = st.tabs(["📥 حجوزات للمراجعة", "📚 كل الحجوزات", "➕ حملة أو حجز جديد", "🏷️ الأسعار والأماكن"])

# ---------------------------------------------------------------- review pending web bookings
with t_review:
    pend = bk[bk["status"] == "pending"].sort_values("created_at", ascending=False)
    if pend.empty:
        st.success("مفيش حجوزات مستنية مراجعة.")
    else:
        st.markdown(f"**{len(pend)}** حجز جه من الموقع. علّم على اللي عايز توافق عليه أو تلغيه.")
        ed = st.data_editor(booking_table(pend), hide_index=True, use_container_width=True, key="pend",
                            disabled=[c for c in booking_table(pend).columns if c != "اختيار"],
                            column_config={"القيمة": st.column_config.NumberColumn(format="%d")})
        ids = ed.loc[ed["اختيار"], "رقم الحجز"].tolist()
        a, b, c = st.columns(3)
        if a.button(f"✅ موافقة ({len(ids)})", disabled=not ids, use_container_width=True, type="primary"):
            writes.set_booking_status(eng, ids, "confirmed")
            cm.refresh()
            st.rerun()
        if b.button(f"❌ إلغاء ({len(ids)})", disabled=not ids, use_container_width=True):
            writes.set_booking_status(eng, ids, "cancelled")
            cm.refresh()
            st.rerun()
        if c.button("✅ موافقة على الكل", use_container_width=True):
            writes.set_booking_status(eng, pend["booking_id"].tolist(), "confirmed")
            cm.refresh()
            st.rerun()

# ---------------------------------------------------------------- all bookings
with t_all:
    f1, f2, f3 = st.columns(3)
    status_pick = f1.multiselect("الحالة", list(cm.AR_STATUS), default=["confirmed", "pending"],
                                 format_func=cm.AR_STATUS.get)
    adv_pick = f2.selectbox("المعلن", ["الكل"] + sorted(campaigns["company_name"].unique()))
    only_future = f3.checkbox("الحالية والجاية بس", value=True)
    view = bk[bk["status"].isin(status_pick)]
    if adv_pick != "الكل":
        view = view[view["campaign_id"].isin(campaigns.loc[campaigns["company_name"] == adv_pick, "campaign_id"])]
    if only_future:
        view = view[view["end_date"] >= pd.Timestamp(cm.today())]
    view = view.sort_values("start_date", ascending=False).head(500)
    st.caption(f"{len(view)} حجز (بيظهر أول 500)")
    tbl = booking_table(view)
    ed2 = st.data_editor(tbl, hide_index=True, use_container_width=True, key="all",
                         disabled=[c for c in tbl.columns if c != "اختيار"],
                         column_config={"القيمة": st.column_config.NumberColumn(format="%d")})
    ids2 = ed2.loc[ed2["اختيار"], "رقم الحجز"].tolist()
    a, b = st.columns(2)
    if a.button(f"❌ إلغاء المختار ({len(ids2)})", disabled=not ids2, use_container_width=True):
        writes.set_booking_status(eng, ids2, "cancelled")
        cm.refresh()
        st.rerun()
    if b.button(f"↩️ رجّع المختار لمؤكد ({len(ids2)})", disabled=not ids2, use_container_width=True):
        try:
            writes.set_booking_status(eng, ids2, "confirmed")
        except writes.BookingConflict:
            st.error("مقدرش أرجّع الحجز: المكان اتحجز لحد تاني في نفس الفترة.")
        else:
            cm.refresh()
            st.rerun()

# ---------------------------------------------------------------- new campaign / booking
with t_new:
    left, right = st.columns(2)
    with left, st.form("new_campaign", clear_on_submit=True):
        st.markdown("#### حملة جديدة")
        company = st.text_input("اسم الشركة")
        industry = st.selectbox("المجال", list(INDUSTRY_AUDIENCE), format_func=lambda x: cm.AR_IND.get(x, x))
        cname = st.text_input("اسم الحملة")
        aud = st.selectbox("الجمهور", AUDIENCES, format_func=lambda x: cm.AR_AUD.get(x, x))
        s1, s2 = st.columns(2)
        cstart = s1.date_input("من", cm.today(), format="DD/MM/YYYY")
        cend = s2.date_input("لحد", cm.today() + dt.timedelta(days=29), format="DD/MM/YYYY")
        cbudget = st.number_input("الميزانية (جنيه)", min_value=0, value=200_000, step=10_000, format="%d")
        if st.form_submit_button("ضيف الحملة", type="primary"):
            if not company.strip() or not cname.strip() or cend < cstart:
                st.error("اكتب اسم الشركة والحملة، واتأكد إن تاريخ النهاية بعد البداية.")
            else:
                cid = writes.add_campaign(eng, company, industry, cname, aud, cstart, cend, cbudget)
                cm.refresh()
                st.success(f"اتضافت الحملة رقم {cid}. تقدر تحجز لها أماكن من الجنب.")

    with right, st.container(border=True):
        st.markdown("#### حجز مكان لحملة")
        camp_opts = campaigns.sort_values("campaign_id", ascending=False)
        cid = st.selectbox("الحملة", camp_opts["campaign_id"].tolist(),
                           format_func=lambda i: f"#{i} {camp_opts.set_index('campaign_id').loc[i, 'campaign_name']}")
        st_id = st.selectbox("المحطة", profile.sort_values("rank")["station_id"].tolist(), format_func=station_name.get)
        sp_here = spaces[(spaces["station_id"] == st_id) & spaces["is_active"].astype(bool)]
        sp_id = st.selectbox("المكان الإعلاني", sp_here["ad_space_id"].tolist(),
                             format_func=lambda i: f"#{i} {sp_here.set_index('ad_space_id').loc[i, 'format_ar']} "
                                                   f"({sp_here.set_index('ad_space_id').loc[i, 'monthly_price_egp']:,.0f} جنيه/شهر)")
        c = camp_opts.set_index("campaign_id").loc[cid]
        b1, b2 = st.columns(2)
        bstart = b1.date_input("من ", c["start_date"].date(), format="DD/MM/YYYY")
        bend = b2.date_input("لحد ", c["end_date"].date(), format="DD/MM/YYYY")
        monthly = float(sp_here.set_index("ad_space_id").loc[sp_id, "monthly_price_egp"]) if sp_id else 0.0
        suggested = round(monthly * max(1, ((bend - bstart).days + 1) / 30) / 500) * 500
        price = st.number_input("القيمة (جنيه)", min_value=0, value=int(suggested), step=500, format="%d")
        if st.button("احجز المكان", type="primary", disabled=sp_id is None):
            if bend < bstart:
                st.error("تاريخ النهاية لازم يكون بعد البداية.")
            else:
                try:
                    bid = writes.add_booking(eng, int(cid), int(sp_id), bstart, bend, float(price))
                except writes.BookingConflict:
                    st.error("المكان ده محجوز في جزء من الفترة دي. اختار تواريخ تانية أو مكان تاني.")
                else:
                    cm.refresh()
                    st.success(f"اتسجّل الحجز رقم {bid}.")

# ---------------------------------------------------------------- prices & spaces
with t_prices:
    st.markdown("عدّل السعر الشهري أو وقّف مكان، وبعدين اضغط **احفظ التعديلات**. الأماكن المتوقفة مش بتظهر في الترشيحات.")
    pst = st.selectbox("المحطة ", ["الكل"] + profile.sort_values("rank")["station_id"].tolist(),
                       format_func=lambda i: "كل المحطات" if i == "الكل" else station_name.get(i))
    sv = spaces if pst == "الكل" else spaces[spaces["station_id"] == pst]
    base = pd.DataFrame({
        "رقم المكان": sv["ad_space_id"],
        "المحطة": sv["station_id"].map(station_name),
        "نوع الإعلان": sv["format_ar"],
        "نطاق السوق": sv["price_min"].map("{:,.0f}".format) + " – " + sv["price_max"].map("{:,.0f}".format),
        "السعر الشهري": sv["monthly_price_egp"],
        "شغال": sv["is_active"].astype(bool),
    }).reset_index(drop=True)
    edited = st.data_editor(base, hide_index=True, use_container_width=True, key="prices",
                            disabled=["رقم المكان", "المحطة", "نوع الإعلان", "نطاق السوق"],
                            column_config={"السعر الشهري": st.column_config.NumberColumn(format="%d", min_value=0, step=500)})
    changed = edited[(edited["السعر الشهري"] != base["السعر الشهري"]) | (edited["شغال"] != base["شغال"])]
    if st.button(f"💾 احفظ التعديلات ({len(changed)})", type="primary", disabled=changed.empty):
        n = writes.update_spaces(eng, [{"ad_space_id": r["رقم المكان"], "monthly_price_egp": r["السعر الشهري"],
                                        "is_active": r["شغال"]} for _, r in changed.iterrows()])
        cm.refresh()
        st.success(f"اتحفظ {n} تعديل.")
        st.rerun()
