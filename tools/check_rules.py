"""Repository rules that must never be skipped (W-75; ADR 0071, ADR 0072, ADR 0073 of the private register).

Runs locally (``python tools/check_rules.py``) and in the daily review workflow. Prints a Markdown
summary (also to ``$GITHUB_STEP_SUMMARY`` when set) and exits with 1 when a rule fails.

Rules:
  1. Every hypothesis ID cited in the repository exists in ``registry/hypotheses.json``.
  2. Specification numbers are unique, and every specification is in ``specs/README.md``.
  3. No tool or assistant names in tracked text (the project is tool-independent).
  4. No promotional claims that no study can support, in public text.
  5. No data files outside ``examples/`` and ``tests/``.
  6. Commits since the given date are authored by the project owner.
  7. Changes under ``src/`` or ``web/`` since the given date come with a ``CHANGELOG.md`` change.
  8. Optionally, the published report is fresh (``--report-url``).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWNER = "Carlos Saritama <cssaritama@gmail.com>"
TEXT_SUFFIXES = {".md", ".py", ".js", ".html", ".css", ".json", ".toml", ".yml", ".yaml", ".txt", ".cfg"}
TOOL_NAMES = re.compile(r"\b(claude|anthropic|chatgpt|openai|codex|gemini|copilot|cursor ai|llm assistant)\b", re.I)
CLAIMS = re.compile(
    r"\b(guaranteed (returns?|profits?)|risk[- ]free profits?|pure alpha|mathematically proven|win probability|can'?t lose)\b",
    re.I,
)
DATA_SUFFIXES = {".csv", ".parquet", ".gz", ".zip", ".feather", ".h5", ".xlsx"}
HYPOTHESIS = re.compile(r"\bH-\d{4}-\d{3}\b")
SELF = Path(__file__).resolve()


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout


def tracked() -> list[Path]:
    return [ROOT / p for p in git("ls-files").splitlines()]


def text_files() -> list[Path]:
    return [p for p in tracked() if p.suffix in TEXT_SUFFIXES and p.is_file() and p.resolve() != SELF]


def check_hypotheses() -> list[str]:
    registry = {h["id"] for h in json.loads((ROOT / "registry/hypotheses.json").read_text())}
    problems = []
    for path in text_files():
        if path.name in ("hypotheses.json", "test_check_rules.py"):
            continue  # the register itself, and the checker's own fixtures
        for n, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            for hid in HYPOTHESIS.findall(line):
                if hid not in registry and "withdrawn" not in line.lower() and "never registered" not in line.lower():
                    problems.append(f"{path.relative_to(ROOT)}:{n} cites {hid}, which is not in the register")
    return problems


def check_specs() -> list[str]:
    files = sorted((ROOT / "specs").glob("[0-9][0-9][0-9][0-9]-*.md"))
    numbers = [f.name[:4] for f in files]
    problems = [
        f"specification number {n} is used by more than one file"
        for n in sorted({n for n in numbers if numbers.count(n) > 1})
    ]
    index = (ROOT / "specs/README.md").read_text()
    problems += [f"specs/{f.name} is not in specs/README.md" for f in files if f"({f.name})" not in index]
    return problems


def check_tool_names() -> list[str]:
    problems = []
    for path in text_files():
        for n, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            match = TOOL_NAMES.search(line)
            if match:
                problems.append(f"{path.relative_to(ROOT)}:{n} names a tool ('{match.group(0)}')")
    return problems


def check_claims() -> list[str]:
    problems = []
    for path in text_files():
        rel = path.relative_to(ROOT).as_posix()
        if not (rel.startswith(("web/", "docs/", "specs/")) or rel == "README.md"):
            continue
        content = path.read_text(errors="ignore")
        if rel.startswith("specs/") and "**Status:** withdrawn" in content:
            continue
        for n, line in enumerate(content.splitlines(), 1):
            match = CLAIMS.search(line)
            if match:
                problems.append(f"{rel}:{n} makes a claim no study supports ('{match.group(0)}')")
    return problems


def check_data_files() -> list[str]:
    problems = []
    for path in tracked():
        rel = path.relative_to(ROOT).as_posix()
        if path.suffix in DATA_SUFFIXES and not rel.startswith(("examples/", "tests/")):
            problems.append(f"{rel} is a data file outside examples/ and tests/")
    return problems


def check_history(since: str) -> list[str]:
    problems = []
    log = git("log", f"--since={since}", "--no-merges", "--format=%H%x09%an <%ae>%x09%s", "HEAD")
    commits = [line.split("\t") for line in log.splitlines() if line]
    for sha, author, subject in commits:
        if author != OWNER:
            problems.append(f"commit {sha[:7]} ({subject}) is authored by {author}")
    changed = set()
    for sha, _, _ in commits:
        changed |= set(git("show", "--name-only", "--format=", sha).split())
    code = sorted(p for p in changed if p.startswith(("src/", "web/")))
    if code and "CHANGELOG.md" not in changed:
        problems.append(f"{len(code)} file(s) under src/ or web/ changed since {since} without a CHANGELOG.md change")
    return problems


def check_report(url: str) -> list[str]:
    sys.path.insert(0, str(ROOT / "src"))
    from tsip.data import freshness

    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            report = json.loads(response.read())
    except Exception as exc:  # network or format problems are reported, not hidden
        return [f"published report could not be read ({exc})"]
    status = freshness.assess(report)
    if status["overall"] == "stale":
        stale = [r["code"] for r in status["instruments"] if r["status"] == "stale"]
        return [f"published report of {report.get('generated_at')} is stale now for {', '.join(stale)}"]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", default="2026-11-10", help="start of the history checks (git date)")
    parser.add_argument("--report-url", default=None)
    args = parser.parse_args(argv)
    checks = {
        "Hypothesis IDs are registered": check_hypotheses,
        "Specification numbers are unique and indexed": check_specs,
        "No tool or assistant names": check_tool_names,
        "No unsupported claims in public text": check_claims,
        "No data files in the repository": check_data_files,
        f"Authors and changelog since {args.since}": lambda: check_history(args.since),
    }
    if args.report_url:
        checks["Published report is fresh"] = lambda: check_report(args.report_url)
    lines, failed = ["## Repository rules", ""], False
    for name, check in checks.items():
        problems = check()
        failed |= bool(problems)
        lines.append(f"- {'FAIL' if problems else 'pass'}: {name}")
        lines += [f"  - {p}" for p in problems[:50]]
    summary = "\n".join(lines) + "\n"
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as fh:
            fh.write(summary)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
