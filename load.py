"""Load the ArrowFin dataset and tag every fill with its CME trading session."""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent / "dataset"
CUT = pd.Timestamp("2026-08-25T14:30:00Z")
EXCHANGE_TZ = "America/Chicago"


def session_date(ts_utc: pd.Series) -> pd.Series:
    """CME Globex session a timestamp belongs to.

    A session opens at 17:00 Central and closes at 16:00 the next afternoon; it is
    named after the day it closes. Shifting Central time forward 7h maps 17:00 to
    midnight, so the shifted calendar date is the session date. Working in Central
    time (not a fixed UTC offset) keeps this right across DST changes.
    """
    central = ts_utc.dt.tz_convert(EXCHANGE_TZ)
    return (central + pd.Timedelta(hours=7)).dt.normalize().dt.tz_localize(None)


def load():
    """Return fills (enriched) plus the reference tables, keyed by name."""
    accounts = pd.read_csv(DATA / "accounts.csv", parse_dates=["created_at"])
    traders = pd.read_csv(DATA / "traders.csv", parse_dates=["created_at"])
    brokers = pd.read_csv(DATA / "brokers.csv")
    instruments = pd.read_csv(DATA / "instruments.csv")
    marks = pd.read_csv(DATA / "market_prices.csv", parse_dates=["as_of"])

    fills = pd.read_csv(DATA / "fills.csv", parse_dates=["filled_at"])
    fills = fills[fills["filled_at"] <= CUT]  # nothing after "now"
    fills["session"] = session_date(fills["filled_at"])
    fills["signed_qty"] = fills["quantity"].where(fills["side"] == "BUY", -fills["quantity"])
    fills = fills.merge(
        instruments[["symbol", "point_value_usd"]],
        left_on="instrument_symbol", right_on="symbol", how="left", validate="many_to_one",
    ).drop(columns="symbol")
    fills = fills.merge(
        accounts[["id", "trader_id", "account_type", "status"]].rename(columns={"id": "account_id"}),
        on="account_id", how="left", validate="many_to_one",
    )
    assert fills["point_value_usd"].notna().all(), "fill on an instrument with no spec"
    assert fills["trader_id"].notna().all(), "fill on an unknown account"

    return {
        "fills": fills.sort_values("filled_at").reset_index(drop=True),
        "accounts": accounts,
        "traders": traders,
        "brokers": brokers,
        "instruments": instruments,
        "marks": marks,
    }
