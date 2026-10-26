-- =====================================================================
-- Cairo Metro Advertising - SQL Business Analysis
-- Run each query on its own in pgAdmin (select it, then F5).
-- Station facts: real/estimated (see Methodology). Ad sales data: SIMULATED.
-- =====================================================================
SET search_path TO cairo_metro;


-- =====================================================================
-- PART A - NETWORK & AUDIENCE
-- =====================================================================

-- Q1. Network overview per line: stations, estimated riders, avg ad score
SELECT l.line_number,
       l.line_name,
       COUNT(*)                          AS stations,
       SUM(r.avg_daily_riders)           AS est_daily_riders,
       ROUND(AVG(sc.ad_score), 1)        AS avg_ad_score,
       COUNT(*) FILTER (WHERE sc.tier = 'Premium') AS premium_stations
FROM line_stations ls
JOIN lines l              USING (line_id)
JOIN station_scores sc    USING (station_id)
JOIN station_ridership r  USING (station_id)
GROUP BY l.line_number, l.line_name
ORDER BY l.line_number;


-- Q2. Top 3 stations on EACH line by ad score  (window function: ROW_NUMBER)
WITH ranked AS (
    SELECT l.line_number, s.name_en, sc.ad_score, sc.tier,
           ROW_NUMBER() OVER (PARTITION BY l.line_number ORDER BY sc.ad_score DESC) AS rn
    FROM line_stations ls
    JOIN lines l           USING (line_id)
    JOIN stations s        USING (station_id)
    JOIN station_scores sc USING (station_id)
)
SELECT line_number, rn AS rank_on_line, name_en, ad_score, tier
FROM ranked
WHERE rn <= 3
ORDER BY line_number, rn;


-- Q3. Footfall concentration: what share of riders do the top 10 stations carry?
--     (window functions: running total + share)
WITH f AS (
    SELECT s.name_en, r.avg_daily_riders,
           SUM(r.avg_daily_riders) OVER (ORDER BY r.avg_daily_riders DESC
                                         ROWS UNBOUNDED PRECEDING) AS running_riders,
           SUM(r.avg_daily_riders) OVER ()                         AS total_riders,
           ROW_NUMBER() OVER (ORDER BY r.avg_daily_riders DESC)    AS rn
    FROM stations s JOIN station_ridership r USING (station_id)
)
SELECT rn, name_en, avg_daily_riders,
       ROUND(100.0 * running_riders / total_riders, 1) AS cumulative_share_pct
FROM f
ORDER BY rn
LIMIT 10;


-- Q4. Best stations per target audience (which stations reach students, upper-middle class, ...)
WITH aud AS (
    SELECT s.name_en, sc.ad_score, r.avg_daily_riders,
           TRIM(a) AS audience
    FROM station_scores sc
    JOIN stations s USING (station_id)
    JOIN station_ridership r USING (station_id)
    CROSS JOIN LATERAL UNNEST(STRING_TO_ARRAY(sc.target_audience, ',')) AS a
),
ranked AS (
    SELECT *, DENSE_RANK() OVER (PARTITION BY audience ORDER BY ad_score DESC, avg_daily_riders DESC) AS rk
    FROM aud
)
SELECT audience, rk, name_en, ad_score, avg_daily_riders
FROM ranked
WHERE rk <= 3
ORDER BY audience, rk;


-- Q5. Area type vs. ad value: is CBD really worth the premium?
SELECT s.area_type,
       COUNT(*)                                   AS stations,
       ROUND(AVG(sc.ad_score), 1)                 AS avg_score,
       SUM(r.avg_daily_riders)                    AS total_riders,
       ROUND(AVG(a.monthly_price_egp))            AS avg_space_price_egp
FROM stations s
JOIN station_scores sc   USING (station_id)
JOIN station_ridership r USING (station_id)
LEFT JOIN ad_spaces a    USING (station_id)
GROUP BY s.area_type
ORDER BY avg_score DESC;


-- Q6. Interchange vs. non-interchange stations
SELECT is_interchange,
       COUNT(*)                         AS stations,
       ROUND(AVG(avg_daily_riders))     AS avg_riders,
       ROUND(AVG(ad_score), 1)          AS avg_score
FROM station_ad_profile
GROUP BY is_interchange;


