"""Course broker example: orders are built from the frozen threshold and go only to the paper endpoint."""

import json

import pytest

from tsip.capstone import paper_order as P


def test_orders_only_for_funds_above_the_threshold():
    orders = P.build_orders({"SPY": 0.6, "QQQ": 0.4, "GLD": 0.55, "BTC-USD": 0.9}, 0.5, 1000, 0.2)
    assert [o["symbol"] for o in orders] == ["SPY", "GLD"]  # crypto is not part of this example
    assert orders[0]["notional"] == "200.00" and orders[0]["side"] == "buy"


def test_only_the_paper_endpoint_is_accepted(monkeypatch):
    with pytest.raises(ValueError):
        P.send([{"symbol": "SPY"}], url="https://api.alpaca.markets/v2/orders")


def test_send_needs_paper_keys(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_API_SECRET_KEY", raising=False)
    with pytest.raises(SystemExit):
        P.send([{"symbol": "SPY"}])


def test_send_posts_each_order_with_the_keys(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY_ID", "k")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "s")
    seen = []

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"status": "accepted"}'

    def opener(req, timeout):
        seen.append((req.full_url, req.get_header("Apca-api-key-id"), json.loads(req.data)))
        return Reply()

    replies = P.send([{"symbol": "SPY"}, {"symbol": "GLD"}], opener=opener)
    assert replies == [{"status": "accepted"}] * 2
    assert seen[0][0] == P.PAPER_URL and seen[0][1] == "k" and seen[1][2]["symbol"] == "GLD"
