"""Build the public report from cached bars."""

from __future__ import annotations

import hashlib
import json
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from tsip import __version__
from tsip.evidence.grading import GRADE_LABELS, RULES_VERSION, finalize_grades
from tsip.frames import daily_from_intraday_utc, rth_daily_from_intraday
from tsip.instruments import get_instrument
from tsip.report.headlines import headline
from tsip.report.publish import assert_publishable
from tsip.studies import calendar, entry_timing, first_passage, intraday, level_map, level_memory
from tsip.studies.common import StudyContext

SCHEMA = "tsip.report/1"
SECTIONS = [
    ("now", "Where we are now", ("map",)),
    ("levels", "Level memory", ("levels",)),
    ("sessions", "Sessions and intraday", ("sessions", "intraday")),
    ("weekly", "Weekly structure", ("weekly",)),
    ("paths", "Paths and entries", ("paths", "entries")),
    ("calendar", "Calendar", ("calendar",)),
]
STUDIES = (level_map, level_memory, intraday, first_passage, entry_timing, calendar)


@dataclass
class InstrumentInput:
    code: str
    session_model: str  # crypto | us_rth
    daily: pd.DataFrame | None = None
    intraday: pd.DataFrame | None = None
    sources: list[dict] = field(default_factory=list)
    quality: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    open_from: str | None = None  # long daily histories: first day with genuine opens


def _coverage(frame: pd.DataFrame | None) -> dict | None:
    if frame is None or len(frame) == 0:
        return None
    return {
        "start": str(pd.Timestamp(frame.index[0]).date()),
        "end": str(pd.Timestamp(frame.index[-1]).date()),
        "rows": int(len(frame)),
        "timeframe": frame.attrs.get("timeframe"),
    }


def prepare_context(inp: InstrumentInput, *, reps: int, seed: int) -> StudyContext:
    instrument = get_instrument(inp.code)
    daily, rth_bars = inp.daily, None
    if inp.intraday is not None and len(inp.intraday):
        if inp.session_model == "crypto":
            daily = daily_from_intraday_utc(inp.intraday, bars_per_day=24)
        else:
            daily, rth = rth_daily_from_intraday(inp.intraday)
            full_days = daily.index[daily["full_day"]]
            rth_bars = rth[rth["date"].isin(full_days)]
    return StudyContext(
        instrument=instrument,
        daily=daily,
        session_model=inp.session_model,
        intraday=inp.intraday if inp.session_model == "crypto" else None,
        rth_bars=rth_bars,
        reps=reps,
        seed=seed,
        open_reliable_from=pd.Timestamp(inp.open_from) if inp.open_from else None,
    )


def _instrument_report(inp: InstrumentInput, *, reps: int, seed: int) -> dict:
    instrument = get_instrument(inp.code)
    base = {"code": instrument.code, "instrument": instrument.to_dict(), "sources": inp.sources, "notes": inp.notes}
    if (inp.daily is None or len(inp.daily) == 0) and (inp.intraday is None or len(inp.intraday) == 0):
        return {
            **base,
            "status": "unavailable",
            "message": "No market data available for this instrument in this build.",
        }
    ctx = prepare_context(inp, reps=reps, seed=seed)
    cards = []
    skipped = []
    for study in STUDIES:
        name = study.__name__.rsplit(".", 1)[-1]
        try:
            cards.extend(study.run(ctx))
        except Exception as exc:  # one failing study must not take the whole report down
            print(f"[{instrument.code}] study {name} failed:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            skipped.append({"study": name, "reason": type(exc).__name__})
    grading = finalize_grades(cards)
    for card in cards:
        card.headline = headline(card)
    sections = []
    for key, title, families in SECTIONS:
        members = [c.to_dict() for c in cards if c.family in families]
        if members:
            sections.append({"id": key, "title": title, "cards": members})
    counts = {g: 0 for g in GRADE_LABELS["edge"]}
    for card in cards:
        for item in card.items:
            counts[item.grade] = counts.get(item.grade, 0) + 1
    return {
        **base,
        "status": "ok",
        "coverage": {"daily": _coverage(ctx.daily), "intraday": _coverage(inp.intraday)},
        "quality": inp.quality,
        "grading": grading,
        "grade_counts": counts,
        "sections": sections,
        "skipped_studies": skipped,
    }


def load_hypotheses(path: str | Path | None) -> list[dict]:
    if path is None or not Path(path).exists():
        return []
    entries = json.loads(Path(path).read_text())
    for entry in entries:
        canonical = json.dumps({k: v for k, v in entry.items() if k != "sha256"}, sort_keys=True, separators=(",", ":"))
        entry["sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    return entries


def build_report(
    inputs: list[InstrumentInput],
    *,
    reps: int = 1000,
    seed: int = 20261026,
    hypotheses_path: str | Path | None = None,
) -> dict:
    instruments = []
    for inp in inputs:
        try:
            instruments.append(_instrument_report(inp, reps=reps, seed=seed))
        except Exception as exc:
            print(f"[{inp.code}] report failed:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            instruments.append(
                {
                    "code": inp.code,
                    "instrument": get_instrument(inp.code).to_dict(),
                    "sources": inp.sources,
                    "notes": inp.notes,
                    "status": "unavailable",
                    "message": f"This build could not compute the statistics ({type(exc).__name__}).",
                }
            )
    report = {
        "schema": SCHEMA,
        "version": __version__,
        "rules_version": RULES_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "settings": {"bootstrap_replicates": reps, "seed": seed, "holdout_fraction": 0.3},
        "grade_labels": GRADE_LABELS,
        "instruments": instruments,
        "hypotheses": load_hypotheses(hypotheses_path),
    }
    assert_publishable(report)
    return report
