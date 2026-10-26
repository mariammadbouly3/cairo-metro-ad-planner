-- =====================================================================
-- Cairo Metro Advertising Database  (PostgreSQL)
-- Goal: analyze metro stations and recommend the best ad locations
-- =====================================================================

DROP SCHEMA IF EXISTS cairo_metro CASCADE;
CREATE SCHEMA cairo_metro;
SET search_path TO cairo_metro;

-- ---------------------------------------------------------------------
-- 1) Metro network
-- ---------------------------------------------------------------------
CREATE TABLE lines (
    line_id        SERIAL PRIMARY KEY,
    line_number    SMALLINT    NOT NULL UNIQUE,
    line_name      VARCHAR(100) NOT NULL,          -- e.g. 'Helwan - New El Marg'
    color          VARCHAR(20),
    opened_year    SMALLINT,
    length_km      NUMERIC(5,1)
);

CREATE TABLE stations (
    station_id     SERIAL PRIMARY KEY,
    name_en        VARCHAR(100) NOT NULL UNIQUE,
    name_ar        VARCHAR(100),
    governorate    VARCHAR(50),                    -- Cairo / Giza / Qalyubia
    district       VARCHAR(100),
    latitude       NUMERIC(9,6),
    longitude      NUMERIC(9,6),
    station_type   VARCHAR(20) CHECK (station_type IN ('underground','surface','elevated')),
    opened_year    SMALLINT
);

-- Many-to-many: one station can sit on more than one line (interchanges)
CREATE TABLE line_stations (
    line_id        INT NOT NULL REFERENCES lines(line_id)    ON DELETE CASCADE,
    station_id     INT NOT NULL REFERENCES stations(station_id) ON DELETE CASCADE,
    stop_order     SMALLINT NOT NULL,              -- position along the line
    PRIMARY KEY (line_id, station_id),
    UNIQUE (line_id, stop_order)
);

-- Interchange stations are derived, not stored twice
CREATE VIEW interchange_stations AS
SELECT s.station_id, s.name_en, COUNT(*) AS lines_count
FROM stations s
JOIN line_stations ls USING (station_id)
GROUP BY s.station_id, s.name_en
HAVING COUNT(*) > 1;

-- ---------------------------------------------------------------------
-- 2) Traffic & surroundings (what makes a station valuable for ads)
-- ---------------------------------------------------------------------
CREATE TABLE station_ridership (
    ridership_id     SERIAL PRIMARY KEY,
    station_id       INT  NOT NULL REFERENCES stations(station_id) ON DELETE CASCADE,
    period_start     DATE NOT NULL,
    period_end       DATE NOT NULL,
    avg_daily_riders INT  CHECK (avg_daily_riders >= 0),
    peak_hour_riders INT  CHECK (peak_hour_riders >= 0),
    source           VARCHAR(200),                 -- where the number came from
    CHECK (period_end >= period_start),
    UNIQUE (station_id, period_start)
);

CREATE TABLE poi_categories (
    category_id    SERIAL PRIMARY KEY,
    category_name  VARCHAR(50) NOT NULL UNIQUE     -- university, mall, hospital, government, business, tourist...
);

CREATE TABLE nearby_places (
    place_id       SERIAL PRIMARY KEY,
    station_id     INT NOT NULL REFERENCES stations(station_id) ON DELETE CASCADE,
    category_id    INT NOT NULL REFERENCES poi_categories(category_id),
    place_name     VARCHAR(150) NOT NULL,
    distance_m     INT CHECK (distance_m >= 0)
);

-- ---------------------------------------------------------------------
-- 3) Advertising inventory
-- ---------------------------------------------------------------------
CREATE TABLE ad_formats (
    format_id      SERIAL PRIMARY KEY,
    format_name    VARCHAR(50) NOT NULL UNIQUE,    -- billboard, digital screen, platform wall, stairs wrap, ticket gate...
    is_digital     BOOLEAN DEFAULT FALSE
);

CREATE TABLE ad_spaces (
    ad_space_id    SERIAL PRIMARY KEY,
    station_id     INT NOT NULL REFERENCES stations(station_id) ON DELETE CASCADE,
    format_id      INT NOT NULL REFERENCES ad_formats(format_id),
    zone           VARCHAR(20) CHECK (zone IN ('entrance','concourse','platform','stairs','exit')),
    width_m        NUMERIC(5,2),
    height_m       NUMERIC(5,2),
    monthly_price_egp NUMERIC(12,2) CHECK (monthly_price_egp >= 0),
    is_active      BOOLEAN DEFAULT TRUE
);

-- ---------------------------------------------------------------------
-- 4) Advertisers, campaigns, bookings
-- ---------------------------------------------------------------------
CREATE TABLE advertisers (
    advertiser_id  SERIAL PRIMARY KEY,
    company_name   VARCHAR(150) NOT NULL,
    industry       VARCHAR(50)                     -- telecom, FMCG, banking, education...
);

CREATE TABLE campaigns (
    campaign_id    SERIAL PRIMARY KEY,
    advertiser_id  INT NOT NULL REFERENCES advertisers(advertiser_id) ON DELETE CASCADE,
    campaign_name  VARCHAR(150) NOT NULL,
    target_audience VARCHAR(100),                  -- students, commuters, families...
    start_date     DATE NOT NULL,
    end_date       DATE NOT NULL,
    budget_egp     NUMERIC(14,2),
    CHECK (end_date >= start_date)
);

