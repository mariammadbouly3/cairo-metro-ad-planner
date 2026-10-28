# 🚇 Cairo Metro Ad Planner · مخطط إعلانات مترو القاهرة

**An end-to-end data project:** an Excel analysis of Cairo Metro's 84 stations became a PostgreSQL database, a live
bilingual web app (Arabic / English) with machine-learning forecasts, and a Power BI dashboard, all reading the same
cloud database.

**▶ Live app:** [Arabic](https://cairo-metro-ad-planner-mwzqpnn7ozdv8uubvti5wu.streamlit.app) ·
[English](https://cairo-metro-ad-planner-mwzqpnn7ozdv8uubvti5wu.streamlit.app/?lang=en)

---

## The problem
An advertiser with a budget wants to reach a specific audience on the metro. Which stations, which ad formats, and
what will it cost? And the metro side wants to know: which spaces sell, which sit empty, and what revenue is coming next.

## What I built

```mermaid
flowchart LR
    A[Excel analysis<br/>84 stations, scores] --> B[(PostgreSQL<br/>Neon cloud)]
    G[GTFS line order<br/>+ coordinates] --> B
    P[Published Egyptian<br/>outdoor-ad prices] --> B
    B --> C[Streamlit web app<br/>Arabic / English]
    B --> D[Power BI dashboard]
    C -- bookings, requests,<br/>price edits --> B
    C --> E[scikit-learn<br/>forecast + demand model]
    C --> F[PDF quotes]
```

| Page | What it does |
|---|---|
| **Dashboard** | Revenue, today's occupancy, live campaigns, revenue by month, line, format, station and advertiser. Refreshes every minute. |
| **Plan & book** | Pick industry, audience, budget and dates; a recommender picks the best *available* spaces, shows them on a map, and books them or downloads a **PDF quote** (Arabic or English). |
| **Request a space** | Public form: choose a station and spaces, leave contact details; the request is held as *pending* for review. |
| **Insights** | Occupancy month by month, occupancy by format × station tier, spend by industry and advertiser, and the least-booked spaces with a suggested action. |
| **Forecasts** | Revenue forecast for the next 3–12 months, and a demand model that explains what makes a space get booked. |
| **Network** | All three lines and both Line 3 branches, stations sized by ad score. |
| **Station** | One station's profile, audience, and the live status of each ad space. |
| **Prices** | Price range per format and the published source behind it. |
| **Admin** | Password protected: approve or cancel bookings and requests, add campaigns, edit prices. |

## Machine learning
- **Revenue forecast:** ridge regression on trend + calendar-month seasonality. Revenue is counted in the months an ad
  actually runs. Accuracy is checked with a **back-test** (the model is re-trained without the last 3 months and
  scored on them), and the forecast shows an 80% range.
- **Demand model:** gradient boosting predicts each space's 12-month occupancy from station riders, ad score,
  purchasing power, format, zone, price and area type. Accuracy is **5-fold cross-validated** (R² ≈ 0.5), and
  **permutation importance** ranks the drivers. Spaces far below their prediction are flagged as under-performing;
  spaces far above it may support a higher price.

## SQL
- `01`–`04`, `06`–`08`: the schema built step by step: lines, stations, ad formats, spaces, advertisers, campaigns, bookings.
- **No double bookings:** an `EXCLUDE USING gist` constraint on `(ad_space_id, daterange)` rejects overlapping bookings
  at database level; cancelled bookings free the space.
- `05_sql_analysis.sql`: 17 business questions using CTEs and window functions (`ROW_NUMBER`, `RANK`, `LAG`, `NTILE`,
  running totals).
- `pbi_*` views feed Power BI directly from the cloud database.

## Stack
PostgreSQL (Neon) · SQL · Python · pandas · SQLAlchemy · scikit-learn · Streamlit · Plotly · ReportLab · Power BI

## Run it yourself
```bash
pip install -r requirements.txt
streamlit run app.py
```
Without a `DATABASE_URL`, the sidebar asks for a local PostgreSQL password. To deploy:
1. Create a free Neon database and run `00_cloud_setup.sql` once.
2. On [share.streamlit.io](https://share.streamlit.io), pick this repo with `app.py` as the main file and add the secrets
   `DATABASE_URL` and `ADMIN_PASSWORD`.
3. In Power BI: Get data → PostgreSQL → the Neon host, database `neondb`, then load the `cairo_metro.pbi_*` views.

## Data notes
- Station facts and ad scores: my own analysis. Daily ridership per station is an **estimate**.
- Line order and coordinates: [Transport for Cairo Metro-GTFS](https://github.com/transportforcairo/Metro-GTFS)
  (CC BY-NC 4.0) and Wikipedia.
- Prices: Cairo Metro does not publish its rate card, so each format is priced inside **published Egyptian
  outdoor-advertising ranges** ([Entasher](https://entasher.com/Blog/190/Cost-of-billboard-advertising-in-Egypt-billboards-in-egypt-price),
  [Alaanak 2025](https://alaanak.com/billboard-price-in-egypt-guide-digital-vs-traditional-options/)). Formats with no
  published price are marked *estimate*.
- Advertisers, campaigns and bookings are **simulated** with invented company names, so the ML results show the
  method, not real advice. This is a portfolio project, not an official Cairo Metro service.

## Author
**Mariam Madbouly** · Data Science graduate ·
[LinkedIn](https://www.linkedin.com/in/mariam-madbouly-32b03a361)
