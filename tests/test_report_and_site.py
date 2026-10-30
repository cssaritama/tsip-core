import json

import numpy as np
import pandas as pd
import pytest

from tsip.data.schema import make_bars
from tsip.report import InstrumentInput, PublicationError, assert_publishable, build_report
from tsip.site import build_site


def synthetic_hourly(days=400, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=days * 24, freq="1h", tz="UTC")
    r = rng.normal(0, 0.004, len(idx))
    close = 20000 * np.exp(np.cumsum(r))
    open_ = np.concatenate([[20000.0], close[:-1]])
    frame = pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) * 1.001,
            "low": np.minimum(open_, close) * 0.999,
            "close": close,
            "volume": 1.0,
        },
        index=idx,
    )
    return make_bars(frame, instrument="BTC-USD", source="coinbase", timeframe="1h")


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    hyp = tmp_path_factory.mktemp("reg") / "h.json"
    hyp.write_text(
        json.dumps(
            [
                {
                    "id": "H-1",
                    "statement": "s",
                    "instrument": "BTC-USD",
                    "metric": "m",
                    "criterion": "c",
                    "registered": "2026-10-26",
                    "evaluation_start": "2026-10-27",
                    "evaluation_end": "2027-01-31",
                    "status": "open",
                }
            ]
        )
    )
    inputs = [InstrumentInput("BTC-USD", "crypto", intraday=synthetic_hourly()), InstrumentInput("SPY", "us_rth")]
    return build_report(inputs, reps=100, hypotheses_path=hyp)


def test_report_structure_and_grades(report):
    btc, spy = report["instruments"]
    assert btc["status"] == "ok" and spy["status"] == "unavailable"
    cards = [c for s in btc["sections"] for c in s["cards"]]
    assert cards and all(c["grade"] in {"A", "B", "C", "D", "F", "N/A"} for c in cards)
    assert all(c["headline"] for c in cards)
    assert len(report["hypotheses"][0]["sha256"]) == 64
    json.dumps(report, allow_nan=False)  # strict JSON


def test_report_contains_no_raw_prices(report):
    assert_publishable(report)
    with pytest.raises(PublicationError):
        assert_publishable({"x": {"close": [1, 2, 3]}})
    with pytest.raises(PublicationError):
        assert_publishable({"series": list(range(1000))})


def test_site_build(tmp_path, report):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report))
    out = build_site(path, tmp_path / "dist")
    assert (out / "index.html").exists() and (out / "assets" / "app.js").exists()
    assert json.loads((out / "data" / "report.json").read_text())["schema"] == report["schema"]


def test_site_canonical_address(tmp_path, report):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report))
    out = build_site(path, tmp_path / "dist", site_url="https://example.pages.dev")
    html = (out / "index.html").read_text(encoding="utf-8")
    assert '<link rel="canonical" href="https://example.pages.dev/">' in html
    assert html.count("</head>") == 1 and "github.com/cssaritama" in html
    with pytest.raises(ValueError):
        build_site(path, tmp_path / "dist2", site_url="http://insecure.example")


def test_a_failing_study_does_not_stop_the_report(monkeypatch):
    import types

    from tsip.report import build as build_module

    def run(ctx):
        raise RuntimeError("boom")

    Broken = types.ModuleType("tsip.studies.broken")
    Broken.run = run

    monkeypatch.setattr(build_module, "STUDIES", (Broken, *build_module.STUDIES))
    idx = pd.date_range("2024-01-01", periods=24 * 120, freq="1h", tz="UTC")
    rng = np.random.default_rng(1)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.003, len(idx))))
    frame = pd.DataFrame(
        {"open": close, "high": close * 1.002, "low": close * 0.998, "close": close, "volume": 1.0}, index=idx
    )
    report = build_module.build_report([build_module.InstrumentInput("BTC-USD", "crypto", intraday=frame)], reps=50)
    inst = report["instruments"][0]
    assert inst["status"] == "ok" and inst["skipped_studies"] == [{"study": "broken", "reason": "RuntimeError"}]


def test_report_carries_data_status(report):
    status = report["data_status"]
    assert status["overall"] in {"fresh", "degraded", "stale"}
    codes = {r["code"] for r in status["instruments"]}
    assert {"BTC-USD", "SPY", "QQQ", "SPX", "NDX"} <= codes


def test_site_is_self_contained(tmp_path, report):
    import re

    path = tmp_path / "r.json"
    path.write_text(json.dumps(report))
    out = build_site(path, tmp_path / "site")
    html = (out / "index.html").read_text(encoding="utf-8")
    assets = re.findall(r'(?:src|href)="([^"#]+)"', html)
    external = [a for a in assets if a.startswith("http") and "github.com" not in a]
    assert external == []  # no third-party scripts, styles, fonts or trackers
    assert (out / "assets" / "fonts" / "instrument-sans-latin.woff2").stat().st_size > 10_000
    assert (out / "assets" / "fonts" / "OFL-instrument-sans.txt").exists()
