(() => {
  "use strict";

  // Display order follows ADR 0049: one tradable instrument per family first, index references after.
  const PRIMARY = ["SPY", "QQQ", "BTC-USD", "BTC-USDT"];
  const REFERENCES = ["SPX", "NDX"];
  const MARKET_NAMES = {
    SPY: "S&P 500", SPX: "S&P 500 index", QQQ: "Nasdaq-100", NDX: "Nasdaq-100 index", "BTC-USD": "Bitcoin", "BTC-USDT": "Bitcoin",
  };
  const SHORT_CODE = { "BTC-USD": "BTC", "BTC-USDT": "BTC" };
  const HORIZONS = ["day", "week", "month", "quarter", "half-year", "year"];
  const HORIZON_NAMES = { day: "Day", week: "Week", month: "Month", quarter: "Quarter", "half-year": "Half-year", year: "Year" };
  const SEGMENTS = { A: 5, B: 4, C: 3, D: 2, F: 1, "N/A": 0 };
  const state = { report: null, active: null };

  const el = (tag, attrs = {}, ...children) => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") node.className = value;
      else node.setAttribute(key, value);
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  };
  const svg = (tag, attrs = {}) => {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  };
  const gradeClass = (g) => (g === "N/A" ? "g-NA" : `g-${g}`);
  const fmt = (v, unit, digits) => {
    if (v === null || v === undefined || Number.isNaN(v)) return "–";
    const d = digits ?? (unit === "%" ? 2 : 1);
    const sign = v > 0 ? "+" : "";
    if (unit === "bps") return `${sign}${v.toFixed(d)} bps`;
    if (unit === "pp") return `${sign}${v.toFixed(d)} pp`;
    return `${sign}${v.toFixed(d)}%`;
  };
  const pct = (v, d = 0) => (v === null || v === undefined ? "–" : `${v.toFixed(d)}%`);
  const num = (v) => (v === null || v === undefined ? "–" : Number(v).toLocaleString("en-US"));
  const pval = (v) => (v === null || v === undefined ? "–" : v < 0.001 ? "<0.001" : v.toFixed(3));
  const marketName = (code) => MARKET_NAMES[code] || code;

  function meter(grade, label) {
    const m = el("span", { class: "meter", "data-g": grade, role: "img", "aria-label": label || `Grade ${grade}` });
    for (let i = 0; i < 5; i++) m.append(el("i", { class: i < (SEGMENTS[grade] ?? 0) ? "on" : "" }));
    return m;
  }
  const gradeTag = (grade, label) =>
    el("span", { class: "grade", title: label || "" }, meter(grade, label), el("span", { class: "grade__letter" }, grade), label ? el("span", {}, label) : null);

  // ------------------------------------------------------------------ charts
  function verticalBars(items, unit, primary) {
    const w = 340, h = 150, padL = 30, padB = 20, padT = 8;
    const values = items.flatMap((i) => [i.ci_low, i.ci_high, i.estimate]).filter((v) => v !== null);
    const max = Math.max(...values.map(Math.abs), 1e-9) * 1.1;
    const y = (v) => padT + ((max - v) / (2 * max)) * (h - padT - padB);
    const band = (w - padL) / items.length;
    const root = svg("svg", { viewBox: `0 0 ${w} ${h}`, class: "chart", role: "img", "aria-label": "Estimates with 95% intervals" });
    root.append(svg("line", { x1: padL, x2: w, y1: y(0), y2: y(0), class: "zero" }));
    for (const v of [max / 1.1, -max / 1.1]) {
      const t = svg("text", { x: padL - 4, y: y(v) + 3, "text-anchor": "end" });
      t.textContent = fmt(v, unit, Math.abs(v) >= 100 ? 0 : 1).replace(" bps", "").replace(" pp", "");
      root.append(t);
    }
    const every = items.length > 14 ? 3 : 1;
    items.forEach((item, i) => {
      const x = padL + i * band + band * 0.16;
      const bw = band * 0.68;
      const top = y(Math.max(0, item.estimate ?? 0));
      const bottom = y(Math.min(0, item.estimate ?? 0));
      const rect = svg("rect", {
        x, y: top, width: bw, height: Math.max(1, bottom - top), rx: 1.5,
        fill: `var(--${gradeClass(item.grade)})`,
        class: i === primary ? "primary" : "",
      });
      const title = svg("title");
      title.textContent = `${item.label}: ${fmt(item.estimate, unit)} (95% CI ${fmt(item.ci_low, unit)} to ${fmt(item.ci_high, unit)}), grade ${item.grade}`;
      rect.append(title);
      root.append(rect);
      if (item.ci_low !== null && item.ci_high !== null) {
        const cx = x + bw / 2;
        root.append(svg("line", { x1: cx, x2: cx, y1: y(item.ci_high), y2: y(item.ci_low), class: "whisker" }));
      }
      if (i % every === 0) {
        const t = svg("text", { x: x + bw / 2, y: h - 6, "text-anchor": "middle" });
        t.textContent = shortLabel(item.label);
        root.append(t);
      }
    });
    return root;
  }

  function shortLabel(label) {
    const m = label.match(/^(\d{2}):(\d{2})/);
    if (m) return m[2] === "00" && label.includes("UTC") ? m[1] : `${m[1]}:${m[2]}`;
    if (/^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)$/.test(label)) return label.slice(0, 3);
    if (label.startsWith("Asia")) return "Asia";
    if (label.startsWith("London")) return "London";
    if (label.startsWith("New York")) return "New York";
    if (label.startsWith("Late US")) return "Late US";
    if (label.startsWith("Opening")) return "Open hour";
    if (label.startsWith("Midday")) return "Midday";
    if (label.startsWith("Closing")) return "Close hour";
    if (label.startsWith("Overnight minus")) return "Difference";
    if (label.startsWith("Overnight")) return "Overnight";
    if (label.startsWith("Intraday")) return "Intraday";
    return label.length > 10 ? label.slice(0, 9) + "…" : label;
  }

  function baseRateBars(items) {
    const wrap = el("div", { class: "hbars" });
    for (const item of items) {
      const fill = el("div", { class: "hbar__fill", style: `width:${Math.max(0, Math.min(100, item.estimate))}%;background:var(--${gradeClass(item.grade)})` });
      const ci = el("div", { class: "hbar__ci", style: `left:${item.ci_low}%;width:${Math.max(0.5, item.ci_high - item.ci_low)}%` });
      wrap.append(
        el("div", { class: "hbar", title: `${item.label}: ${pct(item.estimate, 1)} (95% CI ${pct(item.ci_low, 1)}–${pct(item.ci_high, 1)}); last period ${pct(item.recent, 1)}; reliability ${item.grade}` },
          el("div", { class: "hbar__top" },
            el("span", { class: "hbar__label" }, item.label),
            el("span", { class: "hbar__value num" }, pct(item.estimate))),
          el("div", { class: "hbar__track" }, fill, ci))
      );
    }
    return wrap;
  }

  function statBlocks(card) {
    const k = card.primary ?? 0;
    const item = card.items[k];
    if (card.family === "paths") {
      const x = item.extra || {};
      return el("div", { class: "stats" },
        stat(`Naive · ${item.label}`, pct(x.naive_upper_first_pct)),
        stat("Geometry alone", pct(x.geometry_expected_pct)),
        stat("What levels add", fmt(item.estimate, "pp"), true));
    }
    if (card.family === "entries") {
      const x = card.items[0].extra || {};
      return el("div", { class: "stats" },
        stat("Per purchase", fmt(card.items[0].estimate, "%"), true),
        stat("Extra units", fmt(card.items[1]?.estimate, "%")),
        stat("Limit fills", pct(x.fill_rate_pct)));
    }
    if (card.items.length === 1) {
      return el("div", { class: "stats" },
        stat("Effect", fmt(item.estimate, card.unit), true),
        stat(`95% interval (${card.unit})`, `${fmt(item.ci_low, card.unit).replace(/ (bps|pp)|%/, "")} … ${fmt(item.ci_high, card.unit).replace(/ (bps|pp)|%/, "")}`),
        stat("Observations", num(item.n)));
    }
    return el("div", { class: "stats" },
      ...card.items.slice(0, 3).map((i, idx) => stat(shortLabel(i.label), fmt(i.estimate, card.unit), idx === k)));
  }

  const stat = (label, value, key = false) =>
    el("div", { class: `stat${key ? " stat--key" : ""}` }, el("div", { class: "stat__label" }, label), el("div", { class: "stat__value" }, value));

  // ------------------------------------------------------------------ findings
  function detailsTable(card) {
    const edge = card.kind === "edge";
    const head = edge
      ? ["", "Estimate", "95% interval", "n", "Recent 30%", "q", "Grade"]
      : ["", "Rate", "95% interval", "n", "Recent 30%", "Last period", "Grade"];
    const rows = card.items.map((i) => {
      const cells = edge
        ? [i.label, fmt(i.estimate, card.unit), `${fmt(i.ci_low, card.unit)} to ${fmt(i.ci_high, card.unit)}`, num(i.n), fmt(i.holdout, card.unit), pval(i.q_value), i.grade]
        : [i.label, pct(i.estimate, 1), `${pct(i.ci_low, 1)} to ${pct(i.ci_high, 1)}`, num(i.n), pct(i.holdout, 1), pct(i.recent, 1), i.grade];
      return el("tr", {}, ...cells.map((c) => el("td", {}, c)));
    });
    return el("div", { class: "table-wrap" },
      el("table", {}, el("thead", {}, el("tr", {}, ...head.map((h) => el("th", {}, h)))), el("tbody", {}, ...rows)));
  }

  function stateLine(card) {
    const st = card.state || {};
    const zone = { above: "Last close above the prior range", inside: "Last close inside the prior range", below: "Last close below the prior range" };
    const flag = (done, text) => el("span", { class: done ? "state__yes" : "state__no" }, done ? text : `Not yet ${text.toLowerCase()}`);
    return el("div", { class: "state" },
      el("span", {}, `${st.period} against ${st.prior_period}`),
      flag(st.broke_prior_high, "Above the prior high"),
      flag(st.broke_prior_low, "Below the prior low"),
      el("span", {}, zone[st.last_close_vs_prior_range] || ""));
  }

  function renderFinding(card, gradeLabels) {
    let visual;
    if (card.kind === "base_rate") visual = card.items.length ? baseRateBars(card.items) : null;
    else if (card.items.length > 3) visual = verticalBars(card.items, card.unit, card.primary);
    else visual = statBlocks(card);
    const labels = gradeLabels[card.kind === "edge" ? "edge" : "base_rate"] || {};
    const notes = (card.notes || []).map((n) => el("p", {}, n));
    return el("article", { class: "finding", id: card.id.replaceAll(".", "-") },
      el("div", {},
        el("h3", { class: "finding__title" }, card.title),
        el("p", { class: "finding__q" }, card.question),
        card.family === "map" ? stateLine(card) : null,
        el("p", { class: "finding__headline" }, card.headline)),
      el("div", { class: "finding__side" },
        gradeTag(card.grade, labels[card.grade] || card.grade_label),
        el("div", { class: "finding__visual" }, visual)),
      el("details", {},
        el("summary", {}, "Method, control and numbers"),
        el("div", { class: "details__body" },
          el("p", {}, el("b", {}, "Compared with: "), card.control),
          el("p", {}, el("b", {}, "Method: "), card.method),
          el("p", {}, el("b", {}, "Sample: "), `${card.period.start} to ${card.period.end}`),
          ...notes,
          card.items.length ? detailsTable(card) : null)));
  }

  // ------------------------------------------------------------------ time–space grid
  function mapCards(inst) {
    const cards = (inst.sections || []).flatMap((s) => s.cards).filter((c) => c.family === "map" && c.state);
    return cards.sort((a, b) => HORIZONS.indexOf(a.state.horizon) - HORIZONS.indexOf(b.state.horizon));
  }

  function gridRow(card, labels) {
    const st = card.state;
    const share = st.typical_sessions ? Math.min(1, st.sessions_elapsed / st.typical_sessions) : 0;
    const unit = st.session_unit || "sessions";
    const zones = ["below", "inside", "above"].map((z) => {
      const on = st.last_close_vs_prior_range === z;
      const label = { below: "Below", inside: "Inside", above: "Above" }[z];
      const zone = el("span", { class: `zone${on ? " zone--on" : ""}` }, label);
      if (z === "inside" && st.broke_prior_low) zone.append(el("span", { class: "zone__tick zone__tick--low", title: "Prior low taken" }));
      if (z === "inside" && st.broke_prior_high) zone.append(el("span", { class: "zone__tick zone__tick--high", title: "Prior high taken" }));
      return zone;
    });
    const taken = [st.broke_prior_high && "prior high taken", st.broke_prior_low && "prior low taken"].filter(Boolean);
    const item = card.items[card.primary ?? 0];
    const gradeLabel = labels[card.grade] || card.grade_label;
    return el("a", { class: "row", href: `#${card.id.replaceAll(".", "-")}`,
      "aria-label": `${HORIZON_NAMES[st.horizon]}: ${card.headline}` },
      el("div", { class: "row__h" }, el("b", {}, HORIZON_NAMES[st.horizon] || st.horizon), el("span", {}, st.period)),
      el("div", {},
        el("div", { class: "elapsed__track" }, el("span", { class: "elapsed__fill", style: `width:${(share * 100).toFixed(1)}%` })),
        el("div", { class: "elapsed__text" }, `${st.sessions_elapsed} of about ${st.typical_sessions} ${unit}`)),
      el("div", {},
        el("div", { class: "zones", role: "img", "aria-label": `Last close ${st.last_close_vs_prior_range} the prior ${st.horizon} range` }, ...zones),
        el("div", { class: "zones__note" }, taken.length ? capital(taken.join(", ")) : "Neither prior extreme taken")),
      item
        ? el("div", { class: "outcome" },
            el("div", {},
              el("div", { class: "outcome__fig" }, pct(item.estimate)),
              el("div", { class: "outcome__label" }, item.label)),
            el("div", { class: "outcome__side" }, gradeTag(card.grade, null), el("div", { class: "outcome__n" }, `${num(st.analogs ?? item.n)} past ${card.n_label}`)))
        : el("div", { class: "outcome" }, el("div", { class: "outcome__label" }, "Not enough comparable periods yet")));
  }
  const capital = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  function renderGrid(inst) {
    const grid = document.getElementById("grid");
    const rows = document.getElementById("grid-rows");
    const caption = document.getElementById("grid-caption");
    grid.classList.remove("is-ready");
    if (!inst || inst.status !== "ok") {
      rows.replaceChildren(el("div", { class: "grid__empty" }, `${marketName(inst?.code)}: no data in this build. It appears after the next scheduled update.`));
      caption.replaceChildren();
      return;
    }
    const cards = mapCards(inst);
    const labels = state.report.grade_labels?.base_rate || {};
    rows.replaceChildren(...(cards.length
      ? cards.map((c) => gridRow(c, labels))
      : [el("div", { class: "grid__empty" }, "The position against prior periods needs a longer history for this market.")]));
    const asOf = cards[0]?.state?.as_of;
    caption.replaceChildren(
      el("span", {}, `${inst.instrument.name}, ${inst.instrument.unit}${asOf ? `, as of ${asOf}` : ""}`),
      el("span", {}, "Past periods are compared at the same point and in the same position. Price levels are not published."));
    requestAnimationFrame(() => grid.classList.add("is-ready"));
  }

  // ------------------------------------------------------------------ views
  function ordered(report) {
    const codes = report.instruments.map((i) => i.code);
    const main = PRIMARY.filter((c) => codes.includes(c));
    const refs = REFERENCES.filter((c) => codes.includes(c));
    const rest = codes.filter((c) => !main.includes(c) && !refs.includes(c));
    return { main: [...main, ...rest], refs };
  }

  function renderSwitch(report) {
    const { main, refs } = ordered(report);
    const option = (code) => {
      const b = el("button", { class: "switch__opt", role: "tab", "aria-selected": "false", "data-code": code, type: "button" },
        el("b", {}, SHORT_CODE[code] || code), el("span", {}, marketName(code)));
      b.addEventListener("click", () => selectMarket(code));
      return b;
    };
    const box = document.getElementById("market-switch");
    box.replaceChildren(...main.map(option),
      refs.length ? el("div", { class: "switch__refs" }, el("span", {}, "Index references"), ...refs.map(option)) : null);
    return main[0] || refs[0];
  }

  function selectMarket(code) {
    state.active = code;
    for (const b of document.querySelectorAll(".switch__opt")) b.setAttribute("aria-selected", String(b.dataset.code === code));
    const inst = state.report.instruments.find((i) => i.code === code);
    renderGrid(inst);
    const panel = document.getElementById("market-panel");
    const index = document.getElementById("section-index");
    document.getElementById("index-market").textContent = `${marketName(code)}, ${code}`;
    if (!inst || inst.status !== "ok") {
      index.replaceChildren();
      panel.replaceChildren(el("div", { class: "notice" }, `${marketName(code)}: no data in this build. ${inst?.message || ""}`));
      return;
    }
    const cov = inst.coverage || {};
    const span = [cov.daily && `Daily ${cov.daily.start} to ${cov.daily.end}`, cov.intraday && `${cov.intraday.timeframe} bars from ${cov.intraday.start}`].filter(Boolean);
    document.getElementById("index-refs").replaceChildren(...span.map((s) => el("div", {}, s)),
      el("div", {}, `Source: ${inst.sources.map((s) => s.name || s.source).join(", ")}`));
    index.replaceChildren(...inst.sections.map((s) => el("a", { href: `#sec-${code}-${s.id}` }, s.title)));
    const labels = state.report.grade_labels || {};
    const notes = (inst.notes || []).map((n) => el("div", { class: "notice" }, n));
    panel.replaceChildren(...notes, ...inst.sections.map((s) =>
      el("section", { class: "group", id: `sec-${code}-${s.id}` },
        el("h2", { class: "group__title" }, s.title),
        el("p", { class: "group__count" }, `${s.cards.length} ${s.cards.length === 1 ? "question" : "questions"}`),
        ...s.cards.map((c) => renderFinding(c, labels)))));
  }

  function renderStatus(report) {
    const st = report.data_status;
    const box = document.getElementById("status");
    const text = { fresh: "Data up to date", degraded: "Data current, fallback in use", stale: "Some data out of date" };
    if (!st) { box.querySelector(".status__text").textContent = "Data status unavailable"; return; }
    box.dataset.state = st.overall;
    box.querySelector(".status__text").textContent = text[st.overall] || st.overall;
    const word = { fresh: "Up to date", degraded: "Fallback source", stale: "Out of date" };
    const rows = st.instruments.map((r) => el("tr", {},
      el("td", {}, `${marketName(r.code)}, ${r.code}`),
      el("td", {}, el("span", { class: `dot dot--${r.status}` }), word[r.status] || r.status),
      el("td", {}, r.source || "–"),
      el("td", {}, r.last_bar ? r.last_bar.slice(0, 16).replace("T", " ").replace(" 00:00", "") : "missing"),
      el("td", {}, r.reason || `Allowed delay ${r.allowed || "–"}`)));
    document.getElementById("data-status").replaceChildren(el("div", { class: "table-wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, ...["Market", "Status", "Source", "Last bar (UTC)", "Note"].map((h) => el("th", {}, h)))),
      el("tbody", {}, ...rows))));
  }

  function renderData(report) {
    const out = [];
    for (const inst of report.instruments) {
      for (const s of inst.sources || []) {
        out.push(el("article", { class: "source" },
          el("h3", {}, `${marketName(inst.code)}: ${s.name || s.source}`),
          el("dl", { class: "kv" },
            el("dt", {}, "Instrument"), el("dd", {}, `${s.instrument || inst.code} (${s.timeframe}, ${s.price_basis}${s.feed ? `, ${s.feed.toUpperCase()} feed` : ""})`),
            el("dt", {}, "Coverage"), el("dd", {}, `${String(s.start).slice(0, 16)} to ${String(s.end).slice(0, 16)}`),
            el("dt", {}, "Rows"), el("dd", {}, num(s.rows)),
            el("dt", {}, "SHA-256"), el("dd", { class: "hash" }, s.sha256 ? `${s.sha256.slice(0, 16)}…` : "–"),
            el("dt", {}, "Terms"), el("dd", {}, s.terms || "–"),
            s.url ? el("dt", {}, "Reference") : null, s.url ? el("dd", {}, el("a", { href: s.url, rel: "noopener" }, "Provider documentation")) : null)));
      }
      const q = inst.quality || {};
      const rows = [];
      if (q.completeness?.expected_bars) rows.push(["Completeness", `${num(q.completeness.present_bars)} of ${num(q.completeness.expected_bars)} hourly bars (${q.completeness.missing_pct}% missing)`]);
      const x = q.cross_check_vs_binance_btcusdt;
      if (x?.return_correlation !== undefined) rows.push(["Cross-check", `Hourly return correlation ${x.return_correlation}; median close difference ${x.median_abs_close_diff_bps} bps over ${num(x.overlap_bars)} bars`]);
      if (q.sessions?.expected_sessions) rows.push(["Calendar", `${num(q.sessions.observed_sessions)} of ${num(q.sessions.expected_sessions)} ${q.sessions.calendar} sessions (${q.sessions.missing_sessions} missing)`]);
      if (rows.length) {
        out.push(el("article", { class: "source" }, el("h3", {}, `${marketName(inst.code)}: quality checks`),
          el("dl", { class: "kv" }, ...rows.flatMap(([a, b]) => [el("dt", {}, a), el("dd", {}, b)]))));
      }
    }
    document.getElementById("data-panel").replaceChildren(...(out.length ? out : [el("div", { class: "notice" }, "No datasets in this build.")]));
  }

  function renderRegister(report) {
    const panel = document.getElementById("register-panel");
    const hyps = report.hypotheses || [];
    if (!hyps.length) {
      panel.replaceChildren(el("div", { class: "notice" }, "The first pre-registered hypotheses will be published here."));
      return;
    }
    panel.replaceChildren(...hyps.map((h) => el("article", { class: "hyp" },
      el("div", { class: "hyp__head" }, el("span", { class: "hyp__id" }, h.id), el("span", {}, capital(h.status || "open")), el("span", {}, `Evaluated on data from ${h.evaluation_start} to ${h.evaluation_end}`)),
      el("p", {}, h.statement),
      el("dl", { class: "kv" },
        el("dt", {}, "Instrument"), el("dd", {}, h.instrument),
        el("dt", {}, "Metric"), el("dd", {}, h.metric),
        el("dt", {}, "Success"), el("dd", {}, h.criterion),
        h.basis ? el("dt", {}, "Basis") : null, h.basis ? el("dd", {}, h.basis) : null,
        el("dt", {}, "Registered"), el("dd", {}, h.registered),
        el("dt", {}, "Fingerprint"), el("dd", { class: "hash" }, h.sha256)))));
  }

  function fillStaticMeters() {
    for (const m of document.querySelectorAll(".scale .meter")) {
      const g = m.dataset.g;
      for (let i = 0; i < 5; i++) m.append(el("i", { class: i < (SEGMENTS[g] ?? 0) ? "on" : "" }));
    }
  }

  async function init() {
    fillStaticMeters();
    try {
      const res = await fetch("data/report.json", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const report = await res.json();
      state.report = report;
      document.getElementById("rules-version").textContent = report.rules_version;
      document.getElementById("generated").textContent = `Report ${report.version}, generated ${report.generated_at.replace("T", " ").replace("+00:00", " UTC")}`;
      renderStatus(report);
      const first = renderSwitch(report);
      if (first) selectMarket(first);
      renderData(report);
      renderRegister(report);
    } catch (err) {
      document.getElementById("grid-rows").replaceChildren(el("div", { class: "grid__empty" }, `The report could not be loaded (${err.message}). Reload the page to try again.`));
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
