"""Publication guard.

The public report contains derived statistics only. Raw vendor bars must
never be redistributed, so the guard rejects any structure that looks like a
price series: OHLCV keys, or long numeric arrays.
"""

from __future__ import annotations

from typing import Any

FORBIDDEN_KEYS = {"open", "high", "low", "close", "volume", "bars", "ohlc", "ohlcv", "prices"}
MAX_NUMERIC_ARRAY = 400


class PublicationError(RuntimeError):
    pass


def assert_publishable(obj: Any, path: str = "$") -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise PublicationError(f"raw market data key {key!r} at {path}")
            assert_publishable(value, f"{path}.{key}")
    elif isinstance(obj, list):
        numeric = [v for v in obj if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if len(numeric) > MAX_NUMERIC_ARRAY:
            raise PublicationError(f"numeric array of length {len(numeric)} at {path} looks like a price series")
        for i, value in enumerate(obj):
            assert_publishable(value, f"{path}[{i}]")
