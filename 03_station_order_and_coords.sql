-- =====================================================================
-- Station order per line + coordinates
-- Sources: Transport for Cairo Metro-GTFS (CC BY-NC 4.0), Wikipedia.
-- Stations with no published coordinates are left NULL: Gameat El-Dowal, Ring Road, Rod El-Farag Corridor, Tawfikia, Wadi El-Nil
-- =====================================================================
SET search_path TO cairo_metro;

ALTER TABLE line_stations ADD COLUMN IF NOT EXISTS branch VARCHAR(30) DEFAULT 'Trunk';
ALTER TABLE stations ADD COLUMN IF NOT EXISTS coord_source VARCHAR(60);

UPDATE line_stations SET stop_order = NULL;  -- avoid unique clashes while re-numbering
UPDATE line_stations ls SET stop_order = v.ord, branch = v.br
FROM (VALUES
    (1, 'ST001', 2, 'Trunk'),
    (1, 'ST002', 32, 'Trunk'),
    (1, 'ST003', 17, 'Trunk'),
    (1, 'ST033', 22, 'Trunk'),
    (1, 'ST004', 13, 'Trunk'),
    (1, 'ST005', 24, 'Trunk'),
    (1, 'ST006', 6, 'Trunk'),
    (1, 'ST007', 16, 'Trunk'),
    (1, 'ST008', 34, 'Trunk'),
    (1, 'ST009', 31, 'Trunk'),
    (1, 'ST010', 14, 'Trunk'),
    (1, 'ST011', 33, 'Trunk'),
    (1, 'ST012', 23, 'Trunk'),
    (1, 'ST013', 12, 'Trunk'),
    (1, 'ST014', 29, 'Trunk'),
    (1, 'ST015', 5, 'Trunk'),
    (1, 'ST016', 27, 'Trunk'),
    (1, 'ST017', 30, 'Trunk'),
    (1, 'ST018', 1, 'Trunk'),
    (1, 'ST019', 3, 'Trunk'),
    (1, 'ST020', 26, 'Trunk'),
    (1, 'ST021', 8, 'Trunk'),
    (1, 'ST022', 11, 'Trunk'),
    (1, 'ST023', 25, 'Trunk'),
    (1, 'ST024', 15, 'Trunk'),
    (1, 'ST035', 20, 'Trunk'),
    (1, 'ST025', 35, 'Trunk'),
    (1, 'ST026', 21, 'Trunk'),
    (1, 'ST027', 18, 'Trunk'),
    (1, 'ST034', 19, 'Trunk'),
    (1, 'ST028', 28, 'Trunk'),
    (1, 'ST029', 10, 'Trunk'),
    (1, 'ST030', 7, 'Trunk'),
    (1, 'ST031', 9, 'Trunk'),
    (1, 'ST032', 4, 'Trunk'),
    (2, 'ST033', 8, 'Trunk'),
    (2, 'ST052', 9, 'Trunk'),
    (2, 'ST053', 15, 'Trunk'),
    (2, 'ST036', 13, 'Trunk'),
    (2, 'ST037', 14, 'Trunk'),
    (2, 'ST038', 20, 'Trunk'),
    (2, 'ST039', 16, 'Trunk'),
    (2, 'ST040', 17, 'Trunk'),
    (2, 'ST041', 4, 'Trunk'),
    (2, 'ST042', 2, 'Trunk'),
    (2, 'ST043', 7, 'Trunk'),
    (2, 'ST044', 3, 'Trunk'),
    (2, 'ST045', 10, 'Trunk'),
    (2, 'ST046', 18, 'Trunk'),
    (2, 'ST047', 12, 'Trunk'),
    (2, 'ST048', 6, 'Trunk'),
    (2, 'ST034', 11, 'Trunk'),
    (2, 'ST049', 19, 'Trunk'),
    (2, 'ST050', 1, 'Trunk'),
    (2, 'ST051', 5, 'Trunk'),
    (3, 'ST054', 15, 'Trunk'),
    (3, 'ST055', 16, 'Trunk'),
    (3, 'ST056', 1, 'Trunk'),
    (3, 'ST057', 11, 'Trunk'),
    (3, 'ST058', 8, 'Trunk'),
    (3, 'ST052', 19, 'Trunk'),
    (3, 'ST059', 18, 'Trunk'),
    (3, 'ST060', 33, 'Cairo University branch'),
    (3, 'ST053', 34, 'Cairo University branch'),
    (3, 'ST061', 26, 'Rod El-Farag branch'),
    (3, 'ST062', 17, 'Trunk'),
    (3, 'ST063', 2, 'Trunk'),
    (3, 'ST064', 6, 'Trunk'),
    (3, 'ST065', 27, 'Rod El-Farag branch'),
    (3, 'ST066', 14, 'Trunk'),
    (3, 'ST067', 32, 'Cairo University branch'),
    (3, 'ST068', 10, 'Trunk'),
    (3, 'ST069', 9, 'Trunk'),
    (3, 'ST070', 5, 'Trunk'),
    (3, 'ST071', 25, 'Rod El-Farag branch'),
    (3, 'ST072', 23, 'Trunk'),
    (3, 'ST073', 12, 'Trunk'),
    (3, 'ST074', 21, 'Trunk'),
    (3, 'ST075', 7, 'Trunk'),
    (3, 'ST035', 20, 'Trunk'),
    (3, 'ST076', 3, 'Trunk'),
    (3, 'ST077', 4, 'Trunk'),
    (3, 'ST078', 28, 'Rod El-Farag branch'),
    (3, 'ST079', 29, 'Rod El-Farag branch'),
    (3, 'ST080', 22, 'Trunk'),
    (3, 'ST081', 13, 'Trunk'),
    (3, 'ST082', 24, 'Rod El-Farag branch'),
    (3, 'ST083', 30, 'Cairo University branch'),
    (3, 'ST084', 31, 'Cairo University branch')
) v(line_number, code, ord, br)
JOIN lines l ON l.line_number = v.line_number
JOIN stations s ON s.station_code = v.code
WHERE ls.line_id = l.line_id AND ls.station_id = s.station_id;

