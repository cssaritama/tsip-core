import gzip
import json

from tsip.cli import main
from tsip.report.archive import archive_report, verify_archive


def _report(tmp_path, when="2026-11-03T21:56:10+00:00"):
    path = tmp_path / f"report-{when[:10]}.json"
    path.write_text(
        json.dumps(
            {
                "generated_at": when,
                "version": "0.2.11",
                "rules_version": "2026.10.1",
                "data_status": {"overall": "fresh"},
            }
        )
    )
    return path


def test_archive_is_idempotent_and_verifiable(tmp_path):
    archive = tmp_path / "archive"
    first = archive_report(_report(tmp_path), archive)
    again = archive_report(_report(tmp_path), archive)
    assert first["added"] and not again["added"]
    stored = archive / first["path"]
    assert json.loads(gzip.decompress(stored.read_bytes()))["version"] == "0.2.11"
    assert verify_archive(archive) == []
    lines = (archive / "index.csv").read_text().strip().splitlines()
    assert len(lines) == 2 and "fresh" in lines[1]


def test_tampering_is_detected(tmp_path):
    archive = tmp_path / "archive"
    result = archive_report(_report(tmp_path), archive)
    (archive / result["path"]).write_bytes(gzip.compress(b'{"changed": true}'))
    assert verify_archive(archive) == [result["path"]]


def test_archive_command(tmp_path):
    archive = tmp_path / "archive"
    assert main(["archive", "--report", str(_report(tmp_path)), "--dir", str(archive)]) == 0
    assert (
        main(["archive", "--report", str(_report(tmp_path, "2026-11-04T06:30:00+00:00")), "--dir", str(archive)]) == 0
    )
    assert len((archive / "index.csv").read_text().strip().splitlines()) == 3


def test_verify_only(tmp_path):
    archive = tmp_path / "archive"
    archive_report(_report(tmp_path), archive)
    assert main(["archive", "--dir", str(archive), "--verify-only"]) == 0
