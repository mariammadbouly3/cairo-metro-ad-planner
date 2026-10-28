import datetime as dt
import html as _h
import re

import pandas as pd
import streamlit as st

import common as cm
import writes
from common import T

d = cm.data()
profile = d["profile"]
ordered = profile.sort_values("avg_daily_riders", ascending=False).set_index("station_id")

cm.header(T("اشتراك المترو السنوي", "Annual metro pass"),
          T("اطلب كارت الاشتراك السنوي واكتب عنوان بيتك، والكارت يوصلك لحد الباب.",
            "Request an annual metro pass with your home address, and the card is delivered to your door."))
st.info(T("ده **نموذج تجريبي** ضمن مشروع تحليل بيانات، مش خدمة رسمية من مترو الأنفاق، ومفيش كارت حقيقي هيتبعت. "
          "للاشتراك الحقيقي روح أقرب مكتب اشتراكات في المترو.",
          "This is a **demo** in a data-analytics project, not an official Cairo Metro service, and no real card is "
          "sent. For a real pass, visit a metro subscription office."), icon="ℹ️")

cm.html(f"""
<style>
.metro-card {{ position:relative; max-width:430px; aspect-ratio: 1.586; border-radius:20px; padding:1.1rem 1.3rem;
  background: linear-gradient(135deg, #16224A 0%, {cm.NAVY} 55%, #1F1846 100%); border:1px solid rgba(255,255,255,.25);
  box-shadow: 0 18px 40px rgba(0,0,0,.35); color:{cm.INK}; overflow:hidden; display:flex; flex-direction:column; gap:.35rem; }}
.metro-card .bars {{ margin:0 0 .3rem; }}
.metro-card .kind {{ font-size:.8rem; color:{cm.MUTED}; letter-spacing:.04em; }}
.metro-card .name {{ font-size:1.35rem; font-weight:700; line-height:1.25; }}
.metro-card .row {{ display:flex; justify-content:space-between; gap:1rem; margin-top:auto; font-size:.85rem; }}
.metro-card .row b {{ display:block; font-size:.98rem; }}
.metro-card .row small {{ color:{cm.MUTED}; }}
.metro-card .demo {{ position:absolute; inset-inline-end:-38px; top:22px; transform: rotate({45 if not cm.is_ar() else -45}deg);
  background:{cm.GOLD}; color:{cm.NAVY}; font-weight:700; font-size:.75rem; padding:.2rem 2.6rem; }}
.steps {{ display:flex; gap:.4rem; flex-wrap:wrap; margin:.6rem 0; }}
.steps span {{ padding:.35rem .9rem; border-radius:999px; background:rgba(255,255,255,.08); color:{cm.MUTED}; font-size:.88rem; }}
.steps span.done {{ background:rgba(27,158,107,.35); color:{cm.INK}; }}
.steps span.now {{ background:{cm.L1}; color:#fff; font-weight:600; }}
</style>""")


def egp(x):
    return T(f"{x:,.0f} جنيه", f"EGP {x:,.0f}")


def card(name, home, plan, start, number=None):
    end = start + dt.timedelta(days=364)
    return f"""
    <div class="metro-card">
      <div class="demo">{T("تجريبي", "DEMO")}</div>
      <div class="bars"><span style="width:70px;background:{cm.L1}"></span><span style="width:45px;background:{cm.L2}"></span>
        <span style="width:60px;background:{cm.L3}"></span></div>
      <div class="kind">{T("اشتراك المترو", "METRO PASS")} · {cm.lbl("plan", plan)}</div>
      <div class="name">{_h.escape(name) or T("اسمك هنا", "Your name")}</div>
      <div class="row">
        <div><small>{T("محطة البيت", "Home station")}</small><b>{_h.escape(home)}</b></div>
        <div><small>{T("صالح لحد", "Valid until")}</small><b>{end:%d/%m/%Y}</b></div>
        <div><small>{T("رقم الكارت", "Card no.")}</small><b>{f"#{number:06d}" if number else "—"}</b></div>
      </div>
    </div>"""


