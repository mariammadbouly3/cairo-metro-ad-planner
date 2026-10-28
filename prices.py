import pandas as pd
import streamlit as st

import common as cm
from common import T

spaces = cm.data()["spaces"]

cm.header(T("الأسعار ومصادرها", "Prices and sources"),
          T("كل الأسعار شهرية بالجنيه المصري، قبل ضريبة القيمة المضافة 14%.",
            "All prices are monthly, in Egyptian pounds, before 14% VAT."))

with st.container(border=True):
    st.markdown(T(
        "أسعار الإعلانات جوه مترو القاهرة **مش منشورة للجمهور**، والجهة اللي ماسكة الإعلانات بتديها للمعلن لما يطلبها. "
        "عشان كده كل نوع إعلان اتربط بأقرب سعر **منشور فعلًا** في سوق الإعلانات الخارجية في مصر. "
        "المحطات الأكتر زحمة والأعلى في القوة الشرائية سعرها في أعلى النطاق، والأهدى في أوله. "
        "الأنواع اللي مالهاش سعر منشور متعلّم عليها **تقدير**.",
        "Cairo Metro's ad rate card is **not published**: the media owner shares it with advertisers on request. "
        "So each format is priced against the closest **published** Egyptian outdoor-advertising rate. Busier, more "
        "affluent stations sit at the top of the range and quieter ones at the bottom. Formats with no published "
        "price are marked **estimate**."))
    fm = (spaces.groupby(["format_name", "price_basis", "price_min", "price_max", "price_source"], dropna=False)
          .agg(count=("ad_space_id", "count"), avg=("monthly_price_egp", "mean")).reset_index()
          .sort_values("price_max", ascending=False))
    c_lo, c_hi, c_avg = T("أقل سعر", "Min"), T("أعلى سعر", "Max"), T("متوسط السعر في المترو", "Metro average")
    st.dataframe(pd.DataFrame({
        T("نوع الإعلان", "Format"): fm["format_name"].map(lambda x: cm.lbl("format", x)),
        c_lo: fm["price_min"], c_hi: fm["price_max"], c_avg: fm["avg"].round(-2),
        T("عدد الأماكن", "Spaces"): fm["count"],
        T("الأساس", "Basis"): fm["price_basis"].map(lambda x: cm.lbl("basis", x)),
        T("المصدر", "Source"): fm["price_source"],
    }), hide_index=True, use_container_width=True, column_config={
        c_lo: st.column_config.NumberColumn(format="%d"),
        c_hi: st.column_config.NumberColumn(format="%d"),
        c_avg: st.column_config.NumberColumn(format="%d"),
    })
    cm.html(
        '<p class="note">' + T("المصادر: ", "Sources: ") +
        '<a href="https://entasher.com/Blog/190/Cost-of-billboard-advertising-in-Egypt-billboards-in-egypt-price">'
        + T("Entasher، تكلفة إعلانات اللوحات في مصر", "Entasher, cost of billboard advertising in Egypt") + '</a>' + T("، و", ", ") +
        '<a href="https://alaanak.com/billboard-price-in-egypt-guide-digital-vs-traditional-options/">'
        + T("Alaanak، دليل أسعار اللوحات في مصر (يوليو 2025)", "Alaanak, billboard price guide for Egypt (Jul 2025)") + '</a>. '
        + T("الحجوزات والمعلنين الموجودين من الأول بيانات تجريبية للتحليل.",
            "The original advertisers and bookings are simulated demo data.") + '</p>')
