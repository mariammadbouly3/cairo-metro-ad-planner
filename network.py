import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import common as cm
from common import T

d = cm.data()
profile, line_order = d["profile"], d["line_order"]

cm.header(T("شبكة المترو", "Metro network"),
          T("الخطوط التلاتة بفروعها، وكل محطة حجمها على قد درجتها الإعلانية، وتحت تقسيم المحطات لمجموعات بالـ Machine Learning.",
            "All three lines with their branches, each station sized by its ad score, and below, machine-learning "
            "segments of the stations."))

with st.container(border=True):
    lo = line_order.dropna(subset=["latitude"]).copy()
    lo["line"] = "L" + lo["line_number"].astype(str)
    lo["trace"] = lo["line"] + " " + lo["branch"].fillna("Trunk")
    kitkat = lo[(lo["line"] == "L3") & (lo["name_en"] == "Kit Kat")]
    lo = pd.concat([lo, kitkat.assign(trace="L3 Cairo University branch", stop_order=29.5),
                    kitkat.assign(trace="L3 Rod El-Farag branch", stop_order=23.5)]).sort_values(["trace", "stop_order"])
    lo["line_l"] = lo["line"].map(lambda x: cm.lbl("line", x))
    net = px.line_map(lo, lat="latitude", lon="longitude", color="line_l", line_group="trace", hover_name="name_l",
                      color_discrete_map=cm.line_colors(), labels={"line_l": ""},
                      zoom=10.3, center={"lat": 30.06, "lon": 31.27}, map_style="carto-darkmatter")
    net.update_traces(line=dict(width=5))
    pts = profile.dropna(subset=["latitude"])
    net.add_trace(go.Scattermap(
        lat=pts["latitude"], lon=pts["longitude"], mode="markers",
        marker=dict(size=(pts["ad_score"] / 5 + 6).tolist(),
                    color=[cm.INTER if i else "#FFFFFF" for i in pts["is_interchange"]], opacity=.9),
        text=pts["name_l"] + T("، الدرجة ", ", score ") + pts["ad_score"].round(1).astype(str), hoverinfo="text",
        name=T("محطة (البنفسجي = تحويل)", "Station (purple = interchange)")))
    st.plotly_chart(cm.style_fig(net, 600), use_container_width=True)
    cm.html('<p class="note">' + T("5 محطات اتفتحت سنة 2024 مالهاش إحداثيات منشورة، فمش ظاهرة على الخريطة.",
                                   "5 stations opened in 2024 have no published coordinates, so they are not on the map.") + "</p>")

n1, n2 = st.columns(2)
with n1, st.container(border=True):
    by_tier = profile.groupby("tier_l", as_index=False).agg(riders=("avg_daily_riders", "sum"))
    pie = px.pie(by_tier, names="tier_l", values="riders", hole=.6, color="tier_l",
                 color_discrete_map=cm.tier_colors(), title=T("الركاب اليوميين حسب فئة المحطة", "Daily riders by station tier"))
    pie.update_traces(textfont_color="#0B1226")
    st.plotly_chart(cm.style_fig(pie, 360), use_container_width=True)
with n2, st.container(border=True):
    top = profile.nlargest(10, "ad_score").sort_values("ad_score")
    tb = px.bar(top, x="ad_score", y="name_l", orientation="h", title=T("أعلى 10 محطات في الدرجة الإعلانية", "Top 10 stations by ad score"),
                labels={"ad_score": T("الدرجة", "Score"), "name_l": ""}, color_discrete_sequence=[cm.L1])
    tb.update_yaxes(side=cm.y_side())
    st.plotly_chart(cm.style_fig(tb, 360), use_container_width=True)

# ---------------------------------------------------------------- K-means segments
import models  # noqa: E402


@st.cache_data(ttl=3600, show_spinner=False)
def segments(profile_df):
    return models.station_clusters(profile_df)


sg = segments(profile)
seg = sg.stations.merge(profile[["station_id", "name_l", "latitude", "longitude", "avg_daily_riders", "ad_score",
                                 "lines_l", "tier_l"]], on="station_id")
seg_name = lambda k: models.SEGMENTS[k][0 if cm.is_ar() else 1]  # noqa: E731
seg_pitch = lambda k: models.SEGMENTS[k][2 if cm.is_ar() else 3]  # noqa: E731
seg["seg_l"] = seg["segment"].map(seg_name)
SEG_COLORS = {"hub": cm.GOLD, "cbd": cm.L1, "upscale": cm.INTER, "dense": cm.L2, "edge": cm.L3}
seg_colors = {seg_name(k): c for k, c in SEG_COLORS.items()}

