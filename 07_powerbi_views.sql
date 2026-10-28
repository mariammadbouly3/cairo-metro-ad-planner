-- =====================================================================
-- Power BI views. pbi_stations has EXACTLY the columns of the old
-- metro_stations_for_powerbi.csv, so the existing dashboard (measures and
-- visuals) keeps working after its source is switched to the database.
-- Extra live columns (ad spaces, revenue, occupancy) are added at the end.
-- Safe to re-run.
-- =====================================================================
SET search_path TO cairo_metro;

DROP VIEW IF EXISTS pbi_stations;
CREATE VIEW pbi_stations AS
WITH li AS (
    SELECT ls.station_id, STRING_AGG('L' || l.line_number, '/' ORDER BY l.line_number) AS lines,
           COUNT(*) AS n_lines
    FROM line_stations ls JOIN lines l USING (line_id) GROUP BY ls.station_id
),
rid AS (
    SELECT DISTINCT ON (station_id) station_id, avg_daily_riders
    FROM station_ridership ORDER BY station_id, period_start DESC
),
sp AS (
    SELECT station_id, COUNT(*) FILTER (WHERE is_active) AS active_ad_spaces,
           ROUND(AVG(monthly_price_egp)) AS avg_monthly_price_egp
    FROM ad_spaces GROUP BY station_id
),
rev AS (
    SELECT a.station_id,
           SUM(b.price_egp) FILTER (WHERE b.status <> 'cancelled')                                        AS revenue_egp,
           SUM(b.price_egp) FILTER (WHERE b.status <> 'cancelled'
                                    AND EXTRACT(YEAR FROM b.start_date) = EXTRACT(YEAR FROM CURRENT_DATE)) AS revenue_this_year_egp,
           COUNT(DISTINCT b.ad_space_id) FILTER (WHERE b.status <> 'cancelled'
                                    AND CURRENT_DATE BETWEEN b.start_date AND b.end_date)                 AS spaces_booked_today,
           COUNT(*) FILTER (WHERE b.status = 'pending')                                                   AS pending_bookings
    FROM bookings b JOIN ad_spaces a USING (ad_space_id) GROUP BY a.station_id
)
SELECT sc.rank,
       sc.tier,
       sc.ad_score,
       s.station_code                                            AS station_id,
       s.name_en                                                 AS station_en,
       s.name_ar                                                 AS station_ar,
       li.lines,
       CASE WHEN li.n_lines > 1 THEN 'Interchange' ELSE li.lines END AS line_group,
       s.area_type,
       s.district,
       s.governorate,
       s.purchasing_power,
       rid.avg_daily_riders                                      AS est_daily_footfall,
       CASE WHEN li.n_lines > 1 OR s.transport_hub OR s.is_terminus THEN 'Mass reach / commuters'
            WHEN s.purchasing_power = 3 THEN 'Affluent audience'
            WHEN s.near_university THEN 'Youth / students'
            ELSE 'Local / neighbourhood' END                     AS package,
       sc.best_advertisers,
       sc.c_reach, sc.c_purchasing, sc.c_dwell, sc.c_poi, sc.c_environment,
       -- live columns from the website
       s.latitude, s.longitude,
       COALESCE(sp.active_ad_spaces, 0)                          AS active_ad_spaces,
       sp.avg_monthly_price_egp,
       COALESCE(rev.revenue_egp, 0)                              AS revenue_egp,
       COALESCE(rev.revenue_this_year_egp, 0)                    AS revenue_this_year_egp,
       COALESCE(rev.spaces_booked_today, 0)                      AS spaces_booked_today,
       COALESCE(rev.pending_bookings, 0)                         AS pending_bookings,
       -- columns the dashboard's Power Query step expects
       CASE WHEN li.n_lines > 1 THEN 1 ELSE 0 END                AS is_interchange,
       CASE WHEN s.is_terminus THEN 1 ELSE 0 END                 AS is_terminus,
       CASE s.station_type WHEN 'underground' THEN 'Underground' WHEN 'elevated' THEN 'Elevated'
                           ELSE 'At-grade' END                   AS structure,
       s.opened_year::int                                        AS opened
FROM stations s
JOIN station_scores sc USING (station_id)
LEFT JOIN li  USING (station_id)
LEFT JOIN rid USING (station_id)
LEFT JOIN sp  USING (station_id)
LEFT JOIN rev USING (station_id)
ORDER BY sc.rank;

-- same shape as the old station_lines.csv
CREATE OR REPLACE VIEW pbi_station_line_groups AS
SELECT 'L' || l.line_number AS line_group, s.station_code AS station_id
FROM line_stations ls JOIN lines l USING (line_id) JOIN stations s USING (station_id);

SELECT COUNT(*) AS stations_in_view, SUM(revenue_egp) AS total_revenue FROM pbi_stations;
