-- 09: annual metro subscription cards, delivered to the rider's home address.
-- The app runs this automatically when it starts (writes.ensure_schema), so you don't have to.
-- Safe to run again: the table is created only once, and the demo riders are added only while the table is empty.
SET search_path TO cairo_metro;

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id  SERIAL PRIMARY KEY,
    full_name        VARCHAR(120) NOT NULL,
    phone            VARCHAR(40),
    governorate      VARCHAR(40),
    district         VARCHAR(80),
    address          TEXT,                              -- where the card is delivered
    home_station_id  INT NOT NULL REFERENCES stations(station_id),
    work_station_id  INT REFERENCES stations(station_id), -- where they ride to most (work / study), optional
    plan             VARCHAR(12) NOT NULL CHECK (plan IN ('annual_2', 'annual_3')),
    price_egp        NUMERIC(10,2) NOT NULL,
    start_date       DATE NOT NULL,
    status           VARCHAR(12) NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'approved', 'shipped', 'delivered', 'cancelled')),
    is_demo          BOOLEAN NOT NULL DEFAULT FALSE,    -- simulated riders, so the analysis has data from day one
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS subscriptions_home_idx ON subscriptions (home_station_id);

-- 1,200 simulated annual subscribers. Home stations are weighted by ridership and how residential the area is;
-- work/study stations by ridership and how commercial it is. Same result every time (setseed).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM cairo_metro.subscriptions) THEN
    PERFORM setseed(0.42);
    WITH st AS (
        SELECT station_id, governorate, district, avg_daily_riders::numeric AS riders,
               CASE area_type WHEN 'Dense Residential' THEN 1.6 WHEN 'Upscale Residential' THEN 1.4
                              WHEN 'Suburban' THEN 1.5 WHEN 'CBD' THEN 0.4 WHEN 'Commercial' THEN 0.7 ELSE 0.9 END AS home_w,
               CASE area_type WHEN 'CBD' THEN 2.5 WHEN 'Commercial' THEN 1.8 WHEN 'Industrial' THEN 1.3 ELSE 0.6 END
                 + CASE WHEN near_university THEN 1.0 ELSE 0 END AS work_w
        FROM cairo_metro.station_ad_profile
    ),
    home AS (SELECT station_id, governorate, district,
                    SUM(riders * home_w) OVER (ORDER BY station_id) / SUM(riders * home_w) OVER () AS cum FROM st),
    work AS (SELECT station_id, SUM(riders * work_w) OVER (ORDER BY station_id) / SUM(riders * work_w) OVER () AS cum FROM st),
    draws AS (SELECT g, random() AS u_home, random() AS u_work, random() AS u_plan, random() AS u_day, random() AS u_status
              FROM generate_series(1, 1200) AS g)
    INSERT INTO cairo_metro.subscriptions
        (full_name, governorate, district, home_station_id, work_station_id, plan, price_egp, start_date, status, is_demo, created_at)
    SELECT 'Demo rider ' || d.g, h.governorate, h.district, h.station_id,
           NULLIF(w.station_id, h.station_id),
           CASE WHEN d.u_plan < 0.72 THEN 'annual_2' ELSE 'annual_3' END,
           CASE WHEN d.u_plan < 0.72 THEN 4235 ELSE 5335 END,
           (CURRENT_DATE - (d.u_day * 365)::int),
           CASE WHEN d.u_status < 0.90 THEN 'delivered' WHEN d.u_status < 0.95 THEN 'shipped'
                WHEN d.u_status < 0.98 THEN 'approved' ELSE 'cancelled' END,
           TRUE, now() - (d.u_day * 365 || ' days')::interval
    FROM draws d
    CROSS JOIN LATERAL (SELECT * FROM home WHERE home.cum >= d.u_home ORDER BY home.cum LIMIT 1) h
    CROSS JOIN LATERAL (SELECT * FROM work WHERE work.cum >= d.u_work ORDER BY work.cum LIMIT 1) w;
  END IF;
END $$;

-- Subscribers living near each station: a steady audience that passes the station's ads twice a day
SELECT s.name_en, s.name_ar, COUNT(*) AS subscribers
FROM subscriptions x JOIN stations s ON s.station_id = x.home_station_id
WHERE x.status <> 'cancelled'
GROUP BY 1, 2 ORDER BY subscribers DESC LIMIT 10;
