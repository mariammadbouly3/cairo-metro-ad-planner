import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import common as cm
import models
from common import T

d = cm.data()
profile, spaces = d["profile"], d["spaces"]
daily = cm.daily(d["bookings"])
today = pd.Timestamp(cm.today())
EGP = T("جنيه", "EGP")

cm.header(T("التوقعات (Machine Learning)", "Forecasts (machine learning)"),
          T("نموذجين: واحد بيتوقع إيراد الشهور الجاية، والتاني بيتعلم إيه اللي بيخلّي مكان إعلاني يتحجز أكتر.",
            "Two models: one forecasts revenue for the coming months, the other learns what makes an ad space "
            "get booked more."))


@st.cache_data(ttl=600, show_spinner=False)
def run_forecast(daily_df, n_spaces, this_month, horizon):
    return models.revenue_forecast(models.monthly_occupancy(daily_df, n_spaces), this_month, horizon)


@st.cache_data(ttl=600, show_spinner=T("بيدرّب النموذج...", "Training the model..."))
def run_demand(spaces_df, profile_df, daily_df, start, end):
    return models.demand_model(spaces_df, profile_df, models.space_occupancy(daily_df, start, end))


tab_rev, tab_demand = st.tabs([T("📈 توقع الإيراد", "📈 Revenue forecast"), T("🧠 نموذج الطلب على الأماكن", "🧠 Demand model")])

# ---------------------------------------------------------------- revenue forecast
with tab_rev:
    horizon = st.slider(T("عدد الشهور الجاية", "Months ahead"), 3, 12, 6)
    n_active = int(spaces["is_active"].astype(bool).sum())
    fc = run_forecast(daily, n_active, today, horizon)
    fut, hist = fc.future, fc.history
    nxt = fut.head(3)
    gap = (nxt["forecast"] - nxt["booked"]).clip(lower=0).sum()
    cm.kpis([
        (cm.short_egp(fut["forecast"].sum()), T(f"الإيراد المتوقع في {horizon} شهور", f"Expected revenue, next {horizon} months")),
        (cm.short_egp(fut["booked"].sum()), T("محجوز فعلًا من دلوقتي", "Already booked")),
        (cm.short_egp(gap), T("المطلوب بيعه في أول 3 شهور عشان نوصل للتوقع", "Still to sell in the next 3 months to hit the forecast")),
        (f"{fc.backtest_mape:.0%}", T(f"متوسط الخطأ في اختبار آخر {fc.holdout} شهور", f"Average error on the last {fc.holdout} months (back-test)")),
    ], accent_first=True)

    with st.container(border=True):
        st.markdown(T("#### الإيراد الشهري: الفعلي والمتوقع", "#### Monthly revenue: actual and forecast"))
        lab = lambda ts: f"{cm.month(ts.month)} {ts.year}"  # noqa: E731
        hx = [lab(t) for t in hist["month_start"]]
        fx = [lab(t) for t in fut["month_start"]]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=hx, y=hist["revenue"], name=T("فعلي", "Actual"), marker_color=cm.L1))
        fig.add_trace(go.Bar(x=fx, y=fut["booked"], name=T("محجوز لحد دلوقتي", "Booked so far"), marker_color="#6C7891"))
        fig.add_trace(go.Scatter(x=fx + fx[::-1], y=list(fut["high"]) + list(fut["low"])[::-1], fill="toself", mode="lines",
                                 fillcolor="rgba(242,193,78,.18)", line=dict(width=0), hoverinfo="skip",
                                 name=T("النطاق المتوقع (80%)", "Likely range (80%)")))
        fig.add_trace(go.Scatter(x=fx, y=fut["forecast"], mode="lines+markers", name=T("المتوقع", "Forecast"),
                                 line=dict(color=cm.GOLD, width=3)))
        fig.update_layout(barmode="overlay", yaxis_title=EGP)
        fig.update_xaxes(categoryorder="array", categoryarray=hx + fx)
        st.plotly_chart(cm.style_fig(fig, 420), use_container_width=True)

    c_f, c_b, c_g = T("المتوقع", "Forecast"), T("محجوز", "Booked"), T("المتبقي للبيع", "Left to sell")
    st.dataframe(pd.DataFrame({
        T("الشهر", "Month"): fx, c_f: fut["forecast"].round(-3), T("من", "Low"): fut["low"].round(-3),
        T("لحد", "High"): fut["high"].round(-3), c_b: fut["booked"].round(-3),
        c_g: (fut["forecast"] - fut["booked"]).clip(lower=0).round(-3)}),
        hide_index=True, use_container_width=True,
        column_config={c: st.column_config.NumberColumn(format="%d") for c in
                       (c_f, c_b, c_g, T("من", "Low"), T("لحد", "High"))})

    with st.expander(T("النموذج ده شغال إزاي؟", "How does this model work?")):
        st.markdown(T(
            f"- الإيراد بيتحسب في الشهر اللي الإعلان شغال فيه فعلًا (مش شهر الحجز).\n"
            f"- النموذج **Ridge regression** من scikit-learn: اتجاه عام (الإيراد بيزيد ولا بيقل مع الوقت) + تأثير كل شهر في السنة (موسمية).\n"
            f"- اتدرّب على {len(hist)} شهر كامل. عشان نعرف دقته، دربناه من غير آخر {fc.holdout} شهور وقارنّا توقعه بالحقيقة: "
            f"متوسط الخطأ {fc.backtest_mape:.0%}.\n"
            "- النطاق الأصفر هو المدى اللي الإيراد غالبًا هيقع فيه (80%)، محسوب من أخطاء النموذج على الشهور اللي فاتت.\n"
            "- البيانات دي تجريبية، فالهدف إن الطريقة نفسها تبان، مش الأرقام.",
            "- Revenue is counted in the month an ad actually runs (not the month it was booked).\n"
            "- The model is a scikit-learn **Ridge regression**: an overall trend plus an effect for each calendar "
            "month (seasonality).\n"
            f"- It trains on {len(hist)} complete months. To measure accuracy it was re-trained without the last "
            f"{fc.holdout} months and compared with what really happened: {fc.backtest_mape:.0%} average error.\n"
            "- The yellow band is the range revenue will most likely fall in (80%), from the model's past errors.\n"
            "- The data is simulated, so the point is the method, not the exact numbers."))

