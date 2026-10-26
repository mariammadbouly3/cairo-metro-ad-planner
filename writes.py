"""Everything that changes the database. Each function runs in one transaction."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


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
              start: dt.date, end: dt.date, items: list[tuple[int, float]], status: str = "pending") -> int:
    """Create advertiser (if new) + campaign + one booking per space. Returns the campaign id."""
    try:
        with eng.begin() as conn:
            adv = get_or_create_advertiser(conn, company, industry)
            cid = conn.execute(text(
                "INSERT INTO cairo_metro.campaigns (advertiser_id, campaign_name, target_audience, start_date, end_date, budget_egp) "
                "VALUES (:a, :n, :t, :s, :e, :b) RETURNING campaign_id"),
                {"a": adv, "n": campaign_name.strip(), "t": audience, "s": start, "e": end, "b": budget}).scalar_one()
            conn.execute(text(
                "INSERT INTO cairo_metro.bookings (campaign_id, ad_space_id, start_date, end_date, price_egp, status, source) "
                "VALUES (:c, :sp, :s, :e, :p, :st, 'web')"),
                [{"c": cid, "sp": int(sp), "s": start, "e": end, "p": float(price), "st": status} for sp, price in items])
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
