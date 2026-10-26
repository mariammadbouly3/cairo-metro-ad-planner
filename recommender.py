"""Recommendation engine for Cairo Metro advertising.

Pure pandas, no UI: given an audience, budget and dates, pick the best *available*
ad spaces across the metro network.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

AUDIENCES = [
    "Students",
    "Upper-middle class",
    "Office workers & shoppers",
    "Commuters / intercity travellers",
    "Mass-market shoppers",
    "Tourists & visitors",
    "Local residents (mass market)",
]

# Which audiences each industry usually targets (used to pre-fill the form)
INDUSTRY_AUDIENCE = {
    "Telecom": ["Students", "Commuters / intercity travellers", "Local residents (mass market)"],
    "EdTech/courses": ["Students"],
    "Fintech wallets": ["Students", "Commuters / intercity travellers"],
    "Banks": ["Upper-middle class", "Office workers & shoppers"],
    "Real estate": ["Upper-middle class"],
    "Cars": ["Upper-middle class"],
    "Government awareness": ["Office workers & shoppers", "Mass-market shoppers"],
    "FMCG": ["Mass-market shoppers", "Local residents (mass market)"],
    "Retail & fashion": ["Mass-market shoppers", "Upper-middle class"],
    "Food delivery": ["Commuters / intercity travellers", "Students"],
    "Ride-hailing": ["Commuters / intercity travellers"],
    "Tourism & hospitality": ["Tourists & visitors", "Upper-middle class"],
    "Local retail": ["Local residents (mass market)"],
}


@dataclass
class Plan:
    spaces: pd.DataFrame      # one row per recommended ad space
    stations: pd.DataFrame    # one row per station in the plan
    total_cost: float
    impressions: float        # rider-days reached (each station counted once)
    cpm: float                # cost per 1,000 impressions
    budget_left: float


def end_date(start: dt.date, months: int) -> dt.date:
    return start + dt.timedelta(days=30 * months - 1)


def audience_match(target_audience: pd.Series, audiences: list[str]) -> pd.Series:
    """Share of the requested audiences that a station serves (0..1)."""
    if not audiences:
        return pd.Series(1.0, index=target_audience.index)
    ta = target_audience.fillna("")
    hits = sum(ta.str.contains(a, regex=False).astype(int) for a in audiences)
    return hits / len(audiences)


def available_spaces(spaces: pd.DataFrame, bookings: pd.DataFrame, start: dt.date, end: dt.date) -> pd.DataFrame:
    """Active spaces with no booking overlapping [start, end]."""
    b = bookings.copy()
    b["start_date"] = pd.to_datetime(b["start_date"]).dt.date
    b["end_date"] = pd.to_datetime(b["end_date"]).dt.date
    busy = b[(b["start_date"] <= end) & (b["end_date"] >= start)]["ad_space_id"].unique()
    return spaces[spaces["is_active"].astype(bool) & ~spaces["ad_space_id"].isin(busy)].copy()


def score_stations(profile: pd.DataFrame, audiences: list[str]) -> pd.DataFrame:
    p = profile.copy()
    p["audience_fit"] = audience_match(p["target_audience"], audiences)
    riders = p["avg_daily_riders"].fillna(0).astype(float)
    p["reach_norm"] = np.sqrt(riders) / np.sqrt(riders.max() or 1)
    # Fit: audience match matters most, then the station's overall ad score, then raw reach
    p["fit_score"] = (0.5 * p["audience_fit"] + 0.3 * p["ad_score"].astype(float) / 100 + 0.2 * p["reach_norm"]).round(4)
    return p


def recommend(
    profile: pd.DataFrame,
    spaces: pd.DataFrame,
    bookings: pd.DataFrame,
    audiences: list[str],
    budget: float,
    start: dt.date,
    months: int,
    lines: list[str] | None = None,
    formats: list[str] | None = None,
    max_per_station: int = 2,
    max_station_share: float = 0.35,
    min_audience_fit: float = 0.01,
) -> Plan:
    end = end_date(start, months)
    st = score_stations(profile, audiences)
    if lines:
        st = st[st["lines"].fillna("").apply(lambda x: any(l in x.split("/") for l in lines))]
    st = st[st["audience_fit"] >= min_audience_fit]

    sp = available_spaces(spaces, bookings, start, end)
    if formats:
        sp = sp[sp["format_name"].isin(formats)]
    sp = sp.merge(
        st[["station_id", "name_en", "name_ar", "lines", "tier", "ad_score", "avg_daily_riders",
            "audience_fit", "fit_score", "latitude", "longitude"]],
        on="station_id",
    )
    if sp.empty:
        return Plan(sp, sp, 0.0, 0.0, 0.0, budget)

    sp["cost"] = sp["monthly_price_egp"].astype(float) * months
    sp["reach_per_1k_egp"] = sp["avg_daily_riders"].astype(float) * 30 * months / sp["cost"] * 1000
    eff = sp["reach_per_1k_egp"] / sp["reach_per_1k_egp"].max()
    # Value: how well the station fits, balanced against how cheaply it reaches people
    sp["value"] = (0.5 * sp["fit_score"] + 0.5 * np.sqrt(eff)).round(4)
    sp = sp.sort_values(["value", "fit_score"], ascending=False)

    # Greedy pick. Cap each station's share of the budget so the plan spreads its reach,
    # unless the budget is too small to buy more than one space anyway.
    cap = max(max_station_share * budget, sp["cost"].min())
    chosen, spent, per_station, station_spend = [], 0.0, {}, {}
    for row in sp.itertuples():
        if per_station.get(row.station_id, 0) >= max_per_station:
            continue
        if spent + row.cost > budget:
            continue
        if station_spend.get(row.station_id, 0) + row.cost > cap:
            continue
        chosen.append(row.Index)
        spent += row.cost
        per_station[row.station_id] = per_station.get(row.station_id, 0) + 1
        station_spend[row.station_id] = station_spend.get(row.station_id, 0) + row.cost

    plan = sp.loc[chosen].copy()
    plan.insert(0, "priority", range(1, len(plan) + 1))
    plan["start_date"], plan["end_date"] = start, end

    stations = (
        plan.groupby(["station_id", "name_en", "name_ar", "lines", "tier", "latitude", "longitude"], dropna=False)
        .agg(spaces=("ad_space_id", "count"), cost=("cost", "sum"),
             daily_riders=("avg_daily_riders", "first"), audience_fit=("audience_fit", "first"))
        .reset_index()
        .sort_values("cost", ascending=False)
    )
    days = (end - start).days + 1
    impressions = float((stations["daily_riders"] * days).sum()) if not stations.empty else 0.0
    cpm = spent / impressions * 1000 if impressions else 0.0
    return Plan(plan, stations, spent, impressions, cpm, budget - spent)
