"""Minimal HTTP client with retries, used by the market data connectors.

The standard library is used deliberately so that the core package has no
dependency beyond pandas and numpy.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from tsip import __version__

USER_AGENT = f"tsip/{__version__} (+https://github.com/cssaritama/tsip-core)"
RETRYABLE = {429, 500, 502, 503, 504}


class HTTPError(RuntimeError):
    def __init__(self, status: int, url: str, body: str = ""):
        super().__init__(f"HTTP {status} for {url}: {body[:200]}")
        self.status = status
        self.url = url
        self.body = body


def build_url(base: str, params: dict[str, Any] | None = None) -> str:
    if not params:
        return base
    clean = {k: v for k, v in params.items() if v is not None}
    return f"{base}?{urllib.parse.urlencode(clean)}"


def get_bytes(
    url: str,
    headers: dict[str, str] | None = None,
    *,
    timeout: float = 30.0,
    retries: int = 5,
    backoff: float = 1.5,
) -> bytes:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    request_headers.update(headers or {})
    attempt = 0
    while True:
        attempt += 1
        req = urllib.request.Request(url, headers=request_headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - https only
                return resp.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace") if exc.fp else ""
            if exc.code in RETRYABLE and attempt <= retries:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                delay = float(retry_after) if retry_after and retry_after.isdigit() else backoff**attempt
                time.sleep(min(delay, 60.0))
                continue
            raise HTTPError(exc.code, url, body) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt <= retries:
                time.sleep(min(backoff**attempt, 60.0))
                continue
            raise HTTPError(0, url, str(exc)) from exc


def get_json(url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> Any:
    raw = get_bytes(url, {"Accept": "application/json", **(headers or {})}, **kwargs)
    return json.loads(raw.decode("utf-8"))
