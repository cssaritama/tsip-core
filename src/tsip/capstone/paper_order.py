"""Paper-trading order example for the course project (broker API bonus). Educational only.

It turns the latest prediction of the course model into the order that strategy sim1 would place,
and prints it. With ``--send`` and a paper account's keys it submits the order to Alpaca's
**paper** trading endpoint, which uses simulated money; no other endpoint is accepted.

This is not a signal and not advice: on the test period the strategies did not beat buy and hold
(``docs/CAPSTONE.md``, step 5). The example exists to show the plumbing from prediction to order.

    python -m tsip.capstone.paper_order                      # print the orders (dry run)
    python -m tsip.capstone.paper_order --send --notional 1000

Keys: ``ALPACA_API_KEY_ID`` and ``ALPACA_API_SECRET_KEY`` of a paper account.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path

PAPER_URL = "https://paper-api.alpaca.markets/v2/orders"
FUNDS = ("SPY", "QQQ", "GLD")  # equities only in this example


def build_orders(
    latest: dict[str, float], threshold: float, notional: float, sleeve: float, as_of: str = ""
) -> list[dict]:
    """Market buy orders, a fixed share of the notional each, for the funds whose probability clears the threshold."""
    orders = []
    for symbol in FUNDS:
        p = latest.get(symbol)
        if p is not None and p > threshold:
            orders.append(
                {
                    "symbol": symbol,
                    "notional": f"{notional * sleeve:.2f}",
                    "side": "buy",
                    "type": "market",
                    "time_in_force": "day",
                    "client_order_id": f"tsip-course-example-{as_of}-{symbol}",  # unique per day: the broker rejects repeats
                }
            )
    return orders


def send(orders: list[dict], url: str = PAPER_URL, opener=urllib.request.urlopen) -> list[dict]:
    if url != PAPER_URL:
        raise ValueError("Only Alpaca's paper trading endpoint is accepted")
    key, secret = os.environ.get("ALPACA_API_KEY_ID"), os.environ.get("ALPACA_API_SECRET_KEY")
    if not key or not secret:
        raise SystemExit("Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY of a paper account")
    replies = []
    for order in orders:
        req = urllib.request.Request(
            url,
            data=json.dumps(order).encode(),
            headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret, "Content-Type": "application/json"},
            method="POST",
        )
        with opener(req, timeout=30) as resp:
            replies.append(json.loads(resp.read()))
    return replies


def latest_probabilities(store: Path | None = None, feature_set: str = "LECTURE+TIME+SPACE") -> tuple[dict, str]:
    """Probability of a positive next 5 rows on the last row of each fund, from the model fitted on training only."""
    from tsip.capstone import data, evaluate, features
    from tsip.capstone import models as M

    frame, _ = data.load("file", store)
    feats, sets = features.build_features(frame)
    train = M.split(feats, 5)["train"]
    last = feats.sort_values("date").groupby("ticker").tail(1)
    _, _, _, p = evaluate.fit_score(feats, sets, feature_set, train, last, 5)
    return dict(zip(last["ticker"], p.tolist(), strict=True)), str(last["date"].max().date())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", type=Path, default=None)
    parser.add_argument("--notional", type=float, default=1000.0)
    parser.add_argument("--send", action="store_true", help="submit to the paper endpoint (simulated money)")
    args = parser.parse_args(argv)
    from tsip.capstone import evaluate

    choices = json.loads(evaluate.CHOICES.read_text())
    threshold = choices["chosen"]["LECTURE+TIME+SPACE"]["sim1"]["threshold"]
    latest, as_of = latest_probabilities(args.store)
    orders = build_orders(latest, threshold, args.notional, sleeve=1 / 5, as_of=as_of)
    print(json.dumps({"as_of": as_of, "threshold": threshold, "probabilities": latest, "orders": orders}, indent=2))
    print("Educational paper-trading example; the strategy did not beat buy and hold out of sample.")
    if args.send and orders:
        print(json.dumps(send(orders), indent=2))


if __name__ == "__main__":
    main()