UPDATE stations s SET latitude = v.lat, longitude = v.lon, coord_source = v.src
FROM (VALUES
    ('ST001', 29.862604, 31.325026, 'Transport for Cairo GTFS'),
    ('ST002', 30.1310007, 31.3191247, 'Transport for Cairo GTFS'),
    ('ST003', 30.02924, 31.235429, 'Transport for Cairo GTFS'),
    ('ST004', 29.9819859, 31.2420434, 'Transport for Cairo GTFS'),
    ('ST005', 30.0771948, 31.2778616, 'Transport for Cairo GTFS'),
    ('ST006', 29.9063622, 31.2995338, 'Transport for Cairo GTFS'),
    ('ST007', 30.0177162, 31.2311751, 'Transport for Cairo GTFS'),
    ('ST008', 30.1521131, 31.3358134, 'Transport for Cairo GTFS'),
    ('ST009', 30.1208952, 31.3137335, 'Transport for Cairo GTFS'),
    ('ST010', 29.995539, 31.2312341, 'Transport for Cairo GTFS'),
    ('ST011', 30.1392217, 31.3246232, 'Transport for Cairo GTFS'),
    ('ST012', 30.0689315, 31.2646759, 'Transport for Cairo GTFS'),
    ('ST013', 29.9697833, 31.2508303, 'Transport for Cairo GTFS'),
    ('ST014', 30.1059577, 31.3103968, 'Transport for Cairo GTFS'),
    ('ST015', 29.897192, 31.30404, 'Transport for Cairo GTFS'),
    ('ST016', 30.0911897, 31.2990081, 'Transport for Cairo GTFS'),
    ('ST017', 30.1132481, 31.3139963, 'Transport for Cairo GTFS'),
    ('ST018', 29.848824, 31.334252, 'Transport for Cairo GTFS'),
    ('ST019', 29.8694521, 31.3200045, 'Transport for Cairo GTFS'),
    ('ST020', 30.087198, 31.2941319, 'Transport for Cairo GTFS'),
    ('ST021', 29.9364531, 31.2814236, 'Transport for Cairo GTFS'),
    ('ST022', 29.960298, 31.2577343, 'Transport for Cairo GTFS'),
    ('ST023', 30.0819807, 31.2875497, 'Transport for Cairo GTFS'),
    ('ST024', 30.0061683, 31.2295818, 'Transport for Cairo GTFS'),
    ('ST025', 30.163551, 31.338335, 'Transport for Cairo GTFS'),
    ('ST026', 30.0570274, 31.2423062, 'Transport for Cairo GTFS'),
    ('ST027', 30.0356671, 31.2378216, 'Transport for Cairo GTFS'),
    ('ST028', 30.09772, 31.3044691, 'Transport for Cairo GTFS'),
    ('ST029', 29.9533078, 31.2629646, 'Transport for Cairo GTFS'),
    ('ST030', 29.9259651, 31.2875497, 'Transport for Cairo GTFS'),
    ('ST031', 29.9467168, 31.2728834, 'Transport for Cairo GTFS'),
    ('ST032', 29.879053, 31.3134384, 'Transport for Cairo GTFS'),
    ('ST033', 30.0616395, 31.246287, 'Transport for Cairo GTFS'),
    ('ST034', 30.043924, 31.23566, 'Transport for Cairo GTFS'),
    ('ST035', 30.0534568, 31.2386477, 'Transport for Cairo GTFS'),
    ('ST036', 30.0384665, 31.2122431, 'Transport for Cairo GTFS'),
    ('ST037', 30.03584, 31.200255, 'Transport for Cairo GTFS'),
    ('ST038', 29.9810333, 31.2123084, 'Transport for Cairo GTFS'),
    ('ST039', 30.0174932, 31.2037468, 'Transport for Cairo GTFS'),
    ('ST040', 30.0106557, 31.2070513, 'Transport for Cairo GTFS'),
    ('ST041', 30.0978453, 31.2449992, 'Transport for Cairo GTFS'),
    ('ST042', 30.1136611, 31.2487543, 'Transport for Cairo GTFS'),
    ('ST043', 30.0708952, 31.2451011, 'Transport for Cairo GTFS'),
    ('ST044', 30.1040735, 31.2455678, 'Transport for Cairo GTFS'),
    ('ST045', 30.0453402, 31.2441516, 'Transport for Cairo GTFS'),
    ('ST046', 30.0059918, 31.2081348, 'Transport for Cairo GTFS'),
    ('ST047', 30.0419317, 31.2249899, 'Transport for Cairo GTFS'),
    ('ST048', 30.0805881, 31.2454015, 'Transport for Cairo GTFS'),
    ('ST049', 29.9955669, 31.2084889, 'Transport for Cairo GTFS'),
    ('ST050', 30.1225145, 31.244688, 'Transport for Cairo GTFS'),
    ('ST051', 30.0879569, 31.2454927, 'Transport for Cairo GTFS'),
    ('ST052', 30.0523517, 31.2467963, 'Transport for Cairo GTFS'),
    ('ST053', 30.026151, 31.2008715, 'Transport for Cairo GTFS'),
    ('ST054', 30.0697625, 31.2807798, 'Transport for Cairo GTFS'),
    ('ST055', 30.064673, 31.274853, 'Transport for Cairo GTFS'),
    ('ST056', 30.146944, 31.421389, 'Wikipedia (via egymetro dataset)'),
    ('ST057', 30.09183, 31.3263449999999, 'Transport for Cairo GTFS'),
    ('ST058', 30.118056, 31.339722, 'Wikipedia (via egymetro dataset)'),
    ('ST059', 30.0539026, 31.2560177, 'Transport for Cairo GTFS'),
    ('ST060', 30.036111, 31.196389, 'Wikipedia (via egymetro dataset)'),
    ('ST061', 30.082, 31.2105, 'Wikipedia station page'),
    ('ST062', 30.061716, 31.26696, 'Transport for Cairo GTFS'),
    ('ST063', 30.143889, 31.404722, 'Wikipedia (via egymetro dataset)'),
    ('ST064', 30.128333, 31.36, 'Wikipedia (via egymetro dataset)'),
    ('ST065', 30.0932, 31.209, 'Wikipedia station page'),
    ('ST066', 30.072963, 31.30063, 'Transport for Cairo GTFS'),
    ('ST068', 30.101111, 31.332778, 'Wikipedia (via egymetro dataset)'),
    ('ST069', 30.108056, 31.338056, 'Wikipedia (via egymetro dataset)'),
    ('ST070', 30.131111, 31.372778, 'Wikipedia (via egymetro dataset)'),
    ('ST071', 30.077222, 31.217778, 'Wikipedia (via egymetro dataset)'),
    ('ST072', 30.066667, 31.213056, 'Wikipedia (via egymetro dataset)'),
    ('ST073', 30.084163, 31.329012, 'Transport for Cairo GTFS'),
    ('ST074', 30.055556, 31.232222, 'Wikipedia (via egymetro dataset)'),
    ('ST075', 30.122222, 31.343889, 'Wikipedia (via egymetro dataset)'),
    ('ST076', 30.140556, 31.394167, 'Wikipedia (via egymetro dataset)'),
    ('ST077', 30.134722, 31.383889, 'Wikipedia (via egymetro dataset)'),
    ('ST080', 30.0625, 31.2225, 'Wikipedia (via egymetro dataset)'),
    ('ST081', 30.072742, 31.3173380000001, 'Transport for Cairo GTFS'),
    ('ST082', 30.0698, 31.2053, 'Wikipedia station page')
) v(code, lat, lon, src) WHERE s.station_code = v.code;

