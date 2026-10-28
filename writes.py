"""Everything that changes the database. Each function runs in one transaction."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


SCHEMA_UPDATES = [
    # 08_request_form.sql: contact details for bookings requested from the website (safe to run many times)
    "ALTER TABLE cairo_metro.campaigns ADD COLUMN IF NOT EXISTS contact_name  VARCHAR(120)",
    "ALTER TABLE cairo_metro.campaigns ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(40)",
    "ALTER TABLE cairo_metro.campaigns ADD COLUMN IF NOT EXISTS contact_email VARCHAR(160)",
    "ALTER TABLE cairo_metro.campaigns ADD COLUMN IF NOT EXISTS notes         TEXT",
    "ALTER TABLE cairo_metro.campaigns ADD COLUMN IF NOT EXISTS created_at    TIMESTAMPTZ DEFAULT now()",
]


SUBSCRIPTIONS_SQL = """
CREATE TABLE IF NOT EXISTS cairo_metro.subscriptions (
    subscription_id  SERIAL PRIMARY KEY,
    full_name        VARCHAR(120) NOT NULL,
    phone            VARCHAR(40),
    governorate      VARCHAR(40),
    district         VARCHAR(80),
    address          TEXT,
    home_station_id  INT NOT NULL REFERENCES cairo_metro.stations(station_id),
    work_station_id  INT REFERENCES cairo_metro.stations(station_id),
    plan             VARCHAR(12) NOT NULL CHECK (plan IN ('annual_2', 'annual_3')),
    price_egp        NUMERIC(10,2) NOT NULL,
    start_date       DATE NOT NULL,
    status           VARCHAR(12) NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'approved', 'shipped', 'delivered', 'cancelled')),
    is_demo          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS subscriptions_home_idx ON cairo_metro.subscriptions (home_station_id);
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
"""


def ensure_schema(eng) -> bool:
    """Create what the newer pages need if the database doesn't have it yet (09_subscriptions.sql and
    08_request_form.sql). Each step is separate, so one failing never blocks the others."""
    ok = True
    for steps in (SCHEMA_UPDATES, [SUBSCRIPTIONS_SQL]):
        try:
            with eng.begin() as conn:
                for stmt in steps:
                    conn.exec_driver_sql(stmt)
        except Exception:  # noqa: BLE001  (read-only user: the app still works without these)
            ok = False
    return ok


# ---------------------------------------------------------------- annual subscription cards
def add_subscription(eng, full_name: str, phone: str, governorate: str, district: str, address: str,
                     home_station_id: int, work_station_id: int | None, plan: str, price: float,
                     start: dt.date) -> int:
    with eng.begin() as conn:
        return conn.execute(text(
            "INSERT INTO cairo_metro.subscriptions (full_name, phone, governorate, district, address, home_station_id, "
            "work_station_id, plan, price_egp, start_date) "
            "VALUES (:n, :p, :g, :d, :a, :h, :w, :pl, :pr, :s) RETURNING subscription_id"),
            {"n": full_name.strip(), "p": phone.strip(), "g": governorate, "d": district, "a": address.strip(),
             "h": int(home_station_id), "w": int(work_station_id) if work_station_id else None, "pl": plan,
             "pr": float(price), "s": start}).scalar_one()


def track_subscription(eng, subscription_id: int, phone: str):
    """Status of one request, only when the phone number matches (so nobody can look up other people)."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    with eng.connect() as conn:
        row = conn.execute(text(
            "SELECT subscription_id, full_name, plan, start_date, status, home_station_id, district, created_at, phone "
            "FROM cairo_metro.subscriptions WHERE subscription_id = :i AND NOT is_demo"),
            {"i": int(subscription_id)}).mappings().first()
    if not row or "".join(ch for ch in (row["phone"] or "") if ch.isdigit()) != digits or not digits:
        return None
    return dict(row)


def subscriptions_admin(eng):
    """Full details for the admin page only."""
    import pandas as pd
    with eng.connect() as conn:
        return pd.read_sql(text(
            "SELECT subscription_id, full_name, phone, governorate, district, address, home_station_id, work_station_id, "
            "plan, price_egp, start_date, status, is_demo, created_at FROM cairo_metro.subscriptions "
            "ORDER BY is_demo, created_at DESC"), conn)


def set_subscription_status(eng, ids: list[int], status: str) -> int:
    if not ids:
        return 0
    with eng.begin() as conn:
        return conn.execute(text("UPDATE cairo_metro.subscriptions SET status = :st WHERE subscription_id = ANY(:ids)"),
                            {"st": status, "ids": [int(i) for i in ids]}).rowcount


class BookingConflict(Exception):
    """One of the spaces was booked by someone else for overlapping dates."""


def _is_overlap(err: DBAPIError) -> bool:
    return "no_overlapping_bookings" in str(err.orig) or getattr(err.orig, "pgcode", "") == "23P01"


