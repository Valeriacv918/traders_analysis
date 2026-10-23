"""Per-session profit and loss, per account and per trader.

Accounting: average cost per (account, instrument). A fill that reduces or flips a
position realizes (exit - avg_entry) * qty * point_value. Whatever is still open at
the cut is marked to market_prices.csv. Commissions are subtracted as charged
(commission_usd is the total for the fill, already per contract per side).

Every historical session in this dataset ends flat, so a session's P&L never
depends on a previous session's settlement price. We assert that rather than
assume it: if a position were carried overnight we would need settles we don't have.
"""
import numpy as np
import pandas as pd

from load import CUT, load


def _walk_fills(group: pd.DataFrame) -> pd.DataFrame:
    """Average-cost walk over one (account, instrument)'s fills in time order."""
    pos, avg = 0, 0.0
    realized, position_after = [], []
    for qty, price, pv in zip(group["signed_qty"], group["price"], group["point_value_usd"]):
        r = 0.0
        if pos != 0 and np.sign(qty) != np.sign(pos):  # reducing, closing or flipping
            closed = min(abs(qty), abs(pos))
            r = closed * (price - avg) * np.sign(pos) * pv
            if abs(qty) > abs(pos):    # flipped: remainder opens at this price
                avg = price
            elif abs(qty) == abs(pos):
                avg = 0.0
        else:                          # opening or adding
            avg = (avg * abs(pos) + price * abs(qty)) / (abs(pos) + abs(qty))
        pos += qty
        realized.append(r)
        position_after.append(pos)
    return group.assign(realized_usd=realized, position_after=position_after, avg_after=avg)


def account_sessions(fills: pd.DataFrame, marks: pd.DataFrame) -> pd.DataFrame:
    """One row per (account, instrument, session)."""
    walked = (
        fills.sort_values("filled_at")
        .groupby(["account_id", "instrument_symbol"], group_keys=False)[fills.columns]
        .apply(_walk_fills)
    )
    walked["notional_after"] = walked["position_after"].abs() * walked["price"] * walked["point_value_usd"]

    keys = ["trader_id", "account_id", "account_type", "status", "instrument_symbol", "session"]
    out = walked.groupby(keys).agg(
        realized_usd=("realized_usd", "sum"),
        commission_usd=("commission_usd", "sum"),
        n_fills=("id", "size"),
        n_orders=("order_id", "nunique"),
        contracts=("quantity", "sum"),
        max_position=("position_after", lambda s: s.abs().max()),
        max_notional_usd=("notional_after", "max"),
        open_position=("position_after", "last"),
        open_avg_price=("avg_after", "last"),
        point_value_usd=("point_value_usd", "first"),
        first_fill=("filled_at", "min"),
        last_fill=("filled_at", "max"),
    ).reset_index()

    today = fills["session"].max()
    carried = out[(out["open_position"] != 0) & (out["session"] < today)]
    assert carried.empty, f"positions carried overnight, need settlement prices:\n{carried}"

    mark = out["instrument_symbol"].map(marks.set_index("symbol")["mark_price"])
    out["unrealized_usd"] = np.where(
        out["open_position"] != 0,
        out["open_position"] * (mark - out["open_avg_price"]) * out["point_value_usd"],
        0.0,
    )
    out["net_pnl_usd"] = out["realized_usd"] + out["unrealized_usd"] - out["commission_usd"]
    return out


def trader_sessions(acct: pd.DataFrame) -> pd.DataFrame:
    """Roll accounts and instruments up to one row per (trader, session)."""
    out = acct.groupby(["trader_id", "session"]).agg(
        net_pnl_usd=("net_pnl_usd", "sum"),
        realized_usd=("realized_usd", "sum"),
        unrealized_usd=("unrealized_usd", "sum"),
        commission_usd=("commission_usd", "sum"),
        n_fills=("n_fills", "sum"),
        n_orders=("n_orders", "sum"),
        contracts=("contracts", "sum"),
        max_notional_usd=("max_notional_usd", "max"),
        open_positions=("open_position", lambda s: int((s != 0).sum())),
        instruments=("instrument_symbol", lambda s: ",".join(sorted(set(s)))),
        account_types=("account_type", lambda s: ",".join(sorted(set(s)))),
        accounts=("account_id", "nunique"),
        first_fill=("first_fill", "min"),
        last_fill=("last_fill", "max"),
    ).reset_index()
    out["is_today"] = out["session"] == out["session"].max()
    return out


if __name__ == "__main__":
    d = load()
    acct = account_sessions(d["fills"], d["marks"])
    ts = trader_sessions(acct)
    pd.set_option("display.width", 200, "display.max_columns", 30)
    print(f"cut {CUT}; {len(ts)} trader-sessions, {ts.trader_id.nunique()} traders\n")
    print("open positions at the cut:")
    print(acct[acct.open_position != 0][
        ["trader_id", "account_id", "instrument_symbol", "open_position", "open_avg_price", "unrealized_usd"]
    ].to_string(index=False))
    print("\ntoday, worst 15 by net P&L (raw dollars, not yet normalised):")
    cols = ["trader_id", "net_pnl_usd", "realized_usd", "unrealized_usd", "commission_usd",
            "n_orders", "contracts", "instruments", "account_types"]
    print(ts[ts.is_today].nsmallest(15, "net_pnl_usd")[cols].round(0).to_string(index=False))