-- =====================================================================
-- PART B - REVENUE & SALES  (simulated ad data)
-- =====================================================================

-- Q7. Monthly revenue with month-over-month growth  (LAG)
WITH monthly AS (
    SELECT DATE_TRUNC('month', start_date)::date AS month,
           SUM(price_egp)                         AS revenue
    FROM bookings
    GROUP BY 1
)
SELECT month, revenue,
       LAG(revenue) OVER (ORDER BY month)                                   AS prev_month,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
             / NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 1)           AS mom_growth_pct,
       ROUND(AVG(revenue) OVER (ORDER BY month ROWS 2 PRECEDING))           AS moving_avg_3m
FROM monthly
ORDER BY month;


-- Q8. Year-over-year revenue by line
SELECT l.line_number,
       SUM(b.price_egp) FILTER (WHERE EXTRACT(YEAR FROM b.start_date) = 2025) AS rev_2025,
       SUM(b.price_egp) FILTER (WHERE EXTRACT(YEAR FROM b.start_date) = 2026) AS rev_2026,
       ROUND(100.0 * (SUM(b.price_egp) FILTER (WHERE EXTRACT(YEAR FROM b.start_date) = 2026)
                    - SUM(b.price_egp) FILTER (WHERE EXTRACT(YEAR FROM b.start_date) = 2025))
             / NULLIF(SUM(b.price_egp) FILTER (WHERE EXTRACT(YEAR FROM b.start_date) = 2025), 0), 1) AS yoy_pct
FROM bookings b
JOIN ad_spaces a      USING (ad_space_id)
JOIN line_stations ls ON ls.station_id = a.station_id
JOIN lines l          USING (line_id)
GROUP BY l.line_number
ORDER BY l.line_number;
-- Note: revenue at interchange stations counts on every line they serve.


-- Q9. Top 10 stations by revenue and their share of total  (window: share of total)
SELECT s.name_en, sc.tier,
       SUM(b.price_egp)                                             AS revenue,
       ROUND(100.0 * SUM(b.price_egp) / SUM(SUM(b.price_egp)) OVER (), 1) AS share_pct
FROM bookings b
JOIN ad_spaces a       USING (ad_space_id)
JOIN stations s        ON s.station_id = a.station_id
JOIN station_scores sc ON sc.station_id = s.station_id
GROUP BY s.name_en, sc.tier
ORDER BY revenue DESC
LIMIT 10;


-- Q10. Revenue by ad format: which formats earn the most per space?
SELECT f.format_name, f.is_digital,
       COUNT(DISTINCT a.ad_space_id)                         AS spaces,
       COALESCE(SUM(b.price_egp), 0)                         AS revenue,
       ROUND(COALESCE(SUM(b.price_egp), 0) / COUNT(DISTINCT a.ad_space_id)) AS revenue_per_space
FROM ad_formats f
JOIN ad_spaces a  USING (format_id)
LEFT JOIN bookings b USING (ad_space_id)
GROUP BY f.format_name, f.is_digital
ORDER BY revenue_per_space DESC;


-- Q11. Occupancy rate per tier in 2025 (booked days / available days)
WITH days AS (
    SELECT a.ad_space_id, sc.tier,
           COALESCE(SUM(LEAST(b.end_date, DATE '2025-12-31')
                      - GREATEST(b.start_date, DATE '2025-01-01') + 1)
                    FILTER (WHERE b.start_date <= DATE '2025-12-31' AND b.end_date >= DATE '2025-01-01'), 0) AS booked_days
    FROM ad_spaces a
    JOIN station_scores sc USING (station_id)
    LEFT JOIN bookings b   USING (ad_space_id)
    WHERE a.is_active
    GROUP BY a.ad_space_id, sc.tier
)
SELECT tier,
       COUNT(*)                                   AS active_spaces,
       ROUND(100.0 * SUM(booked_days) / (COUNT(*) * 365), 1) AS occupancy_pct
FROM days
GROUP BY tier
ORDER BY occupancy_pct DESC;


-- Q12. Spaces that were NEVER booked (sales opportunities)
SELECT s.name_en, sc.tier, f.format_name, a.zone, a.monthly_price_egp
FROM ad_spaces a
JOIN stations s        ON s.station_id = a.station_id
JOIN station_scores sc ON sc.station_id = a.station_id
JOIN ad_formats f      USING (format_id)
WHERE a.is_active
  AND NOT EXISTS (SELECT 1 FROM bookings b WHERE b.ad_space_id = a.ad_space_id)
