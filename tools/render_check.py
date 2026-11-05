"""Render check: open the built website in a headless browser and fail on console errors,
horizontal scroll or overlapping chart text. Specification: ``specs/0002-readable-charts.md``.

    tsip site --report report.json --out dist
    python tools/render_check.py --site dist --markets SPY,BTC-USD,SPX

Requires Playwright with Chromium (``pip install playwright`` and ``playwright install chromium``).
Exit status 1 when any problem is found.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import sys
import threading
from pathlib import Path

WIDTHS = (390, 768, 1024, 1280, 1440, 1920)

# Bounding boxes of visible SVG text, and of dots, in screen pixels; pairs that intersect by more
# than one pixel in both directions are overlaps.
OVERLAPS = r"""
() => {
  const visible = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none"; };
  const hit = (a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1;
  const out = [];
  for (const chart of document.querySelectorAll("main svg")) {
    if (!visible(chart) || chart.closest("[hidden]")) continue;
    const texts = [...chart.querySelectorAll("text")].filter(visible).map((t) => ({ t: t.textContent, r: t.getBoundingClientRect() }));
    const dots = [...chart.querySelectorAll("circle")].filter(visible).map((c) => ({ r: c.getBoundingClientRect() }));
    for (let i = 0; i < texts.length; i++) {
      for (let j = i + 1; j < texts.length; j++) if (hit(texts[i].r, texts[j].r)) out.push(`${chart.getAttribute("class")}: "${texts[i].t}" / "${texts[j].t}"`);
      for (const d of dots) if (hit(texts[i].r, d.r)) out.push(`${chart.getAttribute("class")}: "${texts[i].t}" / dot`);
    }
  }
  return out;
}
"""


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # noqa: D401 - keep the check's output readable
        pass


# Board tiles clip their content (hidden overflow): a tile whose content is wider than the tile has
# text that cannot be seen, which the page-level scroll check does not catch.
CLIPPED = r"""
() => [...document.querySelectorAll(".tile, .coord, .curves-card")]
  .filter((t) => t.getBoundingClientRect().width > 0 && t.scrollWidth > t.clientWidth + 1)
  .map((t) => `${t.className}: content ${t.scrollWidth}px in ${t.clientWidth}px`)
"""


def serve(directory: Path) -> tuple[http.server.ThreadingHTTPServer, str]:
    handler = functools.partial(_QuietHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/"


def check(site: Path, markets: list[str], widths: tuple[int, ...] = WIDTHS) -> list[str]:
    from playwright.sync_api import sync_playwright

    server, url = serve(site)
    problems: list[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for width in widths:
                for scheme in ("dark", "light"):
                    page = browser.new_page(viewport={"width": width, "height": 900}, color_scheme=scheme)
                    errors: list[str] = []
                    page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
                    page.on("console", lambda m, errors=errors: errors.append(m.text) if m.type == "error" else None)
                    page.goto(url)
                    page.wait_for_selector(".switch__opt", timeout=15000)
                    for code in markets:
                        button = page.locator(f'.switch__opt[data-code="{code}"]')
                        if button.count() == 0:
                            problems.append(f"{width}px: market {code} not in the report")
                            continue
                        button.first.click()
                        page.wait_for_timeout(250)
                        where = f"{width}px {scheme} {code}"
                        scroll = page.evaluate(
                            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
                        )
                        if scroll > 1:
                            problems.append(f"{where}: horizontal scroll of {scroll}px")
                        problems.extend(f"{where}: overlap {o}" for o in page.evaluate(OVERLAPS))
                        problems.extend(f"{where}: clipped {c}" for c in page.evaluate(CLIPPED))
                    problems.extend(f"{width}px {scheme}: console error {e}" for e in errors)
                    page.close()
            browser.close()
    finally:
        server.shutdown()
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", type=Path, required=True, help="directory built by `tsip site`")
    parser.add_argument("--markets", default="SPY,BTC-USD,SPX", help="comma-separated market codes to open")
    parser.add_argument("--widths", default=",".join(map(str, WIDTHS)))
    args = parser.parse_args(argv)
    problems = check(
        args.site, [m for m in args.markets.split(",") if m], tuple(int(w) for w in args.widths.split(","))
    )
    for line in problems:
        print(line)
    print(f"render check: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