p1, p2 = st.columns(2)
for col, plan in ((p1, "annual_2"), (p2, "annual_3")):
    with col:
        cm.html(f'<div class="kpi"><b>{egp(cm.PLANS[plan])}</b><small>{cm.lbl("plan", plan)} · '
                f'{T("حوالي", "about")} {egp(cm.PLANS[plan] / 12)} {T("في الشهر", "a month")}</small></div>')
cm.html(f'<p class="note">{T("الأسعار الرسمية المنشورة لاشتراك المترو السنوي (أسعار 2025)، ", "Published Cairo Metro annual pass prices (2025 tariff), ")}'
        f'<a href="{cm.PLAN_SOURCE}">{T("المصدر", "source")}</a>. '
        f'{T("كل خطين بينهم محطة تحويل، فاشتراك الخطين بيكفي أغلب الرحلات.", "Every pair of lines shares an interchange, so the 2-line pass covers most trips.")}</p>')

tab_new, tab_track = st.tabs([T("🎫 اطلب الكارت", "🎫 Request a card"), T("📦 تابع طلبك", "📦 Track your request")])

# ---------------------------------------------------------------- request
PHONE = re.compile(r"^01[0125]\d{8}$")
OTHER = "__other__"
with tab_new:
    left, right = st.columns([1.25, 1])
    with left:
        st.markdown(T("#### بياناتك", "#### Your details"))
        name = st.text_input(T("الاسم بالكامل *", "Full name *"), max_chars=120)
        phone = st.text_input(T("رقم الموبايل *", "Mobile number *"), placeholder="01xxxxxxxxx", max_chars=20)

        st.markdown(T("#### عنوان التوصيل", "#### Delivery address"))
        g1, g2 = st.columns(2)
        govs = ["Cairo", "Giza", "Qalyubia"]
        gov = g1.selectbox(T("المحافظة", "Governorate"), govs, format_func=lambda x: cm.lbl("gov", x))
        districts = sorted(profile.loc[profile["governorate"] == gov, "district"].dropna().unique(),
                           key=lambda x: cm.lbl("district", x))
        district = g2.selectbox(T("المنطقة", "Area"), districts + [OTHER],
                                format_func=lambda x: T("منطقة تانية", "Another area") if x == OTHER else cm.lbl("district", x))
        address = st.text_area(T("العنوان بالتفصيل *", "Full address *"), max_chars=300,
                               placeholder=T("الشارع، رقم العمارة، الدور، الشقة، علامة مميزة",
                                             "Street, building no., floor, flat, landmark"))

        st.markdown(T("#### رحلتك", "#### Your trip"))
        near = ordered[ordered["district"] == district].index.tolist() if district != OTHER else []
        gov_st = ordered[ordered["governorate"] == gov].index.tolist()
        options = near + [i for i in gov_st if i not in near] + [i for i in ordered.index if i not in gov_st and i not in near]
        home = st.selectbox(T("محطة البيت (أقرب محطة ليك)", "Home station (nearest to you)"), options,
                            format_func=lambda i: f"{ordered.loc[i, 'name_l']} · {ordered.loc[i, 'lines_l']}",
                            help=T("محطات منطقتك ظاهرة الأول.", "Stations in your area are listed first."))
        work = st.selectbox(T("بتروح فين أكتر؟ (شغل أو دراسة، اختياري)", "Where do you ride to most? (work or study, optional)"),
                            [None] + [i for i in ordered.index if i != home],
                            format_func=lambda i: T("مش محدد", "Not set") if i is None else ordered.loc[i, "name_l"])
        p_a, p_b = st.columns(2)
        plan = p_a.radio(T("نوع الاشتراك", "Pass"), list(cm.PLANS), format_func=lambda x: f"{cm.lbl('plan', x)} · {egp(cm.PLANS[x])}")
        start = p_b.date_input(T("يبدأ من", "Starts on"), cm.today() + dt.timedelta(days=7),
                               min_value=cm.today(), max_value=cm.today() + dt.timedelta(days=90), format="DD/MM/YYYY")
        agree = st.checkbox(T("فاهم إن ده نموذج تجريبي ومفيش كارت حقيقي هيتبعت", "I understand this is a demo and no real card is sent"))
        send = st.button(T("ابعت الطلب", "Send request"), type="primary", use_container_width=True)

    with right:
        st.markdown(T("#### شكل الكارت", "#### Your card"))
        slot = st.empty()
        with slot.container():
            cm.html(card(name, ordered.loc[home, "name_l"], plan, start))
        cm.html('<p class="note">' + T("الكارت بيوصل خلال 7 لـ 10 أيام من الموافقة. هتحتاج بطاقتك عند الاستلام.",
                                       "The card arrives 7 to 10 days after approval. Have your ID ready on delivery.") + "</p>")

    if send:
        digits = re.sub(r"\D", "", phone or "")
        problems = []
        if len(name.strip()) < 3:
            problems.append(T("اكتب اسمك بالكامل.", "Enter your full name."))
        if not PHONE.match(digits):
            problems.append(T("رقم الموبايل لازم يكون 11 رقم ويبدأ بـ 010 أو 011 أو 012 أو 015.",
                              "The mobile number must be 11 digits starting with 010, 011, 012 or 015."))
        if len(address.strip()) < 10:
            problems.append(T("اكتب العنوان بالتفصيل عشان الكارت يوصل.", "Enter the full address so the card can be delivered."))
        if not agree:
            problems.append(T("علّم على خانة الموافقة الأول.", "Tick the confirmation box first."))
        if problems:
            for p in problems:
                st.error(p)
        else:
            sid = writes.add_subscription(cm.engine(), name, digits, gov, None if district == OTHER else district, address,
                                          home, work, plan, cm.PLANS[plan], start)
            cm.refresh()
            with slot.container():
                cm.html(card(name, ordered.loc[home, "name_l"], plan, start, sid))
            st.success(T(f"وصل طلبك رقم **{sid}**. احتفظ بالرقم ده، وتقدر تتابع الطلب من تبويب **تابع طلبك** برقم الطلب ورقم موبايلك.",
                         f"Request **#{sid}** received. Keep this number: you can track it in **Track your request** "
                         "with the request number and your mobile number."))
            st.balloons()

