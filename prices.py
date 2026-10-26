import pandas as pd
import streamlit as st

import common as cm

spaces = cm.data()["spaces"]

cm.header("الأسعار ومصادرها", "كل الأسعار شهرية بالجنيه المصري، قبل ضريبة القيمة المضافة 14%.")

with st.container(border=True):
    st.markdown(
        "أسعار الإعلانات جوه مترو القاهرة **مش منشورة للجمهور**، والجهة اللي ماسكة الإعلانات بتديها للمعلن لما يطلبها. "
        "عشان كده كل نوع إعلان اتربط بأقرب سعر **منشور فعلًا** في سوق الإعلانات الخارجية في مصر. "
        "المحطات الأكتر زحمة والأعلى في القوة الشرائية سعرها في أعلى النطاق، والأهدى في أوله. "
        "الأنواع اللي مالهاش سعر منشور متعلّم عليها **تقدير**.")
    fm = (spaces.groupby(["format_ar", "price_basis", "price_min", "price_max", "price_source"], dropna=False)
          .agg(count=("ad_space_id", "count"), avg=("monthly_price_egp", "mean")).reset_index()
          .sort_values("price_max", ascending=False))
    st.dataframe(pd.DataFrame({
        "نوع الإعلان": fm["format_ar"],
        "أقل سعر": fm["price_min"], "أعلى سعر": fm["price_max"], "متوسط السعر في المترو": fm["avg"].round(-2),
        "عدد الأماكن": fm["count"],
        "الأساس": fm["price_basis"].map(cm.AR_BASIS),
        "المصدر": fm["price_source"],
    }), hide_index=True, use_container_width=True, column_config={
        "أقل سعر": st.column_config.NumberColumn(format="%d"),
        "أعلى سعر": st.column_config.NumberColumn(format="%d"),
        "متوسط السعر في المترو": st.column_config.NumberColumn(format="%d"),
    })
    cm.html(
        '<p class="note">المصادر: '
        '<a href="https://entasher.com/Blog/190/Cost-of-billboard-advertising-in-Egypt-billboards-in-egypt-price">Entasher، تكلفة إعلانات اللوحات في مصر</a>، و'
        '<a href="https://alaanak.com/billboard-price-in-egypt-guide-digital-vs-traditional-options/">Alaanak، دليل أسعار اللوحات في مصر (يوليو 2025)</a>. '
        'الحجوزات والمعلنين الموجودين من الأول بيانات تجريبية للتحليل.</p>')
