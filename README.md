# 🚇 مخطط إعلانات مترو القاهرة · Cairo Metro Ad Planner

A bilingual (Arabic UI) web app on a PostgreSQL database of the 84 stations on Cairo Metro Lines 1–3.
Advertisers plan a campaign, get the best **available** ad spaces for their audience and budget, and book it.
Admins review bookings and edit prices. Every change shows up straight away on every page and in Power BI.

**Pages**
| Page | What it does |
|---|---|
| لوحة المؤشرات (Dashboard) | Revenue, occupancy today, live campaigns, revenue by month, line, format, station and advertiser. Refreshes every minute. |
| خطّط واحجز (Plan & book) | Industry → audience, budget, dates, lines, formats → recommended plan on a map, plus a one-click booking (saved as *pending*). |
| شبكة المترو (Network) | All three lines with both Line 3 branches. Stations are sized by ad score. |
| تفاصيل محطة (Station) | Profile, audience, best advertisers, and live availability of every ad space. |
| الأسعار (Prices) | Price range per format, and the published source behind it. |
| الإدارة (Admin) | Password protected: approve/cancel bookings, add campaigns and bookings, edit prices, switch spaces off. |

## Stack
PostgreSQL (Neon in the cloud) · Python · pandas · SQLAlchemy · Streamlit · Plotly · Power BI

## Run on your laptop
```bash
pip install -r requirements.txt
streamlit run app.py
```
Or double-click `run_app.bat` on Windows. Without a `DATABASE_URL`, the sidebar asks for the local PostgreSQL password.

## Deploy (free)
1. **Database**: create a Neon project, then run `sql/00_cloud_setup.sql` once (in pgAdmin or the Neon SQL editor).
2. **App**: on [share.streamlit.io](https://share.streamlit.io) choose this repo, set `app.py` as the main file, and add these secrets:
   ```toml
   DATABASE_URL = "postgresql://USER:PASSWORD@HOST/neondb?sslmode=require"
   ADMIN_PASSWORD = "choose-a-password"
   ```
3. **Power BI**: Get data → PostgreSQL → server = Neon host, database = `neondb`. Load the `cairo_metro.pbi_*` views
   and `station_ad_profile`, then use **Refresh** to pull the latest bookings.

## Database
`sql/01`–`06` build the schema step by step, and `sql/05_sql_analysis.sql` has 17 business questions
(CTEs, window functions: ROW_NUMBER, LAG, RANK, NTILE, running totals).
Bookings use an exclusion constraint, so the same ad space can never be double-booked. A cancelled booking frees the space.

## Data notes
- Station facts and ad scores: own analysis (`metro_ads_analysis.xlsx`). Daily footfall is an **estimate**.
- Line order and coordinates: [Transport for Cairo Metro-GTFS](https://github.com/transportforcairo/Metro-GTFS) (CC BY-NC 4.0) and Wikipedia.
- Prices: Cairo Metro does not publish its rate card. Each format is priced inside **published Egyptian outdoor-advertising
  ranges** ([Entasher](https://entasher.com/Blog/190/Cost-of-billboard-advertising-in-Egypt-billboards-in-egypt-price),
  [Alaanak 2025](https://alaanak.com/billboard-price-in-egypt-guide-digital-vs-traditional-options/)). Formats with no published
  price are marked *estimate*.
- The original advertisers, campaigns and bookings are **simulated**, and the company names are invented.
