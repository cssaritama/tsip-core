"""Private, fail-closed EOD data import and exchange-session quality checks.

The parsers preserve vendor OHLCV; they never replace OHLC with adjusted close,
invent actions, forward-fill a missing session, or confer market-data rights.
The XNYS schedule is a common-US-equity RTH calendar proxy for SPY and QQQ,
not a claim that both ETFs are listed on NYSE. Provider-specific corrections
and corporate-action completeness still need independent reconciliation.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd

PRICE_COLUMNS = ["open", "high", "low", "close"]
REQUIRED_COLUMNS = PRICE_COLUMNS + ["volume"]
ACTION_COLUMNS = ["dividend_amount", "split_coefficient"]
OPTIONAL_COLUMNS = ["adjusted_close", *ACTION_COLUMNS, "adjusted_open",
                    "adjusted_high", "adjusted_low", "adjusted_volume"]
PROVIDERS = {"canonical", "alpha_vantage", "tiingo", "historicaldata"}
ALIASES = {
    "timestamp": "date", "adj close": "adjusted_close",
    "adjusted close": "adjusted_close", "adjclose": "adjusted_close",
    "divcash": "dividend_amount", "splitfactor": "split_coefficient",
    "adjopen": "adjusted_open", "adjhigh": "adjusted_high",
    "adjlow": "adjusted_low", "adjvolume": "adjusted_volume",
    "adj_open": "adjusted_open", "adj_high": "adjusted_high",
    "adj_low": "adjusted_low", "adj_close": "adjusted_close", "adj_volume": "adjusted_volume",
}


def _symbol(symbol: str) -> str:
    if symbol not in {"SPY", "QQQ"}:
        raise ValueError("R8.1 EOD import accepts SPY or QQQ ETF symbols only")
    return symbol


def _column(name: str) -> str:
    name = name.strip().lower()
    return ALIASES.get(name, name)


def _session_dates(values: pd.Series, provider: str) -> pd.DatetimeIndex:
    # A daily date is a session label, not an instant to convert to local time.
    strings = values.astype(str)
    pattern = r"\d{4}-\d{2}-\d{2}"
    if provider == "tiingo":
        # Tiingo labels EOD dates with midnight UTC, which must NOT shift to
        # the previous NY date. Reject non-midnight records as intraday input.
        pattern += r"(?:(?:T| )00:00:00(?:\.0+)?(?:Z|\+00:00)?)?"
    if not strings.str.fullmatch(pattern).all():
        raise ValueError("Daily dates must be ISO YYYY-MM-DD session labels; no ambiguous dates/times")
    result = pd.DatetimeIndex(pd.to_datetime(strings.str[:10], format="%Y-%m-%d", errors="raise"))
    if result.isna().any() or result.duplicated().any():
        raise ValueError("Session dates must be non-null and unique")
    return result


def _normalize(frame: pd.DataFrame, symbol: str, provider: str) -> pd.DataFrame:
    _symbol(symbol)
    if provider not in PROVIDERS:
        raise ValueError(f"Unsupported provider; choose {sorted(PROVIDERS)}")
    columns = [_column(str(c)) for c in frame.columns]
    if len(columns) != len(set(columns)):
        raise ValueError("Duplicate/aliased CSV column names")
    frame = frame.copy()
    frame.columns = columns
    if provider == "historicaldata":
        if not {"dividend", "split", "dividend_type"}.issubset(frame):
            raise ValueError("HistoricalData source requires explicit dividend/split event columns")
        if frame.dividend_type.fillna("").astype(str).str.contains("CUR:|ADJ:UNKNOWN", regex=True).any():
            raise ValueError("Foreign-currency/unknown adjustments require separate reconciliation")
        # Documented sentinels: blank means no event, not a reported zero
        # distribution or a reported 1:1 split. Preserve event-presence flags.
        frame["dividend_event_reported"] = frame.dividend.notna()
        frame["split_event_reported"] = frame.split.notna()
        frame["dividend_amount"] = pd.to_numeric(frame.dividend, errors="raise").fillna(0.0)
        def historical_split(value):
            if pd.isna(value) or value == "":
                return 1.0
            ratio = 1.0
            for part in str(value).split("+"):
                if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?:[0-9]+(?:\.[0-9]+)?", part):
                    raise ValueError("Invalid HistoricalData from:to split ratio")
                old, new = map(float, part.split(":"))
                if old <= 0 or new <= 0:
                    raise ValueError("Split ratio terms must be positive")
                ratio *= new / old
            return ratio
        frame["split_coefficient"] = frame.split.map(historical_split)
    if "symbol" in frame and not frame.symbol.astype(str).eq(symbol).all():
        raise ValueError("Mixed symbols or requested symbol does not match the input")
    if "date" not in frame or not set(REQUIRED_COLUMNS).issubset(frame):
        raise ValueError("Real EOD input requires date, open, high, low, close, volume")
    if not len(frame):
        raise ValueError("Empty market-data input")
    frame.index = _session_dates(frame.pop("date"), provider)
    frame.index.name = "date"
    frame = frame[[c for c in REQUIRED_COLUMNS + OPTIONAL_COLUMNS +
                   ["dividend_event_reported", "split_event_reported"] if c in frame]].sort_index()
    validate_numeric_bars(frame)
    frame.attrs.update(symbol=symbol, provider=provider, synthetic=False,
                       ohlcv_adjustment="vendor_supplied_not_inferred")
    if provider == "historicaldata":
        frame.attrs.update(ohlcv_adjustment="raw", volume_session_basis="whole_day_including_extended_hours",
                           ohlc_session_basis="regular", action_blank_policy="no event; arithmetic sentinels 0/1",
                           adjustment_method="backward_discount_prev_close")
    return frame


def load_vendor_csv(path: str | Path, symbol: str, provider: str = "canonical") -> pd.DataFrame:
    """Read canonical, Alpha Vantage daily-adjusted, or Tiingo EOD CSV.

    Optional actions stay absent when the source omitted them. Caller must
    separately record the vendor's raw/split-adjusted/total-return policy.
    """
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        header = next(csv.reader(handle), [])
    normalized = [_column(c) for c in header]
    if len(normalized) != len(set(normalized)):
        raise ValueError("Duplicate/aliased CSV column names")
    return _normalize(pd.read_csv(path, dtype={"date": str, "timestamp": str}), symbol, provider)


def load_vendor_json(path: str | Path, symbol: str, provider: str) -> pd.DataFrame:
    """Read a local Tiingo EOD response or Alpha Vantage daily JSON response."""
    obj = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if provider == "tiingo":
        if not isinstance(obj, list) or not obj or not all(isinstance(r, dict) for r in obj):
            raise ValueError("Expected non-empty Tiingo EOD list, not API error/metadata")
        return _normalize(pd.DataFrame(obj), symbol, provider)
    if provider == "alpha_vantage":
        if not isinstance(obj, dict) or "Time Series (Daily)" not in obj:
            raise ValueError("Expected Alpha Vantage daily bars, not API error/limit response")
        metadata = obj.get("Meta Data", {})
        if metadata.get("2. Symbol", symbol) != symbol:
            raise ValueError("Alpha Vantage response symbol mismatch")
        rows = []
        for date, bar in obj["Time Series (Daily)"].items():
            row = {"date": date}
            for key, value in bar.items():
                clean = re.sub(r"^\d+\.\s*", "", key).replace(" ", "_")
                row[clean] = value
            rows.append(row)
        return _normalize(pd.DataFrame(rows), symbol, provider)
    raise ValueError("JSON parser supports alpha_vantage or tiingo")


def load_kibot_daily(path: str | Path, symbol: str) -> pd.DataFrame:
    """Parse headerless daily bars; caller must know the requested adjustment mode."""
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows or any(len(row) != 6 for row in rows):
        raise ValueError("Expected six-column Kibot daily bars, not an API error response")
    frame = pd.DataFrame(rows, columns=["date", *REQUIRED_COLUMNS])
    if not frame.date.str.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}").all():
        raise ValueError("Expected Kibot daily MM/DD/YYYY dates")
    frame["date"] = pd.to_datetime(frame.date, format="%m/%d/%Y", errors="raise").dt.strftime("%Y-%m-%d")
    result = _normalize(frame, symbol, "canonical")
    result.attrs["provider"] = "kibot"
    return result


def load_kibot_bundle(raw_path: str | Path, adjusted_path: str | Path | None = None,
                      actions_path: str | Path | None = None, symbol: str = "SPY", *,
                      actions_coverage_confirmed: bool = False) -> pd.DataFrame:
    """Join explicit unadjusted, adjusted and optional entitled actions files.

    Raw must have been requested with unadjusted=1; adjusted must use the
    provider's fully adjusted mode. Without an actions response, action columns
    remain ABSENT. An error or missing response never means zero dividends.
    actions_coverage_confirmed refers to the request scope, not independent
    verification of the vendor history. Queries must cover processing dates
    through retrieval, since events are joined by EventDate (the ex-date).
    """
    result = load_kibot_daily(raw_path, symbol)
    hashes = {"raw": hashlib.sha256(Path(raw_path).read_bytes()).hexdigest()}
    if adjusted_path is not None:
        adjusted = load_kibot_daily(adjusted_path, symbol)
        if not result.index.equals(adjusted.index):
            raise ValueError("Raw/adjusted Kibot session coverage mismatch; no inner-join data loss allowed")
        for column in REQUIRED_COLUMNS:
            result[f"adjusted_{column}"] = adjusted[column]
        hashes["adjusted"] = hashlib.sha256(Path(adjusted_path).read_bytes()).hexdigest()
    if actions_path is not None:
        if not actions_coverage_confirmed:
            raise ValueError("Confirm the actions request covers processing dates through retrieval")
        actions = pd.read_csv(actions_path, sep="\t", dtype=str)
        if list(actions.columns) != ["Date", "Symbol", "Company", "Action", "Description", "EventDate"]:
            raise ValueError("Expected entitled Kibot adjustments TSV, not error/limit response")
        if actions.isna().any().any() or actions.duplicated().any():
            raise ValueError("Null or duplicate action records cannot be silently repaired")
        if not actions.Symbol.eq(symbol).all():
            raise ValueError("Mixed symbols or Kibot action symbol mismatch")
        for field in ("Date", "EventDate"):
            if not actions[field].str.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}").all():
                raise ValueError("Kibot action dates must be MM/DD/YYYY")
            actions[field] = pd.to_datetime(actions[field], format="%m/%d/%Y", errors="raise")
        result["dividend_amount"] = 0.0
        result["split_coefficient"] = 1.0
        result["dividend_event_reported"] = False
        result["split_event_reported"] = False
        for _, action in actions.iterrows():
            date = action.EventDate  # Never use provider processing Date here.
            if action.Description == "Dividend":
                cash = float(action.Action)
                if not np.isfinite(cash) or cash < 0:
                    raise ValueError("Invalid dividend amount")
                column, value = "dividend_amount", cash
            elif action.Description in {"Split", "Reverse Split"}:
                if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?-[0-9]+(?:\.[0-9]+)?", action.Action):
                    raise ValueError("Invalid Kibot new-old split ratio")
                new, old = map(float, action.Action.split("-"))
                if old <= 0 or new <= 0:
                    raise ValueError("Split ratio terms must be positive")
                column, value = "split_coefficient", new / old
            else:
                raise ValueError(f"Unsupported corporate action {action.Description!r}")
            if result.index.min() <= date <= result.index.max():
                if date not in result.index:
                    raise ValueError("Corporate action falls on missing/off-calendar price row")
                if column == "dividend_amount":
                    result.loc[date, column] += value
                    result.loc[date, "dividend_event_reported"] = True
                else:
                    result.loc[date, column] *= value
                    result.loc[date, "split_event_reported"] = True
        hashes["actions"] = hashlib.sha256(Path(actions_path).read_bytes()).hexdigest()
    validate_numeric_bars(result)
    result.attrs.update(provider="kibot", ohlcv_adjustment="raw", ohlc_session_basis="regular",
                        volume_session_basis="provider_daily_definition_requires_verification",
                        corporate_actions_supplied=actions_path is not None,
                        source_sha256=hashes, synthetic=False)
    return result


def validate_numeric_bars(frame: pd.DataFrame) -> None:
    """Validate without repairing prices, malformed volume or action columns."""
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is not None:
        raise ValueError("Expected timezone-naive DatetimeIndex of session dates")
    if frame.index.isna().any() or frame.index.duplicated().any() or not frame.index.is_monotonic_increasing:
        raise ValueError("Session index must be non-null, unique and sorted")
    if not frame.index.equals(frame.index.normalize()):
        raise ValueError("Session index must contain dates at midnight only")
    if not len(frame) or not set(REQUIRED_COLUMNS).issubset(frame):
        raise ValueError("Non-empty OHLCV columns required")
    for name in [c for c in REQUIRED_COLUMNS + OPTIONAL_COLUMNS if c in frame]:
        values = pd.to_numeric(frame[name], errors="raise")
        if not np.isfinite(values.to_numpy(dtype=float)).all():
            raise ValueError(f"{name} must contain finite non-null values")
        frame[name] = values
    if (frame[PRICE_COLUMNS] <= 0).any().any():
        raise ValueError("OHLC prices must be positive")
    if ((frame.high < frame[["open", "close", "low"]].max(axis=1)) |
            (frame.low > frame[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("OHLC high/low must enclose open and close")
    # Do not round fractional shares; historical provider conventions can change.
    if (frame.volume < 0).any():
        raise ValueError("Raw ETF volume must be nonnegative")
    actions = [c in frame for c in ACTION_COLUMNS]
    if any(actions) and not all(actions):
        raise ValueError("Supply both dividend_amount and split_coefficient, or neither")
    if all(actions):
        if (frame.dividend_amount < 0).any() or (frame.split_coefficient <= 0).any():
            raise ValueError("Dividends must be nonnegative and split ratios strictly positive")
    for name in [c for c in OPTIONAL_COLUMNS if c.startswith("adjusted_") and c in frame]:
        if (frame[name] <= 0).any() and name != "adjusted_volume":
            raise ValueError("Adjusted prices must be positive")
        if name == "adjusted_volume" and (frame[name] < 0).any():
            raise ValueError("Adjusted volume must be nonnegative")
    adjusted_ohlc = [f"adjusted_{c}" for c in PRICE_COLUMNS]
    if all(c in frame for c in adjusted_ohlc):
        if ((frame.adjusted_high < frame[["adjusted_open", "adjusted_close", "adjusted_low"]].max(axis=1)) |
                (frame.adjusted_low > frame[["adjusted_open", "adjusted_close", "adjusted_high"]].min(axis=1))).any():
            raise ValueError("Adjusted OHLC high/low enclosure failed")


def session_schedule(start: str | pd.Timestamp, end: str | pd.Timestamp) -> pd.DataFrame:
    """Pinned exchange_calendars XNYS regular cash session open/close in UTC."""
    import exchange_calendars as xcals

    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if start.tz is not None or end.tz is not None or start != start.normalize() or end != end.normalize():
        raise ValueError("Calendar bounds must be timezone-naive session dates")
    if start > end:
        raise ValueError("Calendar start must not follow end")
    # Padding also permits a requested window containing only closed days.
    cal = xcals.get_calendar("XNYS", start=start - pd.Timedelta(days=10), end=end + pd.Timedelta(days=10))
    schedule = cal.schedule.loc[str(start.date()):str(end.date())].copy()
    schedule.index = pd.DatetimeIndex(schedule.index).tz_localize(None)
    schedule.index.name = "date"
    for name in ("open", "close"):
        schedule[name] = pd.to_datetime(schedule[name], utc=True)
    return schedule[["open", "close"]]


def audit_market_data(frame: pd.DataFrame, symbol: str, *, start: str | None = None,
                      end: str | None = None, as_of: str | None = None,
                      ohlcv_adjustment: str = "unknown") -> dict:
    """Audit complete requested window; missing boundaries require start/end.

    A PASS validates structure and calendar only. It does not establish vendor
    accuracy, license rights or corporate-action completeness. No rows are
    dropped and no prices are transformed by this function.
    """
    _symbol(symbol)
    frame = frame.copy()
    validate_numeric_bars(frame)
    if ohlcv_adjustment not in {"raw", "split_adjusted", "split_dividend_adjusted", "unknown"}:
        raise ValueError("Unknown ohlcv_adjustment policy")
    first = pd.Timestamp(start) if start else frame.index.min()
    last = pd.Timestamp(end) if end else frame.index.max()
    schedule = session_schedule(first, last)
    expected = schedule.index
    missing = expected.difference(frame.index)
    unexpected = frame.index.difference(expected)
    errors, warnings = [], []
    if len(missing):
        errors.append("MISSING_TRADING_SESSIONS")
    if len(unexpected):
        errors.append("OFF_CALENDAR_OR_OUT_OF_WINDOW_ROWS")
    incomplete = []
    if as_of is not None:
        instant = pd.Timestamp(as_of)
        if instant.tz is None:
            raise ValueError("as_of must have an explicit UTC offset/timezone")
        incomplete = [str(d.date()) for d in frame.index.intersection(expected)
                      if schedule.loc[d, "close"] > instant]
        if incomplete:
            errors.append("NOT_YET_COMPLETED_SESSIONS")
    else:
        warnings.append("NO_AS_OF_COMPLETENESS_CHECK")
    if start is None or end is None:
        warnings.append("COVERAGE_BOUNDS_INFERRED_FROM_OBSERVED_ROWS")
    if (frame.volume == 0).any():
        warnings.append("ZERO_VOLUME_REQUIRES_PROVIDER_REVIEW")
    actions_present = set(ACTION_COLUMNS).issubset(frame)
    action_report = {"columns_present": actions_present, "independently_verified": False,
                     "dividend_event_count": None, "split_events": [],
                     "adjusted_close_present": "adjusted_close" in frame,
                     "adjusted_return_reconciliation": None}
    if actions_present:
        action_report["dividend_event_count"] = int((frame.dividend_amount > 0).sum())
        action_report["split_events"] = [
            {"date": str(day.date()), "new_shares_per_old_share": float(row.split_coefficient)}
            for day, row in frame[frame.split_coefficient.ne(1)].iterrows()
        ]
        if action_report["split_events"]:
            warnings.append("SPLITS_REQUIRE_COORDINATE_ADJUSTMENT_BEFORE_CROSS_DATE_BARRIER_STUDIES")
        if "adjusted_close" in frame and ohlcv_adjustment == "raw":
            # Diagnostic, NOT exact equivalence: vendor backward dividend
            # discounting can differ from reinvesting distributions at ex-close.
            gross_actions = frame.split_coefficient * (frame.close + frame.dividend_amount) / frame.close.shift(1)
            gross_adjusted = frame.adjusted_close / frame.adjusted_close.shift(1)
            delta = (gross_adjusted - gross_actions).abs().dropna() * 10000
            action_report["adjusted_return_reconciliation"] = {
                "method": "raw close + ex-date cash, splits first, reinvestment at ex-close",
                "n_comparable_returns": len(delta),
                "max_absolute_difference_bps": float(delta.max()) if len(delta) else None,
                "n_differences_over_10_bps": int((delta > 10).sum()),
                "exact_equivalence_expected": False,
                "note": "Vendor adjustment convention and action completeness require separate verification.",
            }
            if (delta > 10).any():
                warnings.append("ADJUSTED_RETURN_DIFFERENCE_REQUIRES_RECONCILIATION")
    else:
        warnings.append("CORPORATE_ACTIONS_ABSENT_TOTAL_RETURN_UNVERIFIED")
    if ohlcv_adjustment == "unknown":
        warnings.append("OHLC_ADJUSTMENT_POLICY_UNVERIFIED")
    large_moves = frame.close.pct_change(fill_method=None).abs() > 0.4
    if large_moves.any():
        warnings.append("LARGE_RAW_CLOSE_MOVE_REQUIRES_PROVIDER_REVIEW")
    local_close = schedule.close.dt.tz_convert("America/New_York")
    early = schedule.index[(local_close.dt.hour < 16).to_numpy()]
    return {
        "schema_version": "tsip.market_data_quality.v1", "symbol": symbol,
        "synthetic": False, "status": "BLOCKED" if errors else "PASS",
        "scope": "structural/calendar QA only; independent price/action/licensing reconciliation required",
        "rows": len(frame), "observed_start": str(frame.index.min().date()),
        "observed_end": str(frame.index.max().date()),
        "requested_start": str(first.date()), "requested_end": str(last.date()),
        "expected_sessions": len(expected),
        "missing_sessions": [str(d.date()) for d in missing],
        "unexpected_sessions": [str(d.date()) for d in unexpected],
        "incomplete_as_of_sessions": incomplete, "as_of": as_of,
        "calendar": "XNYS", "calendar_basis": "common US-equity regular-session proxy for SPY/QQQ",
        "calendar_library_version": importlib.metadata.version("exchange_calendars"),
        "timezone": "America/New_York", "early_close_sessions": [str(d.date()) for d in early],
        "ohlcv_adjustment": ohlcv_adjustment, "corporate_actions": action_report,
        "volume_session_basis": frame.attrs.get("volume_session_basis", "not_declared"),
        "corporate_actions_verified": False,
        "errors": errors, "warnings": warnings, "publication_allowed": False,
    }


def validate_provenance(metadata: dict, symbol: str) -> dict:
    """Validate an operator declaration, without claiming legal verification."""
    required = ["provider", "source_url", "retrieved_at", "symbol", "currency", "timezone",
                "session_kind", "ohlcv_adjustment", "research_use_status", "research_authorization_ref"]
    if any(not isinstance(metadata.get(k), str) or not metadata[k].strip() for k in required):
        raise ValueError("Provenance requires non-empty strings: " + ", ".join(required))
    if metadata["symbol"] != _symbol(symbol) or metadata["currency"] != "USD":
        raise ValueError("Provenance instrument/currency mismatch")
    if metadata["timezone"] != "America/New_York" or metadata["session_kind"] != "regular":
        raise ValueError("SPY/QQQ EOD contract requires America/New_York regular sessions")
    if metadata["ohlcv_adjustment"] not in {"raw", "split_adjusted", "split_dividend_adjusted", "unknown"}:
        raise ValueError("Unsupported ohlcv_adjustment")
    retrieved = pd.Timestamp(metadata["retrieved_at"])
    if retrieved.tz is None:
        raise ValueError("retrieved_at requires timezone")
    url = urlparse(metadata["source_url"])
    if url.scheme != "https" or not url.netloc or url.username or url.password:
        raise ValueError("Use a public HTTPS source reference without credentials")
    sensitive = {"apikey", "api_key", "token", "key", "access_token", "password", "secret"}
    if sensitive.intersection(k.lower() for k in parse_qs(url.query)):
        raise ValueError("Never persist credentials or API keys in source_url")
    if metadata["research_use_status"] not in {"authorized", "unresolved", "prohibited"}:
        raise ValueError("research_use_status must be authorized/unresolved/prohibited")
    result = dict(metadata)
    result.update(synthetic=False, publication_allowed=False,
                  rights_check="operator_declared; software does not verify or create license rights")
    return result


def import_private_dataset(source: str | Path, out_dir: str | Path, *, symbol: str,
                           provider: str, metadata: dict, start: str | None = None,
                           end: str | None = None, audit_only: bool = False) -> dict:
    """Import local authorized data, writing quality/provenance beside CSV.

    The data is never copied into this public repository. Caller must place
    out_dir in a private, access-controlled store outside version control.
    Unresolved rights permit an audit report only, never normalized export.
    """
    source, out_dir = Path(source), Path(out_dir).resolve()
    public_repo = Path(__file__).resolve().parents[2]
    if out_dir == public_repo or public_repo in out_dir.parents:
        raise ValueError("Real-data output must stay outside public-repo")
    provenance = validate_provenance(metadata, symbol)
    if not audit_only and provenance["research_use_status"] != "authorized":
        raise ValueError("Normalized export blocked: research rights unresolved/prohibited")
    frame = (load_vendor_json(source, symbol, provider) if source.suffix.lower() == ".json"
             else load_vendor_csv(source, symbol, provider))
    report = audit_market_data(frame, symbol, start=start, end=end,
                               as_of=provenance["retrieved_at"],
                               ohlcv_adjustment=provenance["ohlcv_adjustment"])
    provenance["raw_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    provenance["raw_filename"] = source.name
    provenance["quality_status"] = report["status"]
    provenance["normalized_exported"] = not audit_only and report["status"] == "PASS"
    out_dir.mkdir(parents=True, exist_ok=True)
    if provenance["normalized_exported"]:
        text = frame.to_csv(index=True, date_format="%Y-%m-%d", lineterminator="\n")
        blob = text.encode("utf-8")
        provenance["normalized_sha256"] = hashlib.sha256(blob).hexdigest()
        (out_dir / f"{symbol}_normalized.csv").write_bytes(blob)
    for name, value in [("quality", report), ("provenance", provenance)]:
        (out_dir / f"{symbol}_{name}.json").write_text(
            json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return {"quality": report, "provenance": provenance}
