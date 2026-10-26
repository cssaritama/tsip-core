"""Instrument registry.

Index levels, ETF prices and futures prices are different instruments with
different units. They are never interchanged: every statistic in a report is
labelled with the instrument it was computed on.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Instrument:
    code: str
    name: str
    kind: str  # index | etf | future | crypto
    unit: str
    timezone: str  # timezone in which the instrument's sessions are defined
    calendar: str  # exchange calendar code, or "24/7"
    family: str  # economic exposure the instrument belongs to

    def to_dict(self) -> dict:
        return asdict(self)


_REGISTRY = {
    "SPX": Instrument("SPX", "S&P 500 Index", "index", "index points", "America/New_York", "XNYS", "S&P 500"),
    "SPY": Instrument("SPY", "SPDR S&P 500 ETF Trust", "etf", "USD per share", "America/New_York", "XNYS", "S&P 500"),
    "ES": Instrument(
        "ES", "E-mini S&P 500 futures", "future", "index points", "America/Chicago", "CME Globex", "S&P 500"
    ),
    "NDX": Instrument("NDX", "Nasdaq-100 Index", "index", "index points", "America/New_York", "XNYS", "Nasdaq-100"),
    "QQQ": Instrument("QQQ", "Invesco QQQ Trust", "etf", "USD per share", "America/New_York", "XNYS", "Nasdaq-100"),
    "NQ": Instrument(
        "NQ", "E-mini Nasdaq-100 futures", "future", "index points", "America/Chicago", "CME Globex", "Nasdaq-100"
    ),
    "BTC-USD": Instrument("BTC-USD", "Bitcoin / US dollar", "crypto", "USD per BTC", "UTC", "24/7", "Bitcoin"),
    "BTC-USDT": Instrument("BTC-USDT", "Bitcoin / Tether", "crypto", "USDT per BTC", "UTC", "24/7", "Bitcoin"),
}


def get_instrument(code: str) -> Instrument:
    try:
        return _REGISTRY[code.upper()]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"Unknown instrument {code!r}; known: {sorted(_REGISTRY)}") from exc


def all_instruments() -> list[Instrument]:
    return list(_REGISTRY.values())