# ---------------------------------------------------------------- demand model
with tab_demand:
    end = today.to_period("M").to_timestamp() - pd.Timedelta(days=1)
    start = end + pd.Timedelta(days=1) - pd.DateOffset(months=12)
    dm = run_demand(spaces, profile, daily, start, end)
    tbl = dm.table.merge(profile[["station_id", "name_l", "lines"]], on="station_id")
    tbl["format_l"] = tbl["format_name"].map(lambda x: cm.lbl("format", x))

    cm.kpis([
        (f"{dm.r2:.2f}", T("R² (من 0 لـ 1، كل ما يعلى أحسن)", "R² (0 to 1, higher is better)")),
        (T(f"±{dm.mae * 100:.0f} نقطة", f"±{dm.mae * 100:.0f} pts"), T("متوسط الخطأ في نسبة الإشغال", "Average error in occupancy")),
        (f"{len(tbl)}", T("مكان اتدرّب عليه النموذج", "Spaces the model learned from")),
    ], accent_first=True)

    a, b = st.columns(2)
    with a, st.container(border=True):
        st.markdown(T("#### إيه اللي بيأثر على الحجز أكتر؟", "#### What drives bookings most?"))
        imp = dm.importance.copy()
        imp["f"] = imp["feature"].map(lambda k: models.FEATURES[k][0 if cm.is_ar() else 1])
        ib = px.bar(imp.sort_values("importance"), x="importance", y="f", orientation="h",
                    labels={"importance": T("الأهمية", "Importance"), "f": ""}, color_discrete_sequence=[cm.L3])
        ib.update_xaxes(tickformat=".0%")
        ib.update_yaxes(side=cm.y_side())
        st.plotly_chart(cm.style_fig(ib, 400), use_container_width=True)
    with b, st.container(border=True):
        st.markdown(T("#### الفعلي مقابل توقع النموذج", "#### Actual vs predicted"))
        sc = px.scatter(tbl, x="predicted", y="occupancy", color="format_l", hover_name="name_l",
                        labels={"predicted": T("الإشغال المتوقع", "Predicted occupancy"),
                                "occupancy": T("الإشغال الفعلي", "Actual occupancy"), "format_l": ""},
                        color_discrete_sequence=[cm.L1, cm.L2, cm.L3, cm.INTER, cm.GOLD, "#7FB3F0", "#F08A6A",
                                                 "#5CC79C", "#9C8CF0", "#8E9AB3"])
        sc.add_shape(type="line", x0=0, y0=0, x1=1, y1=1, line=dict(color="rgba(255,255,255,.35)", dash="dot"))
        sc.update_xaxes(tickformat=".0%", range=[0, 1])
        sc.update_yaxes(tickformat=".0%", range=[0, 1])
        sc.update_layout(showlegend=False)
        st.plotly_chart(cm.style_fig(sc, 400), use_container_width=True)
        cm.html('<p class="note">' + T("كل نقطة مكان إعلاني. فوق الخط = بيتحجز أكتر من المتوقع، وتحته = أقل.",
                                       "Each dot is an ad space. Above the line = booked more than expected, below = less.")
                + "</p>")

    def show(df):
        c_o, c_p, c_g, c_pr = (T("الفعلي", "Actual"), T("المتوقع", "Predicted"), T("الفرق", "Gap"),
                               T("السعر الشهري", "Monthly price"))
        st.dataframe(pd.DataFrame({
            T("رقم المكان", "Space #"): df["ad_space_id"], T("المحطة", "Station"): df["name_l"],
            T("الخطوط", "Lines"): df["lines"].map(cm.lines_short), T("نوع الإعلان", "Format"): df["format_l"],
            c_pr: df["monthly_price_egp"], c_o: (df["occupancy"] * 100).round(), c_p: (df["predicted"] * 100).round(),
            c_g: (df["gap"] * 100).round()}), hide_index=True, use_container_width=True, column_config={
            c_pr: st.column_config.NumberColumn(format="%d"), c_o: st.column_config.NumberColumn(format="%d%%"),
            c_p: st.column_config.NumberColumn(format="%d%%"), c_g: st.column_config.NumberColumn(format="%+d")})

    l, r = st.columns(2)
    with l, st.container(border=True):
        st.markdown(T("#### بيتحجز أقل من أمثاله", "#### Booked less than similar spaces"))
        st.markdown(T("النموذج شايف إن المكان ده المفروض يتحجز أكتر. راجع سعره أو مكانه أو اعرضه على معلنين.",
                      "The model expects these to sell better. Check the price or placement, or pitch them to advertisers."))
        show(tbl.nsmallest(8, "gap"))
    with r, st.container(border=True):
        st.markdown(T("#### بيتحجز أكتر من المتوقع", "#### Booked more than expected"))
        st.markdown(T("طلب عالي: ممكن يستحمل زيادة في السعر في الحجز الجاي.",
                      "High demand: these may support a higher price on the next booking."))
        show(tbl.nlargest(8, "gap"))

    with st.expander(T("النموذج ده شغال إزاي؟", "How does this model work?")):
        st.markdown(T(
            f"- لكل مكان إعلاني شغال، حسبنا نسبة الأيام اللي كان محجوز فيها في آخر 12 شهر ({start:%m/%Y} لـ {end:%m/%Y}).\n"
            "- النموذج **Gradient Boosting** من scikit-learn بيتوقع النسبة دي من: عدد ركاب المحطة، الدرجة الإعلانية، "
            "القوة الشرائية، نوع الإعلان، مكانه في المحطة، السعر، وطبيعة المنطقة.\n"
            "- الدقة محسوبة بـ **5-fold cross-validation**: كل مكان اتقيّم بنموذج ماشافهوش وهو بيتدرّب، "
            f"فالـ R² = {dm.r2:.2f} رقم أمين مش متضخّم.\n"
            "- الأهمية محسوبة بـ **permutation importance**: بنلخبط عمود واحد ونشوف دقة النموذج بتقع قد إيه.\n"
            "- البيانات تجريبية، فالهدف إن الطريقة تبان، والنتايج مش توصيات حقيقية للمترو.",
            f"- For every active space we measured the share of days it was booked over the last 12 months "
            f"({start:%m/%Y} to {end:%m/%Y}).\n"
            "- A scikit-learn **Gradient Boosting** model predicts that share from station riders, ad score, "
            "purchasing power, ad format, zone, price and area type.\n"
            "- Accuracy comes from **5-fold cross-validation**: each space is scored by a model that never saw it "
            f"in training, so R² = {dm.r2:.2f} is an honest number.\n"
            "- Importance is **permutation importance**: shuffle one column and see how much accuracy drops.\n"
            "- The data is simulated, so this shows the method; the results are not real advice for the metro."))