CREATE TABLE bookings (
    booking_id     SERIAL PRIMARY KEY,
    campaign_id    INT NOT NULL REFERENCES campaigns(campaign_id) ON DELETE CASCADE,
    ad_space_id    INT NOT NULL REFERENCES ad_spaces(ad_space_id),
    start_date     DATE NOT NULL,
    end_date       DATE NOT NULL,
    price_egp      NUMERIC(12,2),
    CHECK (end_date >= start_date)
);

-- Prevent double-booking the same ad space for overlapping dates
CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER TABLE bookings ADD CONSTRAINT no_overlapping_bookings
    EXCLUDE USING gist (
        ad_space_id WITH =,
        daterange(start_date, end_date, '[]') WITH &&
    );

-- ---------------------------------------------------------------------
-- 5) Indexes for analysis queries
-- ---------------------------------------------------------------------
CREATE INDEX idx_line_stations_station ON line_stations(station_id);
CREATE INDEX idx_ridership_station     ON station_ridership(station_id);
CREATE INDEX idx_places_station        ON nearby_places(station_id);
CREATE INDEX idx_adspaces_station      ON ad_spaces(station_id);
CREATE INDEX idx_bookings_campaign     ON bookings(campaign_id);

-- ---------------------------------------------------------------------
-- 6) Analysis view: one row per station with its "ad value" signals
--    (connect Power BI to this view)
-- ---------------------------------------------------------------------
CREATE VIEW station_ad_profile AS
WITH latest_ridership AS (
    SELECT DISTINCT ON (station_id) station_id, avg_daily_riders, peak_hour_riders
    FROM station_ridership
    ORDER BY station_id, period_start DESC
),
line_counts AS (
    SELECT station_id, COUNT(*) AS lines_count
    FROM line_stations GROUP BY station_id
),
places AS (
    SELECT station_id,
           COUNT(*)                                             AS nearby_places,
           COUNT(*) FILTER (WHERE c.category_name = 'university') AS universities,
           COUNT(*) FILTER (WHERE c.category_name = 'mall')       AS malls
    FROM nearby_places np JOIN poi_categories c USING (category_id)
    GROUP BY station_id
),
spaces AS (
    SELECT station_id,
           COUNT(*) FILTER (WHERE is_active)   AS active_ad_spaces,
           AVG(monthly_price_egp)              AS avg_monthly_price
    FROM ad_spaces GROUP BY station_id
)
SELECT s.station_id, s.name_en, s.name_ar, s.district,
       COALESCE(lc.lines_count, 0)      AS lines_count,
       (COALESCE(lc.lines_count, 0) > 1) AS is_interchange,
       r.avg_daily_riders, r.peak_hour_riders,
       COALESCE(p.nearby_places, 0)     AS nearby_places,
       COALESCE(p.universities, 0)      AS universities,
       COALESCE(p.malls, 0)             AS malls,
       COALESCE(sp.active_ad_spaces, 0) AS active_ad_spaces,
       sp.avg_monthly_price,
       ROUND(sp.avg_monthly_price / NULLIF(r.avg_daily_riders * 30, 0) * 1000, 2)
                                        AS cost_per_1000_riders_egp   -- CPM-style metric
FROM stations s
LEFT JOIN line_counts      lc USING (station_id)
LEFT JOIN latest_ridership r  USING (station_id)
LEFT JOIN places           p  USING (station_id)
LEFT JOIN spaces           sp USING (station_id);

-- ---------------------------------------------------------------------
-- 7) Starter lookup data
-- ---------------------------------------------------------------------
INSERT INTO lines (line_number, line_name) VALUES
    (1, 'Helwan - New El Marg'),
    (2, 'Shubra El Kheima - El Mounib'),
    (3, 'Adly Mansour - Rod El Farag Corridor');

INSERT INTO poi_categories (category_name) VALUES
    ('university'), ('school'), ('mall'), ('market'), ('hospital'),
    ('government'), ('business'), ('tourist'), ('transport hub'), ('residential');

INSERT INTO ad_formats (format_name, is_digital) VALUES
    ('billboard', FALSE), ('digital screen', TRUE), ('platform wall', FALSE),
    ('stairs wrap', FALSE), ('ticket gate', FALSE), ('train interior', FALSE);

-- ---------------------------------------------------------------------
-- 8) Example business questions
-- ---------------------------------------------------------------------
-- Q1: Top 10 stations by daily riders
-- SELECT name_en, avg_daily_riders FROM station_ad_profile
-- ORDER BY avg_daily_riders DESC NULLS LAST LIMIT 10;

-- Q2: Best stations to reach students
-- SELECT name_en, universities, avg_daily_riders FROM station_ad_profile
-- WHERE universities > 0 ORDER BY universities DESC, avg_daily_riders DESC;

-- Q3: Cheapest reach (lowest cost per 1000 riders)
-- SELECT name_en, cost_per_1000_riders_egp FROM station_ad_profile
-- WHERE cost_per_1000_riders_egp IS NOT NULL ORDER BY cost_per_1000_riders_egp LIMIT 10;

-- Q4: Ad-space occupancy per station this month
-- SELECT s.name_en,
--        COUNT(DISTINCT a.ad_space_id) AS total_spaces,
--        COUNT(DISTINCT b.ad_space_id) AS booked_spaces
-- FROM stations s
-- JOIN ad_spaces a USING (station_id)
-- LEFT JOIN bookings b ON b.ad_space_id = a.ad_space_id
--      AND CURRENT_DATE BETWEEN b.start_date AND b.end_date
-- GROUP BY s.name_en ORDER BY booked_spaces DESC;
