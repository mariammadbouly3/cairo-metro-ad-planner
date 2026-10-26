import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import common as cm

d = cm.data()
profile, line_order = d["profile"], d["line_order"]

cm.header("شبكة المترو", "الخطوط التلاتة بفروعها، وكل محطة حجمها على قد درجتها الإعلانية.")

with st.container(border=True):
    lo = line_order.dropna(subset=["latitude"]).copy()
    lo["line"] = "L" + lo["line_number"].astype(str)
    lo["trace"] = lo["line"] + " " + lo["branch"].fillna("Trunk")
    kitkat = lo[(lo["line"] == "L3") & (lo["name_en"] == "Kit Kat")]
    lo = pd.concat([lo, kitkat.assign(trace="L3 Cairo University branch", stop_order=29.5),
                    kitkat.assign(trace="L3 Rod El-Farag branch", stop_order=23.5)]).sort_values(["trace", "stop_order"])
    lo["الخط"] = lo["line"].map(cm.AR_LINE)
    net = px.line_map(lo, lat="latitude", lon="longitude", color="الخط", line_group="trace", hover_name="name_ar",
                      color_discrete_map={cm.AR_LINE[k]: v for k, v in cm.LINE_COLORS.items()},
                      zoom=10.3, center={"lat": 30.06, "lon": 31.27}, map_style="carto-darkmatter")
    net.update_traces(line=dict(width=5))
    pts = profile.dropna(subset=["latitude"])
    net.add_trace(go.Scattermap(
        lat=pts["latitude"], lon=pts["longitude"], mode="markers",
        marker=dict(size=(pts["ad_score"] / 5 + 6).tolist(),
                    color=[cm.INTER if i else "#FFFFFF" for i in pts["is_interchange"]], opacity=.9),
        text=pts["name_ar"] + "، الدرجة " + pts["ad_score"].round(1).astype(str), hoverinfo="text",
        name="محطة (البنفسجي = تحويل)"))
    st.plotly_chart(cm.style_fig(net, 600), use_container_width=True)
    cm.html('<p class="note">5 محطات اتفتحت سنة 2024 مالهاش إحداثيات منشورة، فمش ظاهرة على الخريطة.</p>')

n1, n2 = st.columns(2)
with n1, st.container(border=True):
    by_tier = profile.groupby("tier_ar", as_index=False).agg(riders=("avg_daily_riders", "sum"))
    pie = px.pie(by_tier, names="tier_ar", values="riders", hole=.6, color="tier_ar",
                 color_discrete_map=cm.TIER_COLORS, title="الركاب اليوميين حسب فئة المحطة")
    pie.update_traces(textfont_color="#0B1226")
    st.plotly_chart(cm.style_fig(pie, 360), use_container_width=True)
with n2, st.container(border=True):
    top = profile.nlargest(10, "ad_score").sort_values("ad_score")
    tb = px.bar(top, x="ad_score", y="name_ar", orientation="h", title="أعلى 10 محطات في الدرجة الإعلانية",
                labels={"ad_score": "الدرجة", "name_ar": ""}, color_discrete_sequence=[cm.L1])
    tb.update_yaxes(side="right")
    st.plotly_chart(cm.style_fig(tb, 360), use_container_width=True)