def get_or_create_advertiser(conn, company: str, industry: str) -> int:
    row = conn.execute(text("SELECT advertiser_id FROM cairo_metro.advertisers WHERE lower(company_name) = lower(:n)"),
                       {"n": company.strip()}).first()
    if row:
        return row[0]
    return conn.execute(text("INSERT INTO cairo_metro.advertisers (company_name, industry) VALUES (:n, :i) "
                             "RETURNING advertiser_id"), {"n": company.strip(), "i": industry}).scalar_one()


def book_plan(eng, company: str, industry: str, campaign_name: str, audience: str, budget: float,
              start: dt.date, end: dt.date, items: list[tuple[int, float]], status: str = "pending",
              source: str = "web", contact: dict | None = None) -> int:
    """Create advertiser (if new) + campaign + one booking per space. Returns the campaign id.
    contact: optional {name, phone, email, notes} saved on the campaign (needs ensure_schema)."""
    contact = {k: (v or "").strip() or None for k, v in (contact or {}).items()}
    try:
        with eng.begin() as conn:
            adv = get_or_create_advertiser(conn, company, industry)
            params = {"a": adv, "n": campaign_name.strip(), "t": audience, "s": start, "e": end, "b": budget}
            if any(contact.values()):
                params.update(cn=contact.get("name"), cp=contact.get("phone"), ce=contact.get("email"), no=contact.get("notes"))
                cid = conn.execute(text(
                    "INSERT INTO cairo_metro.campaigns (advertiser_id, campaign_name, target_audience, start_date, end_date, "
                    "budget_egp, contact_name, contact_phone, contact_email, notes) "
                    "VALUES (:a, :n, :t, :s, :e, :b, :cn, :cp, :ce, :no) RETURNING campaign_id"), params).scalar_one()
            else:
                cid = conn.execute(text(
                    "INSERT INTO cairo_metro.campaigns (advertiser_id, campaign_name, target_audience, start_date, end_date, budget_egp) "
                    "VALUES (:a, :n, :t, :s, :e, :b) RETURNING campaign_id"), params).scalar_one()
            conn.execute(text(
                "INSERT INTO cairo_metro.bookings (campaign_id, ad_space_id, start_date, end_date, price_egp, status, source) "
                "VALUES (:c, :sp, :s, :e, :p, :st, :src)"),
                [{"c": cid, "sp": int(sp), "s": start, "e": end, "p": float(price), "st": status, "src": source}
                 for sp, price in items])
        return cid
    except DBAPIError as err:
        if _is_overlap(err):
            raise BookingConflict from err
        raise


def add_booking(eng, campaign_id: int, ad_space_id: int, start: dt.date, end: dt.date, price: float,
                status: str = "confirmed") -> int:
    try:
        with eng.begin() as conn:
            return conn.execute(text(
                "INSERT INTO cairo_metro.bookings (campaign_id, ad_space_id, start_date, end_date, price_egp, status, source) "
                "VALUES (:c, :sp, :s, :e, :p, :st, 'admin') RETURNING booking_id"),
                {"c": campaign_id, "sp": ad_space_id, "s": start, "e": end, "p": price, "st": status}).scalar_one()
    except DBAPIError as err:
        if _is_overlap(err):
            raise BookingConflict from err
        raise


def add_campaign(eng, company: str, industry: str, campaign_name: str, audience: str,
                 start: dt.date, end: dt.date, budget: float) -> int:
    with eng.begin() as conn:
        adv = get_or_create_advertiser(conn, company, industry)
        return conn.execute(text(
            "INSERT INTO cairo_metro.campaigns (advertiser_id, campaign_name, target_audience, start_date, end_date, budget_egp) "
            "VALUES (:a, :n, :t, :s, :e, :b) RETURNING campaign_id"),
            {"a": adv, "n": campaign_name.strip(), "t": audience, "s": start, "e": end, "b": budget}).scalar_one()


def set_booking_status(eng, booking_ids: list[int], status: str) -> int:
    """Approve / cancel / restore. Restoring can clash with a newer booking -> BookingConflict."""
    if not booking_ids:
        return 0
    try:
        with eng.begin() as conn:
            res = conn.execute(text("UPDATE cairo_metro.bookings SET status = :st WHERE booking_id = ANY(:ids)"),
                               {"st": status, "ids": [int(i) for i in booking_ids]})
            return res.rowcount
    except DBAPIError as err:
        if _is_overlap(err):
            raise BookingConflict from err
        raise


def update_spaces(eng, changes: list[dict]) -> int:
    """changes: [{ad_space_id, monthly_price_egp, is_active}]"""
    if not changes:
        return 0
    with eng.begin() as conn:
        conn.execute(text("UPDATE cairo_metro.ad_spaces SET monthly_price_egp = :p, is_active = :a "
                          "WHERE ad_space_id = :id"),
                     [{"p": float(c["monthly_price_egp"]), "a": bool(c["is_active"]), "id": int(c["ad_space_id"])}
                      for c in changes])
    return len(changes)
