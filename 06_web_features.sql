-- =====================================================================
-- Web app features: booking status, timestamps, Power BI views
-- Run AFTER 01-04. Safe to re-run.
-- =====================================================================
SET search_path TO cairo_metro;

-- 1) Booking status: bookings made from the website start as 'pending' until approved in the admin page
ALTER TABLE bookings  ADD COLUMN IF NOT EXISTS status     VARCHAR(12) NOT NULL DEFAULT 'confirmed';
ALTER TABLE bookings  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE bookings  ADD COLUMN IF NOT EXISTS source     VARCHAR(12) NOT NULL DEFAULT 'seed';
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_status_check;
ALTER TABLE bookings ADD CONSTRAINT bookings_status_check CHECK (status IN ('confirmed', 'pending', 'cancelled'));

-- A cancelled booking frees the space again
ALTER TABLE bookings DROP CONSTRAINT IF EXISTS no_overlapping_bookings;
ALTER TABLE bookings ADD CONSTRAINT no_overlapping_bookings
    EXCLUDE USING gist (
        ad_space_id WITH =,
        daterange(start_date, end_date, '[]') WITH &&
    ) WHERE (status <> 'cancelled');

CREATE INDEX IF NOT EXISTS idx_bookings_dates ON bookings (start_date, end_date);

-- 2) Flat views for Power BI (one refresh pulls everything already joined)
CREATE OR REPLACE VIEW pbi_bookings AS
SELECT b.booking_id, b.status, b.source, b.created_at,
       b.start_date, b.end_date, (b.end_date - b.start_date + 1) AS days,
       DATE_TRUNC('month', b.start_date)::date AS booking_month,
       b.price_egp,
       a.ad_space_id, f.format_name, f.name_ar AS format_ar, f.is_digital, a.zone, a.monthly_price_egp,
       s.station_id, s.station_code, s.name_en AS station_en, s.name_ar AS station_ar, s.latitude, s.longitude,
       sc.tier, sc.ad_score,
       c.campaign_id, c.campaign_name, c.target_audience,
       ad.advertiser_id, ad.company_name, ad.industry
FROM bookings b
JOIN ad_spaces a       USING (ad_space_id)
JOIN ad_formats f      ON f.format_id = a.format_id
JOIN stations s        ON s.station_id = a.station_id
LEFT JOIN station_scores sc ON sc.station_id = s.station_id
JOIN campaigns c       ON c.campaign_id = b.campaign_id
JOIN advertisers ad    ON ad.advertiser_id = c.advertiser_id;

CREATE OR REPLACE VIEW pbi_station_lines AS
SELECT s.station_id, s.name_en AS station_en, s.name_ar AS station_ar,
       'L' || l.line_number AS line, l.line_name, ls.stop_order, ls.branch
FROM line_stations ls
JOIN lines l    USING (line_id)
JOIN stations s USING (station_id);

CREATE OR REPLACE VIEW pbi_occupancy_today AS
SELECT a.ad_space_id, a.station_id, f.name_ar AS format_ar, a.monthly_price_egp, a.is_active,
       EXISTS (SELECT 1 FROM bookings b
               WHERE b.ad_space_id = a.ad_space_id AND b.status <> 'cancelled'
                 AND CURRENT_DATE BETWEEN b.start_date AND b.end_date) AS booked_today
FROM ad_spaces a JOIN ad_formats f USING (format_id);

SELECT 'ok' AS web_features_installed,
       (SELECT COUNT(*) FROM pbi_bookings) AS bookings_in_view;
