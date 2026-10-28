"""Analytics and machine-learning helpers. Pure pandas / scikit-learn, no UI.

* daily_bookings / monthly_occupancy / space_occupancy: spread each booking over the days it runs,
  so revenue and occupancy are counted in the months they actually happen.
* revenue_forecast: trend + monthly seasonality (ridge regression), with a back-test and a range.
* demand_model: gradient boosting that predicts how often a space gets booked from its station and format,
  then flags spaces that are booked much less (or more) than similar spaces.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


# ---------------------------------------------------------------- occupancy
def daily_bookings(bk: pd.DataFrame) -> pd.DataFrame:
    """One row per booking per day, with that day's share of the booking price."""
    b = bk[["booking_id", "ad_space_id", "campaign_id", "start_date", "end_date", "price_egp"]].copy()
    b["n"] = (b["end_date"] - b["start_date"]).dt.days + 1
    b = b[b["n"] > 0]
    rep = b.loc[b.index.repeat(b["n"])].copy()
    rep["day"] = rep["start_date"] + pd.to_timedelta(rep.groupby(level=0).cumcount(), unit="D")
    rep["revenue"] = rep["price_egp"] / rep["n"]
    return rep[["booking_id", "ad_space_id", "campaign_id", "day", "revenue"]].reset_index(drop=True)


def monthly_occupancy(daily: pd.DataFrame, n_spaces: int) -> pd.DataFrame:
    """Per month: revenue earned and the share of space-days that were booked."""
    m = daily.assign(month=daily["day"].dt.to_period("M")).groupby("month").agg(
        revenue=("revenue", "sum"), space_days=("ad_space_id", "size")).reset_index()
    m["days"] = m["month"].dt.days_in_month
    m["occupancy"] = m["space_days"] / (m["days"] * max(n_spaces, 1))
    m["month_start"] = m["month"].dt.to_timestamp()
    return m