-- Re-create the analysis view with coordinates
DROP VIEW IF EXISTS station_ad_profile;
CREATE VIEW station_ad_profile AS
WITH latest_ridership AS (
    SELECT DISTINCT ON (station_id) station_id, avg_daily_riders, peak_hour_riders
    FROM station_ridership ORDER BY station_id, period_start DESC
),
line_info AS (
    SELECT ls.station_id, COUNT(*) AS lines_count,
           STRING_AGG('L' || l.line_number, '/' ORDER BY l.line_number) AS lines
    FROM line_stations ls JOIN lines l USING (line_id) GROUP BY ls.station_id
),
spaces AS (
    SELECT station_id, COUNT(*) FILTER (WHERE is_active) AS active_ad_spaces,
           AVG(monthly_price_egp) AS avg_monthly_price
    FROM ad_spaces GROUP BY station_id
)
SELECT s.station_id, s.station_code, s.name_en, s.name_ar, s.governorate, s.district,
       s.area_type, s.station_type, s.opened_year, s.latitude, s.longitude,
       li.lines, COALESCE(li.lines_count, 0) AS lines_count,
       (COALESCE(li.lines_count, 0) > 1) AS is_interchange, s.is_terminus, s.transport_hub,
       s.purchasing_power, s.near_university, s.near_market, s.near_govt_hospital, s.tourist_heritage,
       r.avg_daily_riders, r.peak_hour_riders,
       sc.rank, sc.tier, sc.ad_score, sc.target_audience, sc.best_advertisers, sc.recommended_formats,
       COALESCE(sp.active_ad_spaces, 0) AS active_ad_spaces, sp.avg_monthly_price,
       ROUND(sp.avg_monthly_price / NULLIF(r.avg_daily_riders * 30, 0) * 1000, 2) AS cost_per_1000_riders_egp
FROM stations s
LEFT JOIN line_info        li USING (station_id)
LEFT JOIN latest_ridership r  USING (station_id)
LEFT JOIN station_scores   sc USING (station_id)
LEFT JOIN spaces           sp USING (station_id);

-- Check
SELECT l.line_number, COUNT(*) AS stations, COUNT(ls.stop_order) AS with_order
FROM line_stations ls JOIN lines l USING (line_id) GROUP BY 1 ORDER BY 1;
