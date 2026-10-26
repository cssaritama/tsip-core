(() => {
  "use strict";

  const MARKET_NAMES = { SPY: "S&P 500", SPX: "S&P 500", "BTC-USD": "Bitcoin", "BTC-USDT": "Bitcoin" };
  const FAMILY_NAMES = {
    levels: "Level memory", sessions: "Sessions", intraday: "Intraday", weekly: "Weekly structure",
    paths: "Paths", entries: "Entries", calendar: "Calendar",
  };
  const state = { report: null, active: null };

  const el = (tag, attrs = {}, ...children) => {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "html") node.innerHTML = value;
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

  // ------------------------------------------------------------------ cards
  function detailsTable(card) {
    const edge = card.kind === "edge";
    const head = edge
      ? ["", "Estimate", "95% CI", "n", "Recent 30%", "q", "Grade"]
      : ["", "Rate", "95% CI", "n", "Recent 30%", "Last period", "Grade"];
    const rows = card.items.map((i) => {
      const cells = edge
        ? [i.label, fmt(i.estimate, card.unit), `${fmt(i.ci_low, card.unit)} … ${fmt(i.ci_high, card.unit)}`, num(i.n), fmt(i.holdout, card.unit), pval(i.q_value), i.grade]
        : [i.label, pct(i.estimate, 1), `${pct(i.ci_low, 1)} … ${pct(i.ci_high, 1)}`, num(i.n), pct(i.holdout, 1), pct(i.recent, 1), i.grade];
      return el("tr", {}, ...cells.map((c) => el("td", {}, c)));
    });
    return el("div", { class: "table-wrap" },
      el("table", {}, el("thead", {}, el("tr", {}, ...head.map((h) => el("th", {}, h)))), el("tbody", {}, ...rows)));
  }

  function renderCard(card) {
    let visual;
    if (card.kind === "base_rate") visual = baseRateBars(card.items);
    else if (card.items.length > 3) visual = verticalBars(card.items, card.unit, card.primary);
    else visual = statBlocks(card);
    const notes = (card.notes || []).map((n) => el("p", {}, n));
    return el("article", { class: "card", id: card.id.replaceAll(".", "-") },
      el("div", { class: "card__head" },
        el("div", {},
          el("div", { class: "card__family" }, FAMILY_NAMES[card.family] || card.family),
          el("h3", { class: "card__title" }, card.title)),
        el("div", { class: `badge ${gradeClass(card.grade)}`, title: card.grade_label },
          el("span", {}, card.grade), el("small", {}, card.kind === "edge" ? "evidence" : "reliability"))),
      el("p", { class: "card__question" }, card.question),
      el("p", { class: "card__headline" }, card.headline),
      visual,
      el("details", {},
        el("summary", {}, "Method, control and numbers"),
        el("div", { class: "details__body" },
          el("p", {}, el("b", {}, "Compared with: "), card.control),
          el("p", {}, el("b", {}, "Method: "), card.method),
          el("p", {}, el("b", {}, "Sample: "), `${card.period.start} to ${card.period.end}`),
          ...notes,
          detailsTable(card))));
  }

  // ------------------------------------------------------------------ views
  function renderKpis(report) {
    const ok = report.instruments.filter((i) => i.status === "ok");
    const items = ok.flatMap((i) => i.sections.flatMap((s) => s.cards.flatMap((c) => c.items.map((it) => ({ kind: c.kind, grade: it.grade })))));
    const edges = items.filter((i) => i.kind === "edge");
    const strong = edges.filter((i) => i.grade === "A" || i.grade === "B").length;
    const years = ok.map((i) => {
      const c = i.coverage?.daily;
      return c ? (new Date(c.end) - new Date(c.start)) / (365.25 * 864e5) : 0;
    });
    const k = document.getElementById("kpis");
    k.replaceChildren(
      kpi(num(items.length), "statistics graded"),
      kpi(`${strong} of ${edges.length}`, "edge tests with A or B evidence"),
      kpi(`${Math.round(Math.max(0, ...years))} yrs`, "longest history covered"),
      kpi(new Date(report.generated_at).toUTCString().slice(5, 22), "last update (UTC)"));
  }
  const kpi = (value, label) => el("div", { class: "kpi" }, el("div", { class: "kpi__value" }, value), el("div", { class: "kpi__label" }, label));

  function renderTabs(report) {
    const tabs = document.getElementById("market-tabs");
    tabs.replaceChildren(...report.instruments.map((inst, idx) => {
      const b = el("button", { class: "tab", role: "tab", "aria-selected": String(idx === 0), id: `tab-${inst.code}` },
        `${MARKET_NAMES[inst.code] || inst.code} · ${inst.code}`);
      b.addEventListener("click", () => selectMarket(inst.code));
      return b;
    }));
  }

  function selectMarket(code) {
    state.active = code;
    for (const b of document.querySelectorAll(".tab")) b.setAttribute("aria-selected", String(b.id === `tab-${code}`));
    const inst = state.report.instruments.find((i) => i.code === code);
    const panel = document.getElementById("market-panel");
    if (!inst || inst.status !== "ok") {
      panel.replaceChildren(el("div", { class: "notice" },
        el("b", {}, `${MARKET_NAMES[code] || code}: data source not connected in this build. `),
        inst?.message || "", " Statistics appear automatically after the next scheduled update."));
      return;
    }
    const i = inst.instrument;
    const daily = inst.coverage?.daily;
    const intraday = inst.coverage?.intraday;
    const cov = el("div", { class: "coverage" },
      el("span", {}, el("b", {}, i.name), ` (${i.code}, ${i.unit})`),
      daily ? el("span", {}, `Daily ${daily.start} → ${daily.end} · ${num(daily.rows)} days`) : null,
      intraday ? el("span", {}, `Intraday ${intraday.timeframe} · ${num(intraday.rows)} bars`) : null,
      el("span", {}, `Source: ${inst.sources.map((s) => s.name || s.source).join(" + ")}`));
    const chips = el("div", { class: "chips" }, ...inst.sections.map((s) => el("a", { class: "chip", href: `#sec-${code}-${s.id}` }, s.title)));
    const notes = (inst.notes || []).map((n) => el("div", { class: "notice" }, n));
    const sections = inst.sections.map((s) =>
      el("section", { id: `sec-${code}-${s.id}` },
        el("h2", { class: "section-title" }, s.title, el("small", {}, `${s.cards.length} ${s.cards.length === 1 ? "question" : "questions"}`)),
        el("div", { class: "cards" }, ...s.cards.map(renderCard))));
    panel.replaceChildren(cov, chips, ...notes, ...sections);
  }

  function renderData(report) {
    const panel = document.getElementById("data-panel");
    const cards = [];
    for (const inst of report.instruments) {
      for (const s of inst.sources || []) {
        cards.push(el("article", { class: "data__card" },
          el("h3", {}, `${MARKET_NAMES[inst.code] || inst.code} · ${s.name || s.source}`),
          el("dl", { class: "kv" },
            el("dt", {}, "Instrument"), el("dd", {}, `${s.instrument} (${s.timeframe}, ${s.price_basis}${s.feed ? `, ${s.feed.toUpperCase()} feed` : ""})`),
            el("dt", {}, "Coverage"), el("dd", {}, `${String(s.start).slice(0, 16)} → ${String(s.end).slice(0, 16)}`),
            el("dt", {}, "Rows"), el("dd", {}, num(s.rows)),
            el("dt", {}, "SHA-256"), el("dd", { class: "hyp__hash" }, s.sha256 ? `${s.sha256.slice(0, 16)}…` : "–"),
            el("dt", {}, "Terms"), el("dd", {}, s.terms || "–"),
            s.url ? el("dt", {}, "Reference") : null, s.url ? el("dd", {}, el("a", { href: s.url, rel: "noopener" }, "documentation")) : null)));
      }
      const q = inst.quality || {};
      const rows = [];
      if (q.completeness?.expected_bars) rows.push(["Hourly completeness", `${num(q.completeness.present_bars)} of ${num(q.completeness.expected_bars)} bars (${q.completeness.missing_pct}% missing)`]);
      const x = q.cross_check_vs_binance_btcusdt;
      if (x?.return_correlation !== undefined) rows.push(["Cross-check vs. independent feed", `hourly return correlation ${x.return_correlation}; median close difference ${x.median_abs_close_diff_bps} bps over ${num(x.overlap_bars)} bars`]);
      if (q.sessions?.expected_sessions) rows.push(["Exchange calendar", `${num(q.sessions.observed_sessions)} of ${num(q.sessions.expected_sessions)} ${q.sessions.calendar} sessions (${q.sessions.missing_sessions} missing)`]);
      if (rows.length) {
        cards.push(el("article", { class: "data__card" }, el("h3", {}, `${MARKET_NAMES[inst.code] || inst.code} · quality checks`),
          el("dl", { class: "kv" }, ...rows.flatMap(([a, b]) => [el("dt", {}, a), el("dd", {}, b)]))));
      }
    }
    panel.replaceChildren(...(cards.length ? cards : [el("div", { class: "notice" }, "No datasets in this build.")]));
  }

  function renderRegister(report) {
    const panel = document.getElementById("register-panel");
    const hyps = report.hypotheses || [];
    if (!hyps.length) {
      panel.replaceChildren(el("div", { class: "notice" }, "The first pre-registered hypotheses will be published here."));
      return;
    }
    panel.replaceChildren(...hyps.map((h) => el("article", { class: "hyp" },
      el("div", {}, el("span", { class: "hyp__id" }, h.id), el("span", { class: "status" }, h.status || "open")),
      el("p", {}, h.statement),
      el("dl", { class: "kv" },
        el("dt", {}, "Instrument"), el("dd", {}, h.instrument),
        el("dt", {}, "Metric"), el("dd", {}, h.metric),
        el("dt", {}, "Success criterion"), el("dd", {}, h.criterion),
        h.basis ? el("dt", {}, "Basis") : null, h.basis ? el("dd", {}, h.basis) : null,
        el("dt", {}, "Registered"), el("dd", {}, h.registered),
        el("dt", {}, "Evaluated on data from"), el("dd", {}, `${h.evaluation_start} to ${h.evaluation_end}`),
        el("dt", {}, "Fingerprint"), el("dd", { class: "hyp__hash" }, h.sha256)))));
  }

  async function init() {
    try {
      const res = await fetch("data/report.json", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const report = await res.json();
      state.report = report;
      document.getElementById("rules-version").textContent = report.rules_version;
      document.getElementById("generated").textContent = `Report ${report.version}, generated ${report.generated_at.replace("T", " ").replace("+00:00", " UTC")}`;
      renderKpis(report);
      renderTabs(report);
      if (report.instruments.length) selectMarket(report.instruments[0].code);
      renderData(report);
      renderRegister(report);
    } catch (err) {
      document.getElementById("market-panel").replaceChildren(el("div", { class: "notice" }, `The report could not be loaded (${err.message}).`));
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