with st.container(border=True):
    st.markdown(T("#### تقسيم المحطات (K-Means)", "#### Station segments (K-means)"))
    st.markdown(T(f"الـ 84 محطة اتقسموا لـ {sg.k} مجموعات متشابهة حسب الزحمة والقوة الشرائية وطبيعة المنطقة واللي "
                  "حواليها (جامعات، أسواق، أماكن سياحية). كل مجموعة ليها نوع معلنين مناسب.",
                  f"The 84 stations fall into {sg.k} groups of similar stations, based on footfall, spending power, "
                  "area type and what is nearby (universities, markets, tourist sites). Each group suits different "
                  "advertisers."))
    s1, s2 = st.columns([1.35, 1])
    with s1:
        sm = seg.dropna(subset=["latitude"])
        fig = px.scatter_map(sm, lat="latitude", lon="longitude", color="seg_l", hover_name="name_l",
                             size=(sm["ad_score"] / 5 + 4), size_max=16, color_discrete_map=seg_colors,
                             hover_data={"lines_l": True, "avg_daily_riders": ":,", "latitude": False, "longitude": False},
                             labels={"seg_l": "", "lines_l": T("الخطوط", "Lines"), "avg_daily_riders": T("ركاب يوميًا", "Daily riders")},
                             zoom=10.2, center={"lat": 30.06, "lon": 31.27}, map_style="carto-darkmatter")
        st.plotly_chart(cm.style_fig(fig, 460), use_container_width=True)
    with s2:
        cards = ""
        for _, r in sg.profile.iterrows():
            names = T("، ", ", ").join(seg.loc[seg["segment"] == r["segment"]].nlargest(3, "ad_score")["name_l"])
            cards += (f'<div class="kpi" style="margin-bottom:.55rem;border-color:{SEG_COLORS[r["segment"]]}">'
                      f'<b style="font-size:1.05rem">{seg_name(r["segment"])} · {int(r["stations"])}</b>'
                      f'<small>{seg_pitch(r["segment"])}<br>{T("زي", "e.g.")} {names} · '
                      f'{T("متوسط", "avg")} {int(r["riders"]):,} {T("راكب", "riders")}</small></div>')
        cm.html(cards)

    with st.expander(T("التقسيم ده اتعمل إزاي؟", "How were the segments made?")):
        st.markdown(T(
            "- 11 خاصية لكل محطة: عدد الركاب (لوغاريتم)، القوة الشرائية، الدرجة الإعلانية، قربها من جامعة أو سوق أو مكان سياحي، "
            "هل هي محطة تحويل أو مركز مواصلات، وطبيعة المنطقة.\n"
            "- الخصائص اتوحّدت (StandardScaler) عشان مفيش واحدة تطغى على الباقي، وبعدين **K-Means** من scikit-learn.\n"
            f"- اخترنا {sg.k} مجموعات: الـ silhouette (مدى وضوح الفصل بين المجموعات) بيتحسن كتير لحد {sg.k} وبعدها الزيادة "
            "بسيطة، والمجموعات بتبقى صغيرة وصعب تتفهم.\n"
            "- اسم كل مجموعة اتحدد من أكتر حاجة مميزة في مركزها (مثلًا كلها محطات تحويل، أو كلها أحياء راقية).",
            "- 11 features per station: riders (log), purchasing power, ad score, near a university, market or tourist "
            "site, interchange or transport hub, and area type.\n"
            "- Features are standardised (StandardScaler) so none dominates, then clustered with scikit-learn **K-means**.\n"
            f"- We chose {sg.k} groups: the silhouette score (how cleanly groups separate) improves a lot up to {sg.k}, "
            "then only a little, and more groups get small and hard to interpret.\n"
            "- Each group is named after what stands out at its centre (e.g. all interchanges, or all upscale areas)."))
        sil = sg.silhouette.copy()
        sil["k"] = sil["k"].astype(str)
        sb = px.bar(sil, x="k", y="score", labels={"k": T("عدد المجموعات", "Number of groups"), "score": "Silhouette"},
                    color=(sil["k"] == str(sg.k)).map({True: "chosen", False: "other"}),
                    color_discrete_map={"chosen": cm.GOLD, "other": "#6C7891"})
        sb.update_layout(showlegend=False)
        sb.update_xaxes(categoryorder="array", categoryarray=sil["k"].tolist())
        st.plotly_chart(cm.style_fig(sb, 260), use_container_width=True)
        pca = px.scatter(seg, x="x", y="y", color="seg_l", hover_name="name_l", color_discrete_map=seg_colors,
                         labels={"x": "PCA 1", "y": "PCA 2", "seg_l": ""},
                         title=T("المحطات في بُعدين (PCA)", "Stations in two dimensions (PCA)"))
        st.plotly_chart(cm.style_fig(pca, 340), use_container_width=True)