def space_occupancy(daily: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Per space over [start, end]: days booked, occupancy and revenue."""
    w = daily[(daily["day"] >= start) & (daily["day"] <= end)]
    days = (end - start).days + 1
    g = w.groupby("ad_space_id").agg(booked_days=("day", "nunique"), revenue=("revenue", "sum"))
    g["occupancy"] = g["booked_days"] / days
    return g


# ---------------------------------------------------------------- revenue forecast
@dataclass
class Forecast:
    history: pd.DataFrame      # month_start, revenue (complete months only)
    future: pd.DataFrame       # month_start, forecast, low, high, booked
    backtest_mape: float       # error on the last `holdout` months when the model never saw them
    holdout: int


def _design(t: np.ndarray, months: np.ndarray) -> np.ndarray:
    season = np.eye(12)[months - 1]
    return np.column_stack([t, season])


def revenue_forecast(monthly: pd.DataFrame, this_month: pd.Timestamp, horizon: int = 6, holdout: int = 3) -> Forecast:
    from sklearn.linear_model import Ridge

    m = monthly.sort_values("month_start")
    hist = m[m["month_start"] < this_month.to_period("M").to_timestamp()][["month_start", "revenue"]].reset_index(drop=True)
    t = np.arange(len(hist), dtype=float)
    months = hist["month_start"].dt.month.to_numpy()
    y = hist["revenue"].to_numpy()

    def fit(idx):
        mdl = Ridge(alpha=1.0)
        mdl.fit(_design(t[idx], months[idx]), y[idx])
        return mdl

    # back-test: train without the last `holdout` months, score on them
    holdout = min(holdout, max(len(hist) - 12, 1))
    train = np.arange(len(hist) - holdout)
    test = np.arange(len(hist) - holdout, len(hist))
    pred = fit(train).predict(_design(t[test], months[test]))
    mape = float(np.mean(np.abs(pred - y[test]) / np.maximum(y[test], 1)))

    mdl = fit(np.arange(len(hist)))
    resid = y - mdl.predict(_design(t, months))
    spread = float(np.std(resid, ddof=1)) * 1.28  # ~80% range

    start = hist["month_start"].iloc[-1] + pd.offsets.MonthBegin(1)
    fut_months = pd.date_range(start, periods=horizon, freq="MS")
    ft = np.arange(len(hist), len(hist) + horizon, dtype=float)
    fc = np.maximum(mdl.predict(_design(ft, fut_months.month.to_numpy())), 0)
    booked = m.set_index("month_start")["revenue"].reindex(fut_months).fillna(0).to_numpy()
    fut = pd.DataFrame({"month_start": fut_months, "forecast": fc, "low": np.maximum(fc - spread, 0),
                        "high": fc + spread, "booked": booked})
    return Forecast(hist, fut, mape, holdout)


# ---------------------------------------------------------------- demand model
FEATURES = {  # column -> (arabic, english) shown in the importance chart
    "avg_daily_riders": ("عدد الركاب", "Daily riders"),
    "ad_score": ("الدرجة الإعلانية", "Ad score"),
    "purchasing_power": ("القوة الشرائية", "Purchasing power"),
    "monthly_price_egp": ("السعر الشهري", "Monthly price"),
    "price_pos": ("مكان السعر في نطاق السوق", "Price within market range"),
    "lines_count": ("عدد الخطوط", "Lines served"),
    "is_interchange": ("محطة تحويل", "Interchange"),
    "format_name": ("نوع الإعلان", "Ad format"),
    "zone": ("المكان في المحطة", "Zone"),
    "tier": ("فئة المحطة", "Station tier"),
    "area_type": ("طبيعة المنطقة", "Area type"),
}
CATEGORICAL = ["format_name", "zone", "tier", "area_type"]


@dataclass
class DemandModel:
    table: pd.DataFrame        # one row per active space: actual, predicted, gap
    importance: pd.DataFrame   # feature, importance (share of the model's accuracy)
    r2: float                  # cross-validated R²
    mae: float                 # cross-validated mean absolute error (occupancy points)


def _features(df: pd.DataFrame) -> pd.DataFrame:
    X = df[[c for c in FEATURES if c not in ("price_pos", "is_interchange")]].copy()
    rng = (df["price_max"] - df["price_min"]).replace(0, np.nan)
    X["price_pos"] = ((df["monthly_price_egp"] - df["price_min"]) / rng).fillna(.5)
    X["is_interchange"] = df["is_interchange"].astype(bool).astype(int)
    X["purchasing_power"] = pd.to_numeric(X["purchasing_power"], errors="coerce").fillna(0)
    return pd.get_dummies(X, columns=CATEGORICAL, dtype=float)


def demand_model(spaces: pd.DataFrame, profile: pd.DataFrame, occ: pd.DataFrame, seed: int = 0) -> DemandModel:
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.inspection import permutation_importance
    from sklearn.model_selection import KFold, cross_val_predict

    df = spaces[spaces["is_active"].astype(bool)].merge(
        profile[["station_id", "avg_daily_riders", "ad_score", "purchasing_power", "lines_count", "is_interchange",
                 "tier", "area_type"]], on="station_id")
    df["occupancy"] = df["ad_space_id"].map(occ["occupancy"]).fillna(0)
    X, y = _features(df), df["occupancy"].to_numpy()

    model = GradientBoostingRegressor(n_estimators=200, max_depth=2, learning_rate=.05, random_state=seed)
    cv = KFold(5, shuffle=True, random_state=seed)
    pred = cross_val_predict(model, X, y, cv=cv)  # every space is scored by a model that never saw it
    ss_res, ss_tot = ((y - pred) ** 2).sum(), ((y - y.mean()) ** 2).sum()
    r2, mae = float(1 - ss_res / ss_tot) if ss_tot else 0.0, float(np.abs(y - pred).mean())

    model.fit(X, y)
    pi = permutation_importance(model, X, y, n_repeats=10, random_state=seed)
    raw = pd.Series(pi.importances_mean, index=X.columns).clip(lower=0)
    grouped = raw.groupby(lambda c: next((k for k in CATEGORICAL if c.startswith(k + "_")), c)).sum()
    imp = (grouped / grouped.sum()).sort_values(ascending=False).rename_axis("feature").reset_index(name="importance")

    df["predicted"] = np.clip(pred, 0, 1)
    df["gap"] = df["occupancy"] - df["predicted"]
    return DemandModel(df, imp, r2, mae)