# ---------------------------------------------------------------- tracking
STEPS = ["pending", "approved", "shipped", "delivered"]
with tab_track:
    t1, t2 = st.columns(2)
    num = t1.number_input(T("رقم الطلب", "Request number"), min_value=1, step=1, value=None, format="%d")
    tphone = t2.text_input(T("رقم الموبايل اللي سجّلت بيه", "The mobile number you used"), placeholder="01xxxxxxxxx")
    if st.button(T("تابع", "Track"), type="primary"):
        row = writes.track_subscription(cm.engine(), int(num), tphone) if num else None
        if not row:
            st.error(T("مفيش طلب بالرقم ده والموبايل ده. اتأكد من الاتنين.", "No request matches that number and mobile. Check both."))
        else:
            status = row["status"]
            if status == "cancelled":
                st.warning(T("الطلب ده اتلغى. لو ده غلط، اطلب كارت جديد.", "This request was cancelled. If that's a mistake, request a new card."))
            else:
                k = STEPS.index(status)
                steps = "".join(f'<span class="{"now" if i == k else "done" if i < k else ""}">{"✓ " if i < k else ""}'
                                f'{cm.lbl("sub_status", s)}</span>' for i, s in enumerate(STEPS))
                cm.html(f'<div class="steps">{steps}</div>')
            cm.html(card(row["full_name"], ordered.loc[row["home_station_id"], "name_l"] if row["home_station_id"] in ordered.index
                         else "—", row["plan"], pd.Timestamp(row["start_date"]).date(), row["subscription_id"]))