ORDER BY sc.ad_score DESC, a.monthly_price_egp DESC;


-- =====================================================================
-- PART C - ADVERTISERS & CAMPAIGNS
-- =====================================================================

-- Q13. Advertiser ranking by spend, with industry rank  (RANK + PARTITION)
SELECT ad.company_name, ad.industry,
       COUNT(DISTINCT c.campaign_id)          AS campaigns,
       SUM(b.price_egp)                       AS total_spend,
       RANK() OVER (ORDER BY SUM(b.price_egp) DESC)                         AS overall_rank,
       RANK() OVER (PARTITION BY ad.industry ORDER BY SUM(b.price_egp) DESC) AS rank_in_industry
FROM advertisers ad
JOIN campaigns c USING (advertiser_id)
JOIN bookings b  USING (campaign_id)
GROUP BY ad.company_name, ad.industry
ORDER BY total_spend DESC;


-- Q14. Budget utilisation per campaign: did campaigns spend their budget?
SELECT c.campaign_name, c.target_audience, c.budget_egp,
       COALESCE(SUM(b.price_egp), 0)                               AS spent,
       ROUND(100.0 * COALESCE(SUM(b.price_egp), 0) / c.budget_egp, 1) AS utilisation_pct,
       CASE WHEN COALESCE(SUM(b.price_egp), 0) < 0.5 * c.budget_egp THEN 'Under-delivered'
            WHEN COALESCE(SUM(b.price_egp), 0) < 0.85 * c.budget_egp THEN 'Partial'
            ELSE 'Fully used' END                                   AS status
FROM campaigns c
LEFT JOIN bookings b USING (campaign_id)
GROUP BY c.campaign_id, c.campaign_name, c.target_audience, c.budget_egp
ORDER BY utilisation_pct;


-- Q15. Cost per 1,000 riders reached (CPM) by audience - which audience is cheapest to reach?
WITH reach AS (
    SELECT c.target_audience,
           SUM(b.price_egp)                                           AS spend,
           SUM(r.avg_daily_riders::numeric * (b.end_date - b.start_date + 1)) AS rider_impressions
    FROM bookings b
    JOIN campaigns c        USING (campaign_id)
    JOIN ad_spaces a        USING (ad_space_id)
    JOIN station_ridership r ON r.station_id = a.station_id
    GROUP BY c.target_audience
)
SELECT target_audience, spend,
       ROUND(spend / NULLIF(rider_impressions, 0) * 1000, 2) AS cpm_egp
FROM reach
ORDER BY cpm_egp;


-- Q16. Pricing check: stations priced below what their ad score suggests  (NTILE)
WITH s AS (
    SELECT st.name_en, sc.ad_score, AVG(a.monthly_price_egp) AS avg_price,
           NTILE(4) OVER (ORDER BY sc.ad_score)        AS score_quartile,
           NTILE(4) OVER (ORDER BY AVG(a.monthly_price_egp)) AS price_quartile
    FROM ad_spaces a
    JOIN stations st       ON st.station_id = a.station_id
    JOIN station_scores sc ON sc.station_id = a.station_id
    GROUP BY st.name_en, sc.ad_score
)
SELECT name_en, ad_score, ROUND(avg_price) AS avg_price, score_quartile, price_quartile,
       CASE WHEN score_quartile > price_quartile THEN 'Underpriced - raise price'
            WHEN score_quartile < price_quartile THEN 'Overpriced - review'
            ELSE 'Fair' END AS pricing_signal
FROM s
WHERE score_quartile <> price_quartile
ORDER BY score_quartile - price_quartile DESC, ad_score DESC;


-- Q17. Seasonality: average monthly revenue by calendar month (both years)
SELECT EXTRACT(MONTH FROM start_date)::int AS month_no,
       TO_CHAR(MIN(start_date), 'Mon')    AS month,
       ROUND(SUM(price_egp) / COUNT(DISTINCT EXTRACT(YEAR FROM start_date))) AS avg_revenue
FROM bookings
GROUP BY 1
ORDER BY 1;
