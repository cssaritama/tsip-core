(() => {
  "use strict";

  // Display order follows ADR 0049: one tradable instrument per family first, index references after.
  const PRIMARY = ["SPY", "QQQ", "BTC-USD", "ETH-USD", "BTC-USDT"];
  const REFERENCES = ["SPX", "NDX"];
  const MARKET_NAMES = {
    SPY: "S&P 500", SPX: "S&P 500 index", QQQ: "Nasdaq-100", NDX: "Nasdaq-100 index", "BTC-USD": "Bitcoin", "BTC-USDT": "Bitcoin", "ETH-USD": "Ether",
  };
  const SHORT_CODE = { "BTC-USD": "BTC", "BTC-USDT": "BTC", "ETH-USD": "ETH" };
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
    if (unit === "pp") return `${sign}${v.toFixed(d)} pts`;
    if (unit === "ATR") return `${sign}${v.toFixed(digits ?? 2)} ATR`;
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
  const CONFIDENCE = {
    edge: { A: "Strong evidence", B: "Moderate evidence", C: "Weak evidence", D: "No reliable difference from the control", F: "Contradicted by recent data", "N/A": "Not enough history yet" },
    base_rate: { A: "High reliability", B: "Good reliability", C: "Fair reliability", D: "Wide uncertainty", "N/A": "Not enough history yet" },
  };
  const confidence = (card, grade) => CONFIDENCE[card.kind === "edge" ? "edge" : "base_rate"][grade] || grade;
  const RANK = { A: 0, B: 1, C: 2, F: 3, D: 4, "N/A": 5 };
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
    const longest = Math.max(...items.map((i) => shortLabel(i.label).length));
    const every = Math.max(1, Math.ceil((longest * 6 + 6) / band));  // labels never touch
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

  // "Observed against control" in plain numbers, so a difference in points is never shown alone.
  function compareLine(card) {
    const it = card.items[card.primary ?? 0];
    if (!it || it.observed === null || it.observed === undefined || it.baseline === null || it.baseline === undefined) return null;
    const contrast = card.contrast || "the control";
    if (card.family === "volatility") {
      const what = card.id.endsWith("hour") || card.id.endsWith("halfhour") ? "range" : "move";
      return el("p", { class: "finding__compare" }, `${it.label}: typical ${what} ${it.observed.toFixed(2)}% against ${it.baseline.toFixed(2)}% for ${contrast}.`);
    }
    if (card.unit === "pp") {
      return el("p", { class: "finding__compare" }, `${it.label}: ${it.observed.toFixed(1)}% observed against ${it.baseline.toFixed(1)}% for ${contrast}; the difference is ${fmt(it.estimate, "pp")}.`);
    }
    if (card.unit === "ATR") {
      return el("p", { class: "finding__compare" }, `${it.label}: on average ${signed(it.observed, 2)} ATR in the same position against ${signed(it.baseline, 2)} ATR for ${contrast}; the difference is ${fmt(it.estimate, "ATR")}.`);
    }
    return null;
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
        el("p", { class: "finding__headline" }, card.headline),
        compareLine(card)),
      el("div", { class: "finding__side" },
        gradeTag(card.grade, card.grade === "N/A" ? `${confidence(card, "N/A")}: ${num(card.items[0]?.n)} ${card.n_label}` : confidence(card, card.grade)),
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
  const HKEY = { week: "week", month: "month", quarter: "quarter", "half-year": "half-year", year: "year" };
  const signed = (v, d = 2) => {
    if (v === null || v === undefined) return "–";
    const r = Number(v.toFixed(d));  // no "-0.00": a value that rounds to zero is shown as zero
    return `${r > 0 ? "+" : ""}${(r === 0 ? 0 : r).toFixed(d)}`;
  };
  const capital = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  function cardsOf(inst) {
    return (inst.sections || []).flatMap((s) => s.cards);
  }

  // Range bar: the reference range is the middle 50% of the track; the marker is the last close.
  function rangeBar(p) {
    const pos = p.range_position_pct;
    const x = pos === null || pos === undefined ? null : Math.max(-45, Math.min(145, pos));
    const left = x === null ? 50 : 25 + x * 0.5;
    const zone = x === null ? "" : pos > 100 ? "above" : pos < 0 ? "below" : "inside";
    const bar = el("div", { class: `range range--${zone}`, role: "img",
      "aria-label": `Last close at ${pos === null ? "an unknown point" : `${pos.toFixed(0)}% of the ${p.reference} range`}` },
      el("span", { class: "range__band" }),
      el("span", { class: "range__edge range__edge--low" }),
      el("span", { class: "range__edge range__edge--high" }),
      x === null ? null : el("span", { class: "range__mark", style: `left:${left.toFixed(1)}%` }));
    const atr = (v) => (v === undefined || v === null ? "" : ` (${signed(v, 1)} ATR)`);
    return el("div", {}, bar,
      el("div", { class: "range__text" },
        el("span", {}, `Low ${signed(p.to_reference_low_pct)}%${atr(p.to_reference_low_atr)}`),
        el("span", {}, `High ${signed(p.to_reference_high_pct)}%${atr(p.to_reference_high_atr)}`)));
  }

  function outcomeFor(p, inst) {
    const cards = cardsOf(inst);
    const h = HKEY[p.horizon];
    if (p.status === "in_progress") {
      const map = cards.find((c) => c.family === "map" && c.state?.horizon === p.horizon);
      if (!map || !map.items.length) return null;
      const item = map.items[map.primary ?? 0];
      return { fig: pct(item.estimate), label: item.label, grade: map.grade, n: `${num(map.state.analogs ?? item.n)} past ${map.n_label}` };
    }
    const lv = cards.find((c) => c.id.endsWith(`.levels.${h}`));
    if (!lv || lv.items.length < 2) return null;
    const up = lv.items[0], dn = lv.items[1];
    const pick = Math.abs(p.to_reference_high_pct ?? 99) <= Math.abs(p.to_reference_low_pct ?? 99) ? up : dn;
    const side = pick === up ? `trades above the ${p.reference} high` : `trades below the ${p.reference} low`;
    return { fig: pct(pick.estimate), label: `The next ${p.horizon} ${side}`, grade: lv.grade, n: `${num(pick.n)} past ${lv.n_label}` };
  }

  function gridRow(p, inst) {
    const map = cardsOf(inst).find((c) => c.family === "map" && c.state?.horizon === p.horizon);
    const st = map?.state;
    const closed = p.status === "closed";
    const share = !closed && st?.typical_sessions ? Math.min(1, st.sessions_elapsed / st.typical_sessions) : closed ? 0 : null;
    const unit = st?.session_unit || "sessions";
    const taken = closed ? [] : [p.took_reference_high && "reference high taken", p.took_reference_low && "reference low taken"].filter(Boolean);
    const out = outcomeFor(p, inst);
    const target = closed ? cardsOf(inst).find((c) => c.id.endsWith(`.levels.${HKEY[p.horizon]}`)) : map;
    const attrs = { class: "row" };
    if (target) attrs.href = `#${target.id.replaceAll(".", "-")}`;
    return el(target ? "a" : "div", attrs,
      el("div", { class: "row__h" }, el("b", {}, capital(p.horizon)), el("span", {}, closed ? `${p.period} opens next` : p.period)),
      el("div", {},
        el("div", { class: "elapsed__track" }, share === null ? null : el("span", { class: "elapsed__fill", style: `width:${(share * 100).toFixed(1)}%` })),
        el("div", { class: "elapsed__text" }, closed ? `Against ${p.reference}, which has closed` : st ? `${st.sessions_elapsed} of about ${st.typical_sessions} ${unit}, against ${p.reference}` : `Against ${p.reference}`)),
      el("div", {}, rangeBar(p), taken.length ? el("div", { class: "zones__note" }, capital(taken.join(", "))) : null),
      out
        ? el("div", { class: "outcome" },
            el("div", {}, el("div", { class: `outcome__fig${out.grade === "N/A" ? " outcome__fig--thin" : ""}` }, out.fig), el("div", { class: "outcome__label" }, out.label)),
            el("div", { class: "outcome__side" }, gradeTag(out.grade, null), el("div", { class: "outcome__n" }, out.grade === "N/A" ? `Not enough history yet: ${out.n}` : out.n)))
        : el("div", { class: "outcome" }, el("div", { class: "outcome__label" }, "Not enough comparable periods yet")));
  }

  // Untested levels: highs and lows of closed periods that price has not traded since. The ladder places
  // each one by its distance from the last close (in ATR); the table gives how often price has travelled
  // that far within 5, 20 and 60 sessions, from every past session of the same market.
  function levelName(l) {
    const hs = l.horizons?.length ? l.horizons : [l.horizon];
    const names = hs.map((h) => capital(h));
    return `${names.join(" and ")} ${l.side}`;
  }

  // Labels never overlap: highs are laid out above the close line and lows below it, at least 16 px
  // apart; a label moved away from its dot is joined to it by a leader line, and dots that would
  // touch are shifted sideways.
  function spread(ys, gap, lo, hi) {
    const out = [...ys];
    for (let i = 1; i < out.length; i++) out[i] = Math.max(out[i], out[i - 1] + gap);
    if (out.length && out[out.length - 1] > hi) {
      out[out.length - 1] = hi;
      for (let i = out.length - 2; i >= 0; i--) out[i] = Math.min(out[i], out[i + 1] - gap);
    }
    if (out.length && out[0] < lo) {
      out[0] = lo;
      for (let i = 1; i < out.length; i++) out[i] = Math.max(out[i], out[i - 1] + gap);
    }
    return out;
  }

  function ladder(levels) {
    const span = 4, gap = 16, dotX = 58, textX = 104;
    const shown = levels.filter((l) => l.distance_atr !== null && Math.abs(l.distance_atr) <= span).slice(0, 10);
    const highs = shown.filter((l) => l.distance_atr > 0).sort((a, b) => b.distance_atr - a.distance_atr);
    const lows = shown.filter((l) => l.distance_atr <= 0).sort((a, b) => b.distance_atr - a.distance_atr);
    const half = Math.max(132, (Math.max(highs.length, lows.length) + 1) * gap);
    const w = 380, h = 2 * half + 36, mid = 18 + half;
    const y = (atr) => mid - Math.max(-span, Math.min(span, atr)) * (half - 10) / span;
    const root = svg("svg", { viewBox: `0 0 ${w} ${h}`, class: "ladder", role: "img", "aria-label": "Untested levels by distance from the last close, in ATR" });
    for (const t of [-3, -2, -1, 1, 2, 3]) {
      root.append(svg("line", { x1: 40, x2: w - 8, y1: y(t), y2: y(t), class: "ladder__grid" }));
      const lab = svg("text", { x: 34, y: y(t) + 3, "text-anchor": "end" }); lab.textContent = `${t > 0 ? "+" : ""}${t}`; root.append(lab);
    }
    root.append(svg("line", { x1: 40, x2: w - 8, y1: mid, y2: mid, class: "ladder__now" }));
    const now = svg("text", { x: 34, y: mid + 3, "text-anchor": "end", class: "ladder__nowlabel" }); now.textContent = "Close"; root.append(now);
    const unit = svg("text", { x: 40, y: 11, class: "ladder__unit" }); unit.textContent = "ATR from the last close"; root.append(unit);
    const draw = (group, lo, hi) => {
      const dotY = group.map((l) => y(l.distance_atr));
      const textY = spread(dotY, gap, lo, hi);
      let prevY = -99, shift = 0;
      group.forEach((l, i) => {
        const r = 4 + Math.min(3, ((l.confluence || 1) - 1) * 1.5);
        shift = Math.abs(dotY[i] - prevY) < 2 * r + 2 ? Math.min(shift + 1, 2) : 0;
        prevY = dotY[i];
        const cx = dotX + shift * 13;
        if (Math.abs(textY[i] - dotY[i]) > 1 || shift) {
          root.append(svg("path", { d: `M${cx + r + 2},${dotY[i].toFixed(1)} L${textX - 6},${textY[i].toFixed(1)}`, class: "ladder__leader" }));
        }
        root.append(svg("circle", { cx, cy: dotY[i], r, class: `ladder__dot ladder__dot--${l.side}` }));
        const p = l.reach?.within?.["20"]?.pct;
        const t = svg("text", { x: textX, y: textY[i] + 4, class: "ladder__label" });
        t.textContent = `${levelName(l)}  ${signed(l.distance_pct)}%${p === null || p === undefined ? "" : `  ·  ${p.toFixed(0)}% in 20`}`;
        root.append(t);
      });
    };
    draw(highs, 22, mid - 10);
    draw(lows, mid + 12, h - 8);
    return root;
  }

  function renderOpenLevels(inst) {
    const box = document.getElementById("open-levels");
    const ol = inst?.open_levels;
    if (!ol || !ol.levels?.length) { box.replaceChildren(); box.hidden = true; return; }
    box.hidden = false;
    const unitWord = inst.instrument.calendar === "24/7" ? "days" : "sessions";
    const odds = (l, k) => {
      const o = l.reach?.within?.[k];
      return o && o.pct !== null ? el("span", { title: `95% interval ${o.ci_low}–${o.ci_high}%, ${num(o.n)} past starting points` }, `${o.pct.toFixed(0)}%`) : "–";
    };
    const rows = ol.levels.slice(0, 10).map((l) => el("tr", {},
      el("td", { class: "levels__name", title: l.levels?.join(", ") || l.period }, el("b", {}, levelName(l)), el("div", { class: "levels__sub" }, l.period)),
      el("td", { class: l.distance_pct >= 0 ? "up" : "down" }, `${signed(l.distance_pct)}%`),
      el("td", {}, l.distance_atr === null ? "–" : signed(l.distance_atr, 1)),
      el("td", {}, l.age_sessions === 0 ? "Just formed" : num(l.age_sessions)),
      el("td", {}, odds(l, "5")), el("td", {}, odds(l, "20")), el("td", {}, odds(l, "60")),
      el("td", {}, l.reach?.typical_sessions ? `${l.reach.typical_sessions}` : "over 120")));
    const revisit = cardsOf(inst).find((c) => c.family === "revisits");
    box.replaceChildren(
      el("div", { class: "levels__head" },
        el("h2", {}, "Untested levels"),
        el("p", {}, `Highs and lows of closed periods that price has not traded since: the reference points a desk watches. For each one, how often price has travelled that far within 5, 20 and 60 ${unitWord}, from every past ${unitWord.slice(0, -1)} of this market at the same volatility-scaled distance, and the typical time to get there. Levels from several horizons at one price are merged. As of ${ol.as_of}; ATR ${ol.atr_pct ? ol.atr_pct.toFixed(2) : "–"}% over 14 ${unitWord}.`),
        revisit ? el("a", { href: `#sec-${inst.code}-revisits` }, "Do real levels attract price? The evidence") : null),
      el("div", { class: "levels__body" },
        ladder(ol.levels),
        el("div", { class: "table-wrap" }, el("table", { class: "levels" },
          el("thead", {},
            el("tr", {}, el("th", { colspan: 4 }), el("th", { colspan: 3, class: "levels__group" }, `Reached within (${unitWord})`), el("th", {})),
            el("tr", {}, ...["Level", "Distance", "ATR", "Untested for", "5", "20", "60", "Typical time"].map((h) => el("th", {}, h)))),
          el("tbody", {}, ...rows)))));
  }

  function renderGrid(inst) {
    const grid = document.getElementById("grid");
    const rows = document.getElementById("grid-rows");
    const caption = document.getElementById("grid-caption");
    grid.classList.remove("is-ready");
    renderOpenLevels(inst);
    if (!inst || inst.status !== "ok") {
      rows.replaceChildren(el("div", { class: "grid__empty" }, `${marketName(inst?.code)}: no data in this build. It appears after the next scheduled update.`));
      caption.replaceChildren();
      return;
    }
    const positions = inst.position?.horizons || [];
    rows.replaceChildren(...(positions.length
      ? positions.map((p) => gridRow(p, inst))
      : [el("div", { class: "grid__empty" }, `${marketName(inst.code)} is a close-only series: positions need daily highs and lows. Its long-history statistics are listed below.`)]));
    caption.replaceChildren(
      el("span", {}, `${inst.instrument.name}, last close ${inst.position?.as_of || "–"}`),
      el("span", {}, "Distances are from the last close, in percent and in 14-session ATR. Outcomes come from past periods in the same position."));
    requestAnimationFrame(() => grid.classList.add("is-ready"));
  }

  // ------------------------------------------------------------------ time coordinates
  // Calendar coordinates of the current (or next) session, in the instrument's own clock, paired
  // with the graded statistics for those coordinates. Exchange holidays are not modelled here.
  const DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const MONTH_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function zoned(date, timeZone) {
    const parts = Object.fromEntries(new Intl.DateTimeFormat("en-US", {
      timeZone, year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "numeric", hourCycle: "h23", weekday: "long",
    }).formatToParts(date).map((p) => [p.type, p.value]));
    return { y: +parts.year, m: +parts.month, d: +parts.day, h: +parts.hour, min: +parts.minute, wd: DAY_NAMES.indexOf(parts.weekday) };
  }

  // Exchange sessions published with the report (holidays and early closes from the exchange calendar).
  function sessionClock(now, ahead) {
    const list = (ahead?.sessions || []).map((s) => ({ ...s, open: new Date(s.open_utc), close: new Date(s.close_utc) }));
    const cur = list.find((s) => s.open <= now && now < s.close);
    const next = cur || list.find((s) => s.open > now);
    if (!next) return null;
    const pad = (n) => String(n).padStart(2, "0");
    const t = zoned(now, "America/New_York");
    const c = zoned(next.close, "America/New_York");
    const minutes = t.h * 60 + t.min;
    const closes = next.early_close ? `, closing early at ${pad(c.h)}:${pad(c.min)} New York` : "";
    const day = new Date(`${next.date}T12:00:00Z`);
    const today = next.date === `${t.y}-${pad(t.m)}-${pad(t.d)}`;
    const label = cur
      ? `Regular session in progress, ${pad(t.h)}:${pad(t.min)} New York${closes}`
      : today ? `Before the open; next: today's regular session${closes}` : `Market closed; next session ${DAY_NAMES[day.getUTCDay()]}${closes}`;
    return {
      open: Boolean(cur), label, early: Boolean(next.early_close),
      session: cur ? (minutes < 630 ? "Opening hour" : minutes < 900 ? "Midday" : "Closing hour") : "Opening hour",
      slot: cur ? `${pad(t.h)}:${t.min < 30 ? "00" : "30"} ET` : "09:30 ET",
      weekday: DAY_NAMES[day.getUTCDay()], month: MONTH_SHORT[day.getUTCMonth()], dom: day.getUTCDate(), y: day.getUTCFullYear(), m: day.getUTCMonth() + 1,
      closeText: next.early_close ? `${pad(c.h)}:${pad(c.min)}` : null,
    };
  }

  function equityClock(now, ahead) {
    const fromCalendar = sessionClock(now, ahead);
    if (fromCalendar) return fromCalendar;
    const t = zoned(now, "America/New_York");
    const minutes = t.h * 60 + t.min;
    let day = new Date(now);
    let wd = t.wd;
    let session, label, open = false;
    const weekend = wd === 0 || wd === 6;
    if (!weekend && minutes >= 570 && minutes < 960) {
      open = true;
      session = minutes < 630 ? "Opening hour" : minutes < 900 ? "Midday" : "Closing hour";
      label = `Regular session in progress, ${String(t.h).padStart(2, "0")}:${String(t.min).padStart(2, "0")} New York`;
    } else {
      // next session: today if before the open on a weekday, otherwise the next weekday
      let add = !weekend && minutes < 570 ? 0 : 1;
      while ([0, 6].includes((wd + add) % 7)) add += 1;
      day = new Date(now.getTime() + add * 864e5);
      wd = (wd + add) % 7;
      session = "Opening hour";
      label = add === 0 ? "Before the open; next: today's regular session" : `Market closed; next session ${DAY_NAMES[wd]}`;
    }
    const z = zoned(day, "America/New_York");
    const slot = open ? `${String(t.h).padStart(2, "0")}:${t.min < 30 ? "00" : "30"} ET` : "09:30 ET";
    return { open, session, label, slot, weekday: DAY_NAMES[wd], month: MONTH_SHORT[z.m - 1], dom: z.d, y: z.y, m: z.m };
  }

  const offsetMinutes = (now, tz) => {
    const z = zoned(now, tz);
    return Math.round((Date.UTC(z.y, z.m - 1, z.d, z.h, z.min) - Math.floor(now.getTime() / 60000) * 60000) / 60000);
  };

  function cryptoClock(now) {
    const u = zoned(now, "UTC");
    const utcMin = u.h * 60 + u.min;
    const london = utcMin + offsetMinutes(now, "Europe/London");
    const newYork = utcMin + offsetMinutes(now, "America/New_York");
    const session = london < 480 ? "Asia" : newYork < 540 ? "London" : newYork < 960 ? "New York" : "Late US";
    const hh = String(u.h).padStart(2, "0");
    return { open: true, session, label: `Trading around the clock; ${hh}:${String(u.min).padStart(2, "0")} UTC`, hour: `${hh}:00 UTC`,
      weekday: DAY_NAMES[u.wd], month: MONTH_SHORT[u.m - 1], dom: u.d, y: u.y, m: u.m };
  }

  const findCard = (inst, suffix) => cardsOf(inst).find((c) => c.id === `${inst.code}.${suffix}`);
  const findItem = (card, pred) => card?.items.find(pred) || null;

  function fact(card, item, text) {
    if (!card || !item) return null;
    return { text, value: fmt(item.estimate, card.unit), grade: item.grade, href: `#${card.id.replaceAll(".", "-")}`, control: card.contrast || "control" };
  }

  // How much price moves at this coordinate against the average one (volatility clock).
  function volFact(card, item, text) {
    if (!card || !item) return null;
    const x = item.extra || {};
    const typical = x.typical_move_pct ?? x.typical_range_pct;
    const est = Math.round(item.estimate ?? 0);
    const tail = typical !== undefined ? `; typical ${x.typical_move_pct !== undefined ? "move" : "range"} ${typical.toFixed(2)}%` : "";
    return { text: `${text}${tail}`, value: `${est > 0 ? "+" : ""}${est === 0 ? 0 : est}%`, grade: item.grade, href: `#${card.id.replaceAll(".", "-")}` };
  }

  // Where the day's high and low form, by session window: bars are observed shares, the line across
  // each bar is the random-walk control. The current (or next) window is marked.
  function extremesChart(hi, lo, current, { w = 260, h = 96 } = {}) {
    if (!hi?.items?.length || !lo?.items?.length) return null;
    const groups = hi.items.map((it, i) => ({ label: it.label, high: it, low: lo.items[i] })).filter((g) => g.low);
    const vals = groups.flatMap((g) => [g.high.observed, g.high.baseline, g.low.observed, g.low.baseline]).filter((v) => v !== null && v !== undefined);
    if (!vals.length) return null;
    const max = Math.max(...vals) * 1.15;
    const padT = 14, padB = 18;
    const y = (v) => padT + (1 - v / max) * (h - padT - padB);
    const band = w / groups.length;
    const bw = Math.min(16, band * 0.24);
    const root = svg("svg", { viewBox: `0 0 ${w} ${h}`, class: "extremes", role: "img", "aria-label": "Share of days whose high (H) and low (L) form in each session window, against a random walk" });
    root.append(svg("line", { x1: 0, x2: w, y1: y(0), y2: y(0), class: "profile__zero" }));
    groups.forEach((g, i) => {
      const now = g.label.startsWith(current);
      const cx = i * band + band / 2;
      [["H", g.high], ["L", g.low]].forEach(([k, it], j) => {
        if (it.observed === null || it.observed === undefined) return;
        const x = cx + (j === 0 ? -bw - 3 : 3);
        const r = svg("rect", { x, y: y(it.observed), width: bw, height: Math.max(1, y(0) - y(it.observed)), rx: 1, fill: gradeFill(it.grade), class: now ? "is-now" : "" });
        const t = svg("title"); t.textContent = `${k === "H" ? "Day high" : "Day low"} in ${it.label}: ${it.observed.toFixed(0)}% of days against ${it.baseline?.toFixed(0)}% in a random walk, grade ${it.grade}`; r.append(t);
        root.append(r);
        if (it.baseline !== null && it.baseline !== undefined) root.append(svg("line", { x1: x - 3, x2: x + bw + 3, y1: y(it.baseline), y2: y(it.baseline), class: "extremes__ctl" }));
        const lab = svg("text", { x: x + bw / 2, y: y(Math.max(it.observed, it.baseline ?? 0)) - 4, "text-anchor": "middle", class: "extremes__k" }); lab.textContent = k; root.append(lab);
      });
      const lab = svg("text", { x: cx, y: h - 5, "text-anchor": "middle", class: now ? "is-now" : "" }); lab.textContent = shortLabel(g.label); root.append(lab);
    });
    return root;
  }

  function timeCoordinates(inst, now = new Date()) {
    const crypto = inst.instrument.calendar === "24/7";
    const clk = crypto ? cryptoClock(now) : equityClock(now, inst.sessions_ahead);
    const starts = (label) => (l) => l.label.startsWith(label);
    const coords = [];
    // session
    const hi = findCard(inst, "sessions.day_high"), lo = findCard(inst, "sessions.day_low");
    const sessionFacts = [
      fact(hi, findItem(hi, starts(clk.session)), "Day high forms in this window, against a random walk"),
      fact(lo, findItem(lo, starts(clk.session)), "Day low forms in this window, against a random walk"),
    ];
    if (crypto) {
      const hr = findCard(inst, "intraday.hour");
      sessionFacts.push(fact(hr, findItem(hr, (l) => l.label === clk.hour), `Return in the ${clk.hour} hour, versus ${hr?.contrast || "the other hours"}`));
    } else {
      const ov = findCard(inst, "intraday.overnight");
      if (!clk.open) sessionFacts.push(fact(ov, findItem(ov, starts("Overnight (")), "Overnight return, prior close to open, versus zero"));
    }
    const vh = crypto ? findCard(inst, "volatility.hour") : findCard(inst, "volatility.halfhour");
    sessionFacts.unshift(volFact(vh, findItem(vh, (l) => l.label === (crypto ? clk.hour : clk.slot)),
      crypto ? `Movement in the ${clk.hour} hour against the average hour` : `Movement in the ${clk.slot} half-hour against the average half-hour`));
    coords.push({ name: "Session", value: clk.session, note: clk.label, facts: sessionFacts, chart: extremesChart(hi, lo, clk.session) });
    // weekday
    const wh = findCard(inst, "weekly.week_high"), wl = findCard(inst, "weekly.week_low"), wd = findCard(inst, "calendar.weekday");
    const small = (card, key, opts = {}) => (card?.items?.length
      ? profileChart(card.items, { highlight: card.items.findIndex((l) => l.label === key), w: 260, h: 84, ...opts }) : null);
    coords.push({ name: "Day of the week", value: clk.weekday, note: crypto ? "" : clk.open ? "Today" : "Next session",
      chart: small(findCard(inst, "volatility.weekday"), clk.weekday, { name: "day" }), facts: [
      volFact(findCard(inst, "volatility.weekday"), findItem(findCard(inst, "volatility.weekday"), (l) => l.label === clk.weekday), `Movement on ${clk.weekday}s against the average day`),
      fact(wh, findItem(wh, (l) => l.label === clk.weekday), "Week high forms on this day, against a random walk"),
      fact(wl, findItem(wl, (l) => l.label === clk.weekday), "Week low forms on this day, against a random walk"),
      fact(wd, findItem(wd, (l) => l.label === clk.weekday), `Return on ${clk.weekday}, versus ${wd?.contrast || "the other days"}`),
    ] });
    // month
    const mo = findCard(inst, "calendar.month"), tom = findCard(inst, "calendar.turn_of_month");
    const lastDay = new Date(Date.UTC(clk.y, clk.m, 0)).getUTCDate();
    const inTurn = clk.dom <= 3 || clk.dom === lastDay;
    const vm = findCard(inst, "volatility.month"), vw = findCard(inst, "volatility.week_of_month");
    const wom = ["Days 1–7", "Days 8–14", "Days 15–21", "Days 22–28", "Days 29–31"][Math.min(4, Math.floor((clk.dom - 1) / 7))];
    const monthFacts = [
      volFact(vm, findItem(vm, (l) => l.label === clk.month), `Movement in ${clk.month} against the average day`),
      volFact(vw, findItem(vw, (l) => l.label === wom), `Movement in ${wom.toLowerCase()} of the month`),
      fact(mo, findItem(mo, (l) => l.label === clk.month), `Return in ${clk.month}, versus ${mo?.contrast || "the other months"}`),
    ];
    if (tom && inTurn) monthFacts.push(fact(tom, tom.items[0], `Turn-of-month days, versus ${tom?.contrast || "the other days"}`));
    // when in the month (and quarter) the lowest and highest close form, against the same days in random order
    const ml = findCard(inst, "extremes.month_low"), mh = findCard(inst, "extremes.month_high");
    const capNote = (card) => (card?.state?.periods < 200 ? "; B at best with this history" : "");
    const monthWindow = (st) => {
      if (!st?.sessions_elapsed || !st?.typical_sessions) return null;
      const edge = crypto ? 7 : 5;
      return st.sessions_elapsed <= edge ? "First week" : st.sessions_elapsed > st.typical_sessions - edge ? "Last week" : "Middle";
    };
    const mw = monthWindow(ml?.state);
    if (mw) {
      monthFacts.push(fact(ml, findItem(ml, (l) => l.label === mw), `Month's lowest close forms in this part (${mw.toLowerCase()}), against the same days in random order${capNote(ml)}`));
      monthFacts.push(fact(mh, findItem(mh, (l) => l.label === mw), `Month's highest close forms in this part, against the same days in random order${capNote(mh)}`));
    }
    coords.push({ name: "Month", value: `${clk.month}, day ${clk.dom}`,
      note: [!clk.open && "Next session", inTurn && "inside the turn-of-month window"].filter(Boolean).join(", ").replace(/^i/, "I"), facts: monthFacts,
      chart: small(vm, clk.month, { name: "month", label: (l) => l.charAt(0) }) });
    // quarter and year progress from the position block
    const q = (inst.position?.horizons || []).find((p) => p.horizon === "quarter");
    const yr = (inst.position?.horizons || []).find((p) => p.horizon === "year");
    const mapQ = cardsOf(inst).find((c) => c.family === "map" && c.state?.horizon === "quarter");
    const mapY = cardsOf(inst).find((c) => c.family === "map" && c.state?.horizon === "year");
    const prog = (m) => (m?.state?.typical_sessions ? `${m.state.sessions_elapsed} of about ${m.state.typical_sessions} ${m.state.session_unit || "sessions"}` : "");
    const vq = findCard(inst, "volatility.quarter");
    const qLabel = `Q${Math.floor((clk.m - 1) / 3) + 1}`;
    const qFacts = [volFact(vq, findItem(vq, (l) => l.label === qLabel), `Movement in ${qLabel} against the average day`)];
    const ql = findCard(inst, "extremes.quarter_low");
    const qWindow = ["1st month", "2nd month", "3rd month"][(clk.m - 1) % 3];
    if (ql) qFacts.push(fact(ql, findItem(ql, (l) => l.label === qWindow), `Quarter's lowest close forms in its ${qWindow}, against the same days in random order${capNote(ql)}`));
    coords.push({ name: "Quarter and year", value: q?.period || "–",
      note: [prog(mapQ) && `Quarter: ${prog(mapQ)}`, prog(mapY) && `Year ${yr?.period}: ${prog(mapY)}`].filter(Boolean).join(". "), facts: qFacts, link: "#space",
      chart: small(vq, qLabel, { name: "quarter" }) });
    return { clock: clk, coords };
  }

  function renderTime(inst) {
    const box = document.getElementById("time-coords");
    if (!inst || inst.status !== "ok") { box.replaceChildren(); return; }
    const { coords } = timeCoordinates(inst);
    box.replaceChildren(...coords.map((c) => el("div", { class: "coord" },
      el("div", { class: "coord__name" }, c.name),
      el("div", { class: "coord__value" }, c.value),
      c.note ? el("div", { class: "coord__note" }, c.note) : null,
      c.chart ? el("div", { class: "coord__chart" }, c.chart) : null,
      el("ul", { class: "coord__facts" }, ...c.facts.filter(Boolean).map((f) => el("li", { class: f.grade === "N/A" ? "is-thin" : "" },
        el("a", { href: f.href }, el("span", { class: "coord__fact" }, f.text), el("span", { class: "coord__fig" }, f.value), gradeTag(f.grade, null))))),
      c.link ? el("a", { class: "coord__more", href: c.link }, "Position against prior quarters and years") : null)));
  }

  // ------------------------------------------------------------------ at a glance
  // Five questions a trader asks before acting, each answered with one figure, one visual and its
  // grade. Observed values are drawn as bars and their control as a thin line, everywhere.
  const gradeFill = (g) => `var(--${gradeClass(g)})`;
  const rel = (v) => (v === null || v === undefined ? "–" : `${Math.round(v) > 0 ? "+" : ""}${Math.round(v)}%`);
  const WEEKDAY_SHORT = { Sunday: "Sun", Monday: "Mon", Tuesday: "Tue", Wednesday: "Wed", Thursday: "Thu", Friday: "Fri", Saturday: "Sat" };
  const dayLabel = (iso) => {
    if (!iso) return "–";
    const d = new Date(`${iso}T12:00:00Z`);
    return `${WEEKDAY_SHORT[DAY_NAMES[d.getUTCDay()]]} ${d.getUTCDate()} ${MONTH_SHORT[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
  };

  // Movement by slot against the average slot: the zero line is the control.
  function profileChart(items, { highlight = -1, every = 1, w = 340, h = 120, label = shortLabel, name = "slot" } = {}) {
    const padT = 20, padB = 20;
    const max = Math.max(10, ...items.map((i) => Math.abs(i.estimate ?? 0))) * 1.12;
    const y = (v) => padT + ((max - v) / (2 * max)) * (h - padT - padB);
    const band = w / items.length;
    const bw = Math.max(2, band * 0.68);
    const now = items[highlight];
    const root = svg("svg", { viewBox: `0 0 ${w} ${h}`, class: "profile", role: "img",
      "aria-label": `Movement by ${name} against the average ${name}${now ? `; ${now.label} ${rel(now.estimate)}` : ""}` });
    root.append(svg("line", { x1: 0, x2: w, y1: y(0), y2: y(0), class: "profile__zero" }));
    items.forEach((it, i) => {
      const v = it.estimate ?? 0;
      const x = i * band + (band - bw) / 2;
      const top = y(Math.max(0, v)), bottom = y(Math.min(0, v));
      const r = svg("rect", { x, y: top, width: bw, height: Math.max(1, bottom - top), rx: 1, fill: gradeFill(it.grade), class: i === highlight ? "is-now" : "" });
      const t = svg("title");
      t.textContent = `${it.label}: ${rel(v)} against the average ${name}, grade ${it.grade}`;
      r.append(t);
      root.append(r);
      const crowded = i !== highlight && highlight >= 0 && Math.abs(i - highlight) < every;
      if (i === highlight || (i % every === 0 && !crowded)) {
        const lab = svg("text", { x: x + bw / 2, y: h - 5, "text-anchor": "middle", class: i === highlight ? "is-now" : "" });
        lab.textContent = label(it.label);
        root.append(lab);
      }
    });
    if (now) {
      const cx = Math.max(16, Math.min(w - 16, highlight * band + band / 2));
      const reach = Math.ceil(16 / band);  // neighbours under the label's width
      const near = items.slice(Math.max(0, highlight - reach), highlight + reach + 1).map((i) => Math.max(0, i.estimate ?? 0));
      const t = svg("text", { x: cx, y: Math.max(11, y(Math.max(...near, 0)) - 6), "text-anchor": "middle", class: "profile__value" });
      const v = now.estimate ?? 0;
      t.textContent = rel(v);
      root.append(t);
    }
    return root;
  }

  // Observed value as a bar, control as a thin line across it.
  function bullet(observed, control, max, grade) {
    const at = (v) => `${Math.max(0, Math.min(100, (v / max) * 100)).toFixed(1)}%`;
    return el("div", { class: "bullet", "aria-hidden": "true" },
      el("span", { class: "bullet__bar", style: `width:${at(observed)};background:${gradeFill(grade)}` }),
      control === null || control === undefined ? null : el("span", { class: "bullet__tick", style: `left:${at(control)}` }));
  }

  const shortContrast = (c) => (c || "control").replace(/^(the|a|an) /, "").replace(/^equally distant /, "");

  function evidenceBullet(card, item, { title, href, control } = {}) {
    if (!item || item.observed === null || item.observed === undefined || item.baseline === null || item.baseline === undefined) return null;
    const vol = card.family === "volatility", atr = card.unit === "ATR";
    const max = vol ? Math.max(item.observed, item.baseline) * 1.25 : 100;
    const f = (v) => (atr ? `${signed(v, 2)} ATR` : vol ? `${v.toFixed(2)}%` : `${v.toFixed(0)}%`);
    const body = [
      el("div", { class: "ev__top" },
        el("span", { class: "ev__title" }, title || item.label),
        el("span", { class: "ev__grade" }, meter(item.grade, confidence(card, item.grade)), item.grade)),
      atr ? dbar(item.observed, item.baseline, Math.max(0.5, Math.abs(item.observed), Math.abs(item.baseline)) * 1.1, item.grade)
        : bullet(item.observed, item.baseline, max, item.grade),
      el("div", { class: "ev__vals" },
        el("span", {}, el("b", {}, f(item.observed)), " observed"),
        el("span", {}, `${f(item.baseline)} ${control || shortContrast(card.contrast)}`))];
    return href ? el("a", { class: "ev", href }, ...body) : el("div", { class: "ev" }, ...body);
  }

  function gauge(p) {
    return el("div", { class: "gauge-wrap" },
      el("div", { class: "gauge", role: "img", "aria-label": `Higher than ${p.toFixed(0)}% of past sessions` },
        el("span", { class: "gauge__normal" }),
        el("span", { class: "gauge__mark", style: `left:${Math.max(0, Math.min(100, p)).toFixed(1)}%` })),
      el("div", { class: "gauge__scale" }, el("span", {}, "Calmer"), el("span", {}, "Middle half of history"), el("span", {}, "More volatile")));
  }

  const tile = (cls, question, ...children) => el("article", { class: `tile ${cls}`, id: cls.split(" ")[0].replace("tile--", "tile-") }, el("h3", { class: "tile__q" }, question), ...children);
  const figure = (value, sub, extra = null) =>
    el("div", { class: "tile__head" }, el("div", { class: "tile__fig" }, value), el("div", { class: "tile__sub" }, sub), extra);

  // Magnitudes on one scale: the size of a normal bar, of the busiest bar, of a normal day, and today's ATR.
  function moveLadder(rows) {
    const max = Math.max(...rows.map((r) => r.value)) * 1.04;
    return el("div", { class: "ladder-rows" }, ...rows.sort((a, b) => a.value - b.value).map((r) =>
      el("div", { class: `mrow${r.now ? " mrow--now" : ""}`, title: r.title || "" },
        el("span", { class: "mrow__label" }, r.label),
        el("span", { class: "mrow__track" }, el("span", { class: "mrow__fill", style: `width:${((r.value / max) * 100).toFixed(1)}%` })),
        el("span", { class: "mrow__v" }, `${r.value.toFixed(2)}%`))));
  }

  function tileMove(inst, clk, unit, crypto) {
    const p = inst.position || {};
    if (p.atr_pct === null || p.atr_pct === undefined) return null;
    const vw = findCard(inst, "volatility.weekday");
    const vc = crypto ? findCard(inst, "volatility.hour") : findCard(inst, "volatility.halfhour");
    const since = String(inst.coverage?.daily?.start || inst.coverage?.intraday?.start || p.atr_history_from || "").slice(0, 4);
    const rows = [{ label: `ATR now, 14 ${unit}`, value: p.atr_pct, now: true }];
    if (vw?.items?.length) {
      const n = vw.items.reduce((s, i) => s + (i.n || 0), 0);
      const avgRange = vw.items.reduce((s, i) => s + (i.extra?.typical_range_pct ?? 0) * (i.n || 0), 0) / (n || 1);
      const avgMove = vw.items[0].extra?.average_move_pct;
      if (avgRange > 0) rows.push({ label: "Average day, high to low", value: avgRange, key: "range", title: `Mean true range since ${since}, including gaps` });
      if (avgMove) rows.push({ label: "Average day, close to close", value: avgMove, title: `Mean absolute daily change since ${since}` });
    }
    if (vc?.items?.length) {
      const slot = crypto ? "hour" : "half-hour";
      const busiest = [...vc.items].sort((a, b) => b.estimate - a.estimate)[0];
      rows.push({ label: `Average ${slot}`, value: vc.items[0].extra?.average_range_pct ?? vc.items[0].baseline, title: `Mean high-to-low range of a ${slot}` });
      rows.push({ label: `${busiest.label}, busiest`, value: busiest.extra?.typical_range_pct ?? busiest.observed, title: `Mean high-to-low range of the ${busiest.label} ${slot}` });
    }
    const pctl = p.atr_percentile;
    const avg = rows.find((r) => r.key === "range");
    const regime = pctl !== null && pctl !== undefined
      ? `Higher than ${pctl.toFixed(0)}% of ${unit} since ${String(p.atr_history_from).slice(0, 4)}; the median is ${p.atr_median_pct.toFixed(2)}%.`
      : avg ? `${p.atr_pct < avg.value ? "Calmer" : "More volatile"} than the average day since ${since}: ${p.atr_pct.toFixed(2)}% against ${avg.value.toFixed(2)}%.` : null;
    const day = findItem(vw, (l) => l.label === clk.weekday);
    const dayFact = day && ["A", "B"].includes(day.grade)
      ? el("a", { class: "tile__fact", href: `#${vw.id.replaceAll(".", "-")}` },
          el("span", {}, `${clk.weekday}s move ${rel(day.estimate)} against the average day`),
          el("span", { class: "tile__factfig" }, `${day.extra?.typical_move_pct?.toFixed(2)}%`), gradeTag(day.grade, confidence(vw, day.grade)))
      : null;
    return tile("tile--move", "How far does it move?",
      figure(`${p.atr_pct.toFixed(2)}%`, `Average daily range over the last 14 ${unit} (ATR)`),
      pctl === null || pctl === undefined ? null : gauge(pctl),
      regime ? el("p", { class: "tile__line tile__line--strong" }, regime) : null,
      moveLadder(rows.filter((r) => r.value > 0)),
      dayFact);
  }

  const sessionPhrase = (label) => {
    const name = label.replace(/\s*\(.*\)$/, "");
    if (name === "Midday") return "at midday";
    if (/hour$/.test(name)) return `in the ${name.toLowerCase()}`;
    return `in the ${name} session`;
  };

  // A short, plain title for a graded effect, built from its card and item.
  function effectTitle(card, item) {
    const label = item.label.replace(/\s*\(.*\)$/, "");
    const id = card.id;
    if (card.family === "volatility") {
      if (id.endsWith(".halfhour")) return `Range in the ${label} half-hour`;
      if (id.endsWith(".hour")) return `Range in the ${label} hour`;
      if (id.endsWith(".weekday")) return `Daily move on ${label}s`;
      if (id.endsWith(".week_of_month")) return `Daily move on ${label.toLowerCase()} of the month`;
      return `Daily move in ${label}`;
    }
    if (card.family === "sessions" && /day_(high|low)$/.test(id)) return `Day ${id.endsWith("high") ? "high" : "low"} forms ${sessionPhrase(item.label)}`;
    if (card.family === "weekly") return `Week ${id.endsWith("high") ? "high" : "low"} forms on ${label}`;
    if (card.family === "extremes") return `${capital(card.state?.scope || "month")}'s ${id.endsWith("high") ? "highest" : "lowest"} close in the ${label.toLowerCase()}`;
    if (card.family === "money") return `${capital(card.state?.horizon || "period")}: ${(MONEY_TITLES[item.extra?.outcome] || label).toLowerCase()}`;
    if (card.family === "plan_regime") return `${capital(card.state?.horizon || "period")} started ${card.state?.regime}: ${(PLAN_ROWS.find(([k]) => k === item.extra?.plan)?.[1] || label).toLowerCase()}`;
    if (card.family === "plan") return `${capital(card.state?.horizon || "period")}: ${(PLAN_ROWS.find(([k]) => k === item.extra?.plan)?.[1] || label).toLowerCase()}`;
    if (card.family === "revisits") {
      const h = id.split(".").pop();
      return `Prior ${h}'s ${label.charAt(0).toLowerCase()}${label.slice(1)}`;
    }
    return `${card.title}: ${label}`;
  }

  function tileWhen(inst, clk, crypto) {
    const vc = crypto ? findCard(inst, "volatility.hour") : findCard(inst, "volatility.halfhour");
    if (!vc || !vc.items.length) return null;
    const key = crypto ? clk.hour : clk.slot;
    const k = vc.items.findIndex((i) => i.label === key);
    const now = vc.items[k];
    const sorted = [...vc.items].sort((a, b) => b.estimate - a.estimate);
    const hi = findCard(inst, "sessions.day_high"), lo = findCard(inst, "sessions.day_low");
    const win = (card) => findItem(card, (l) => l.label.startsWith(clk.session));
    const when = crypto ? "now" : clk.open ? "now" : "when the next session opens";
    const slot = crypto ? "hour" : "half-hour";
    const pair = [[hi, win(hi)], [lo, win(lo)]].map(([c, it]) => (c && it ? evidenceBullet(c, it, { title: effectTitle(c, it), href: `#${c.id.replaceAll(".", "-")}` }) : null)).filter(Boolean);
    return tile("tile--when tile--wide", "When does it move?",
      el("div", { class: "when" },
        figure(now ? rel(now.estimate) : "–", now ? `Range in the ${now.label} ${slot}, ${when}, against the average ${slot}` : "",
          now ? gradeTag(now.grade, confidence(vc, now.grade)) : null),
        el("div", { class: "when__chart" },
          profileChart(vc.items, { highlight: k, every: crypto ? (narrow() ? 4 : 3) : narrow() ? 3 : 2, w: narrow() ? 340 : 480, h: 132, name: slot }),
          el("p", { class: "tile__line" }, `Busiest ${sorted[0].label} (${rel(sorted[0].estimate)}), quietest ${sorted.at(-1).label} (${rel(sorted.at(-1).estimate)}). Each bar: range against the average ${slot}, coloured by grade.`))),
      pair.length ? el("div", { class: "tile__pair" }, ...pair) : null);
  }

  function tilePosition(inst, unit) {
    const rows = (inst.position?.horizons || []).filter((p) => ["week", "month", "quarter"].includes(p.horizon));
    if (!rows.length) return null;
    return tile("tile--stand", "Where does it stand?",
      el("div", { class: "pos" }, ...rows.map((p) => {
        const pos = p.range_position_pct;
        const x = pos === null || pos === undefined ? null : Math.max(-45, Math.min(145, pos));
        const zone = x === null ? "" : pos > 100 ? "above" : pos < 0 ? "below" : "inside";
        return el("div", { class: "pos__row" },
          el("div", { class: "pos__h" }, el("b", {}, capital(p.horizon)), el("span", {}, p.status === "closed" ? "next, against the one just closed" : `against ${p.reference}`)),
          el("div", { class: `range range--${zone}`, role: "img", "aria-label": `Last close at ${pos === null ? "an unknown point" : `${pos.toFixed(0)}%`} of the ${p.reference} range` },
            el("span", { class: "range__band" }), el("span", { class: "range__edge range__edge--low" }), el("span", { class: "range__edge range__edge--high" }),
            x === null ? null : el("span", { class: "range__mark", style: `left:${(25 + x * 0.5).toFixed(1)}%` })),
          el("div", { class: "pos__v" }, pos === null || pos === undefined ? "–" : `${pos.toFixed(0)}%`),
          el("div", { class: "pos__atr" }, `Low ${signed(p.to_reference_low_atr, 1)} ATR`, el("span", {}, `High ${signed(p.to_reference_high_atr, 1)} ATR`)));
      })),
      el("p", { class: "tile__line" }, `Last close within each prior range: 0% at its low, 100% at its high. Distances in ATR, the average daily range.`),
      el("a", { class: "tile__more", href: "#space" }, "All horizons and what followed"));
  }

  // Every untested level on one axis, in ATR from the last close; the shaded band is one normal day.
  const narrow = () => window.matchMedia("(max-width: 720px)").matches;

  function levelMap(levels, atr) {
    const small = narrow();
    const w = small ? 360 : 720, h = 98, padL = 14, padR = 14, axis = 40, span = 4;
    const x = (a) => padL + ((Math.max(-span, Math.min(span, a)) + span) / (2 * span)) * (w - padL - padR);
    const root = svg("svg", { viewBox: `0 0 ${w} ${h}`, class: "lmap", role: "img", "aria-label": "Untested levels by distance from the last close, in ATR" });
    root.append(svg("rect", { x: x(-1), y: axis - 34, width: x(1) - x(-1), height: 68, rx: 3, class: "lmap__day" }));
    root.append(svg("line", { x1: padL, x2: w - padR, y1: axis, y2: axis, class: "lmap__axis" }));
    for (let t = -3; t <= 3; t++) {
      root.append(svg("line", { x1: x(t), x2: x(t), y1: axis - 3, y2: axis + 3, class: "lmap__tick" }));
      const lab = svg("text", { x: x(t), y: h - 6, "text-anchor": "middle" });
      lab.textContent = t === 0 ? "Close" : `${t > 0 ? "+" : ""}${t}${small ? "" : " ATR"}`;
      root.append(lab);
    }
    root.append(svg("line", { x1: x(0), x2: x(0), y1: axis - 34, y2: axis + 34, class: "lmap__close" }));

    const inside = levels.filter((l) => l.distance_atr !== null && Math.abs(l.distance_atr) <= span)
      .sort((p, q) => Math.abs(p.distance_atr) - Math.abs(q.distance_atr));
    const placed = { high: [], low: [] };
    for (const l of inside) {
      const r = 4 + Math.min(3, ((l.confluence || 1) - 1) * 1.5);
      const cx = x(l.distance_atr);
      const side = l.side === "high" ? "high" : "low";
      let level = 0;
      while (placed[side].some((p) => p.level === level && Math.abs(p.cx - cx) < p.r + r + 2) && level < 2) level += 1;
      placed[side].push({ cx, r, level });
      const cy = side === "high" ? axis - 9 - level * 11 : axis + 9 + level * 11;
      const c = svg("circle", { cx, cy, r, class: `lmap__dot lmap__dot--${l.side}` });
      const t = svg("title");
      t.textContent = `${levelName(l)}, ${l.period}: ${signed(l.distance_pct)}% (${signed(l.distance_atr, 1)} ATR); reached within 20 in ${l.reach?.within?.["20"]?.pct ?? "–"}% of past cases`;
      c.append(t);
      root.append(c);
    }
    const beyond = levels.filter((l) => l.distance_atr !== null && Math.abs(l.distance_atr) > span).length;
    return el("figure", { class: "lmap-wrap" }, root,
      el("figcaption", { class: "tile__line" },
        `Highs above the line, lows below; larger dots are levels shared by several horizons. Shaded: one normal day, ±1 ATR${atr ? ` (±${atr.toFixed(2)}%)` : ""}.${beyond ? ` ${beyond} more ${beyond === 1 ? "level lies" : "levels lie"} beyond ±4 ATR.` : ""}`));
  }

  function tileLevels(inst, unit) {
    const levels = inst.open_levels?.levels || [];
    if (!levels.length) return null;
    const above = levels.find((l) => l.distance_pct > 0);
    const below = levels.find((l) => l.distance_pct < 0);
    const block = (l, word) => {
      if (!l) return el("div", { class: "lvl lvl--none" }, `No untested ${word} in the published range.`);
      const half = l.reach?.typical_sessions;
      return el("div", { class: `lvl lvl--${l.side}` },
        el("div", { class: "lvl__top" },
          el("b", {}, levelName(l)),
          el("span", { class: "lvl__dist" }, `${signed(l.distance_pct)}%`, el("span", {}, `${signed(l.distance_atr, 1)} ATR`))),
        el("div", { class: "lvl__sub" }, `${l.period}, untested for ${l.age_sessions === 0 ? "less than a day" : `${num(l.age_sessions)} ${l.age_sessions === 1 ? unit.slice(0, -1) : unit}`}`),
        el("div", { class: "odds" }, ...["5", "20", "60"].map((k) => {
          const o = l.reach?.within?.[k];
          return el("div", { class: "odds__cell", title: o ? `95% interval ${o.ci_low}–${o.ci_high}%, ${num(o.n)} past starting points` : "" },
            el("span", { class: "odds__k" }, `${k} ${unit}`),
            el("span", { class: "odds__track" }, el("span", { class: "odds__fill", style: `width:${o?.pct ?? 0}%` })),
            el("span", { class: "odds__v" }, o?.pct === null || o?.pct === undefined ? "–" : `${o.pct.toFixed(0)}%`));
        })),
        el("div", { class: "lvl__note" }, half ? `Half of past cases got there within ${half} ${half === 1 ? unit.slice(0, -1) : unit}.` : `Fewer than half of past cases got there within 120 ${unit}.`));
    };
    return tile("tile--levels", "Which levels are in reach?",
      levelMap(levels, inst.open_levels?.atr_pct),
      el("div", { class: "lvl-pair" }, block(above, "high above"), block(below, "low below")),
      el("p", { class: "tile__line" }, `How often price has travelled that far within 5, 20 and 60 ${unit}, from every past ${unit.slice(0, -1)} at the same volatility-scaled distance.`),
      el("a", { class: "tile__more", href: "#open-levels" }, "All untested levels"));
  }

  // Typical move from here to the period's end: median excursion below (left) and above (right) the
  // close, interquartile whiskers, and the other periods' medians as thin control lines.
  function moneyFan(same, others, atr) {
    const small = narrow();
    const w = small ? 340 : 560, h = 92, mid = w / 2, bar = 14, cy = 44;
    const val = (g, k, q = "median") => g?.[k]?.[q];
    const span = Math.max(2, val(same, "up_atr", "q3") ?? 0, val(same, "down_atr", "q3") ?? 0) * 1.12;
    const x = (a) => mid + (a / span) * (mid - 12);
    const root = svg("svg", { viewBox: `0 0 ${w} ${h}`, class: "fan", role: "img",
      "aria-label": `Median move above the close ${val(same, "up_atr")?.toFixed(2)} ATR, below ${val(same, "down_atr")?.toFixed(2)} ATR` });
    for (let t = -Math.floor(span); t <= Math.floor(span); t++) {
      root.append(svg("line", { x1: x(t), x2: x(t), y1: cy - 22, y2: cy + 22, class: t === 0 ? "fan__close" : "fan__grid" }));
      const lab = svg("text", { x: x(t), y: h - 6, "text-anchor": "middle" });
      lab.textContent = t === 0 ? "Close" : `${t > 0 ? "+" : "−"}${Math.abs(t)}${small ? "" : " ATR"}`;
      root.append(lab);
    }
    for (const [side, key, sign] of [["up", "up_atr", 1], ["down", "down_atr", -1]]) {
      const m = val(same, key);
      if (m === undefined || m === null) continue;
      const x0 = x(0), x1 = x(sign * m);
      root.append(svg("rect", { x: Math.min(x0, x1), y: cy - bar / 2, width: Math.abs(x1 - x0), height: bar, rx: 2, class: `fan__bar fan__bar--${side}` }));
      const q1 = val(same, key, "q1"), q3 = val(same, key, "q3");
      if (q1 !== undefined && q3 !== undefined) {
        root.append(svg("line", { x1: x(sign * q1), x2: x(sign * q3), y1: cy, y2: cy, class: "fan__whisker" }));
        for (const q of [q1, q3]) root.append(svg("line", { x1: x(sign * q), x2: x(sign * q), y1: cy - 5, y2: cy + 5, class: "fan__whisker" }));
      }
      const o = val(others, key);
      if (o !== undefined && o !== null) root.append(svg("line", { x1: x(sign * o), x2: x(sign * o), y1: cy - bar / 2 - 5, y2: cy + bar / 2 + 5, class: "fan__ctl" }));
      const lab = svg("text", { x: x(sign * Math.max(m, q3 ?? m)) + sign * 6, y: cy + 4, "text-anchor": sign > 0 ? "start" : "end", class: "fan__value" });
      lab.textContent = `${sign > 0 ? "+" : "−"}${m.toFixed(2)}${atr ? ` (${(m * atr).toFixed(2)}%)` : ""}`;
      if (x(sign * Math.max(m, q3 ?? m)) + sign * 70 > 0 && x(sign * Math.max(m, q3 ?? m)) + sign * 70 < w) root.append(lab);
    }
    return root;
  }

  const MONEY_ROWS = [
    ["up_1", "Reached 1 ATR above"], ["down_1", "Reached 1 ATR below"],
    ["up_2", "Reached 2 ATR above"], ["down_2", "Reached 2 ATR below"],
    ["end_up", "Ended above the close"], ["end_down", "Ended below the close"],
  ];
  const MONEY_TITLES = Object.fromEntries(MONEY_ROWS);

  // Round-trip costs with market or limit orders at the lowest volume tier, each with its source and date
  // (tsip-platform/docs/strategy/BENCHMARK_2026-11-04.md). Descriptive only: no grade uses a cost.
  const COST_PROFILES = {
    crypto: [
      { id: "gross", label: "No costs (gross)", pct: 0, source: "" },
      { id: "binance", label: "Binance spot, 0.10% per side", pct: 0.2, source: "Binance standard spot fee, as summarised by CryptoPotato (2025-10-21)" },
      { id: "binance-bnb", label: "Binance paying in BNB, 0.075% per side", pct: 0.15, source: "Binance standard spot fee with the 25% BNB discount, as summarised by CryptoPotato (2025-10-21)" },
      { id: "coinbase-maker", label: "Coinbase Advanced, limit 0.40% per side", pct: 0.8, source: "Coinbase Advanced lowest tier, maker, as summarised by Datawallet (2026-08-20); Coinbase shows the fee on each order preview" },
      { id: "coinbase-taker", label: "Coinbase Advanced, market 0.60% per side", pct: 1.2, source: "Coinbase Advanced lowest tier, taker, as summarised by Datawallet (2026-08-20); Coinbase shows the fee on each order preview" },
      { id: "kraken-maker", label: "Kraken Pro, limit 0.40% per side", pct: 0.8, source: "Kraken Pro fee schedule, lowest tier, maker (kraken.com, read 2026-11-04)" },
      { id: "kraken-taker", label: "Kraken Pro, market 0.80% per side", pct: 1.6, source: "Kraken Pro fee schedule, lowest tier, taker (kraken.com, read 2026-11-04)" },
    ],
    etf: [
      { id: "gross", label: "No costs (gross)", pct: 0, source: "" },
      { id: "eu-5000", label: "EU broker, EUR 1 per order, EUR 5,000", pct: 0.04, source: "Trade Republic EUR 1.00 and Scalable Capital EUR 0.99 per order (justETF broker comparison, 2026-05-06)" },
      { id: "eu-1000", label: "EU broker, EUR 1 per order, EUR 1,000", pct: 0.2, source: "Trade Republic EUR 1.00 and Scalable Capital EUR 0.99 per order (justETF broker comparison, 2026-05-06)" },
      { id: "eu-500", label: "EU broker, EUR 1 per order, EUR 500", pct: 0.4, source: "Trade Republic EUR 1.00 and Scalable Capital EUR 0.99 per order (justETF broker comparison, 2026-05-06)" },
    ],
  };

  // Share of past periods that ended beyond a cost. The report publishes thresholds in ATR at the start of each
  // period; the cost is converted with the current period's own starting ATR, and the first threshold at or above
  // it is used, so the share shown never flatters the reader's cost.
  function beyondCost(nt, group, side, costAtr) {
    const k = (nt?.atr || []).findIndex((t) => t >= costAtr - 1e-9);
    if (k < 0) return null;
    const v = nt?.[group]?.[side]?.[k];
    return v === undefined ? null : { threshold: nt.atr[k], share: v };
  }

  function loadCost(kind) {
    try {
      const saved = JSON.parse(localStorage.getItem(`tsip.cost.${kind}`) || "null");
      if (saved && typeof saved.pct === "number" && saved.pct >= 0) return saved;
    } catch (e) { /* browser storage unavailable: use the default */ }
    return { id: "gross", pct: 0 };
  }

  function saveCost(kind, value) {
    try { localStorage.setItem(`tsip.cost.${kind}`, JSON.stringify(value)); } catch (e) { /* not kept */ }
  }

  // The comparison group of a money card: all periods at the same point (specification 0006); reports built
  // before 0.2.17 only carry the periods in the other states.
  const ctl = (st) => (st?.all_periods
    ? { key: "all", n: st.all_periods, word: "all" }
    : { key: "others", n: st?.others, word: "other" });

  // A horizon is folded when no item is graded A, B or C; the reason is shown instead of the cells.
  function foldReason(c) {
    const h = c.state.horizon;
    if (c.items.every((i) => i.grade === "N/A")) return `too little history to grade (${num(c.state.analogs)} past ${h}s like this; 30 needed)`;
    return `no reliable difference from ${ctl(c.state).word} ${h}s at the same point (${num(c.state.analogs)} past ${h}s like this)`;
  }

  function tileMoney(inst, unit) {
    const cards = ["week", "month", "quarter"].map((h) => findCard(inst, `money.${h}`)).filter((c) => c && c.items.length);
    if (!cards.length) return null;
    const kind = inst.instrument.calendar === "24/7" ? "crypto" : "etf";
    const cost = loadCost(kind);
    let expanded = false;
    const first = cards[0], st0 = first.state || {};
    const c0 = ctl(st0);
    const same0 = st0.excursions?.same || {}, ctl0 = st0.excursions?.[c0.key] || st0.excursions?.others || {};
    const up0 = same0.up_atr?.median, down0 = same0.down_atr?.median;
    const plural = (n, word) => (n === 1 ? word.slice(0, -1) : word);
    const graded = (c) => c.items.some((i) => ["A", "B", "C"].includes(i.grade));
    const folded = cards.filter((c, k) => k > 0 && !graded(c));
    const move = (st, key, sign) => {
      const m = st.excursions?.same?.[key]?.median;
      if (m === undefined || m === null) return "–";
      const pctv = st.atr_start_pct ? ` (${(m * st.atr_start_pct).toFixed(2)}%)` : "";
      return `${sign}${m.toFixed(2)} ATR${pctv}`;
    };
    const costCell = (c, side) => {
      const nt = c.state.net_thresholds, atr0 = c.state.atr_start_pct, g = ctl(c.state);
      if (!nt?.atr?.length || !atr0) return el("td", {}, "–");
      const costAtr = cost.pct / atr0, h = c.state.horizon;
      const mine = beyondCost(nt, "same", side, costAtr), other = beyondCost(nt, nt[g.key] ? g.key : "others", side, costAtr);
      return mine
        ? el("td", { class: "mcell", title: `Share of past ${h}s like this that ended more than ${mine.threshold} ATR ${side} the close, against ${other ? `${other.share.toFixed(0)}% of ${g.word} ${h}s at the same point` : "no comparison"}; your cost of ${cost.pct.toFixed(2)}% is ${costAtr.toFixed(2)} ATR at this ${h}'s starting ATR of ${atr0.toFixed(2)}% (descriptive, not graded)` },
          el("span", { class: "mcell__top" }, el("b", {}, `${mine.share.toFixed(0)}%`), el("span", { class: "mcell__t" }, `>${mine.threshold} ATR`)),
          other ? bullet(mine.share, other.share, 100, "D") : null)
        : el("td", { title: `Your cost is ${costAtr.toFixed(2)} ATR of this ${h}, beyond the published range` }, "beyond 3 ATR");
    };
    const wrap = el("div", { class: "table-wrap" });
    const foldLine = el("p", { class: "tile__line mfold" });
    const note = el("p", { class: "tile__line" });
    const renderTable = () => {
      const list = expanded ? cards : cards.filter((c) => !folded.includes(c));
      const head = el("tr", {}, el("th", {}, ""), ...list.map((c) => el("th", { scope: "col" },
        el("b", {}, capital(c.state.horizon)),
        el("span", {}, `${c.state.sessions_elapsed} of about ${c.state.typical_sessions} ${c.state.session_unit}`),
        el("span", {}, `${num(c.state.analogs)} past ${c.state.horizon}s like this`),
        c.state.atr_start_pct ? el("span", {}, `1 ATR = ${c.state.atr_start_pct.toFixed(2)}%`) : null)));
      const rows = [
        el("tr", { class: "mtable__move" }, el("th", { scope: "row" }, "Typical move above"), ...list.map((c) => el("td", {}, move(c.state, "up_atr", "+")))),
        el("tr", { class: "mtable__move" }, el("th", { scope: "row" }, "Typical move below"), ...list.map((c) => el("td", {}, move(c.state, "down_atr", "−")))),
        ...MONEY_ROWS.map(([key, label]) => el("tr", {}, el("th", { scope: "row" }, label), ...list.map((c) => {
          const it = c.items.find((i) => i.extra?.outcome === key);
          if (!it || it.observed === null || it.observed === undefined) return el("td", {}, "–");
          const h = c.state.horizon, g = ctl(c.state);
          return el("td", { class: "mcell", title: `${it.observed.toFixed(0)}% of ${num(c.state.analogs)} past ${h}s like this, against ${it.baseline.toFixed(0)}% of ${num(g.n)} ${g.word} ${h}s at the same point; ${confidence(c, it.grade).toLowerCase()} (${it.grade})` },
            el("span", { class: "mcell__top" }, el("b", {}, `${it.observed.toFixed(0)}%`), el("span", { class: `mcell__g ${gradeClass(it.grade)}` }, it.grade)),
            bullet(it.observed, it.baseline, 100, it.grade));
        }))),
      ];
      if (cost.pct > 0) {
        for (const [side, label] of [["above", "Ended more than your cost above"], ["below", "Ended more than your cost below"]]) {
          rows.push(el("tr", { class: "mtable__cost" }, el("th", { scope: "row" }, label), ...list.map((c) => costCell(c, side))));
        }
      }
      wrap.replaceChildren(el("table", { class: "mtable" }, el("thead", {}, head), el("tbody", {}, ...rows)));
      if (folded.length) {
        const toggle = el("button", { class: "mfold__btn", type: "button", "aria-expanded": expanded ? "true" : "false" },
          expanded ? "Hide them" : `Show ${folded.map((c) => c.state.horizon).join(" and ")}`);
        toggle.addEventListener("click", () => { expanded = !expanded; renderTable(); });
        foldLine.replaceChildren(...folded.map((c) => el("span", {}, `${capital(c.state.horizon)}: ${foldReason(c)}. `)), toggle);
      } else foldLine.replaceChildren();
      foldLine.hidden = !folded.length;
      const inAtr = list.filter((c) => c.state.atr_start_pct).map((c) => `${(cost.pct / c.state.atr_start_pct).toFixed(2)} (${c.state.horizon})`).join(", ");
      note.textContent = cost.pct > 0
        ? `Cost: ${cost.pct.toFixed(2)}% per round trip${cost.source ? `. Source: ${cost.source}` : ""}. In ATR at the start of each period it is ${inAtr}; each share uses the first published threshold at or above it. Descriptive, not graded.`
        : "Graded rows are gross. Set your trading cost at the top of the board to see how often past periods ended beyond it.";
    };
    renderTable();
    const href = `#${first.id.replaceAll(".", "-")}`;
    return tile("tile--money", "What can be made or lost from here?",
      el("div", { class: "money__body" },
        el("div", { class: "money__main" },
          figure(up0 === undefined || down0 === undefined ? "–" : `+${up0.toFixed(2)} / −${down0.toFixed(2)}`,
            `ATR: the median move above and below the last close before the ${st0.horizon} ended, in ${num(st0.analogs)} past ${st0.horizon}s in the same position after ${st0.sessions_elapsed} ${plural(st0.sessions_elapsed, st0.session_unit)}. 1 ATR at the start of the ${st0.horizon} = ${st0.atr_start_pct?.toFixed(2)}%.`),
          moneyFan(same0, ctl0, st0.atr_start_pct),
          el("p", { class: "tile__line" }, `Bars: median move; whiskers: middle half of past ${st0.horizon}s; thin lines: ${c0.word} ${st0.horizon}s at the same point (${num(c0.n)}).`)),
        el("div", { class: "money__odds" },
          wrap,
          foldLine,
          note,
          el("p", { class: "tile__line" }, `Each cell: past periods in the same position as today (bar) against ${c0.word === "all" ? "all" : "the other"} periods at the same point (line), with the grade. Percentages are ATR multiples at the ATR at the start of each period.`),
          el("a", { class: "tile__more", href }, "Method and numbers for every horizon"))));
  }

  // One trading cost for the whole board, chosen once and kept in this browser only (specifications 0003, 0005).
  function costControl(inst) {
    const kind = inst.instrument.calendar === "24/7" ? "crypto" : "etf";
    const profiles = COST_PROFILES[kind];
    const cost = loadCost(kind);
    const select = el("select", { class: "cost__select", "aria-label": "Your trading cost per round trip" },
      ...profiles.map((p) => el("option", { value: p.id, selected: p.id === cost.id ? "selected" : null }, `${p.label}${p.pct ? ` (${p.pct}% round trip)` : ""}`)),
      el("option", { value: "custom", selected: cost.id === "custom" ? "selected" : null }, "My own cost per round trip"));
    const custom = el("input", { class: "cost__custom", type: "number", min: "0", max: "3", step: "0.01", value: cost.id === "custom" ? String(cost.pct) : "", "aria-label": "My cost per round trip, percent", placeholder: "%" });
    custom.hidden = cost.id !== "custom";
    const apply = (next) => { saveCost(kind, next); renderBoard(inst); };
    select.addEventListener("change", () => {
      if (select.value === "custom") { custom.hidden = false; custom.focus(); return; }  // applied once a figure is entered
      const p = profiles.find((x) => x.id === select.value);
      apply({ id: p.id, pct: p.pct, source: p.source });
    });
    custom.addEventListener("change", () => apply({ id: "custom", pct: Math.max(0, Math.min(3, Number(custom.value) || 0)), source: "your own figure" }));
    return el("div", { class: "cost cost--board" },
      el("label", {}, "Your trading cost", select), custom,
      el("span", { class: "cost__hint" }, cost.pct > 0 ? "Applied to the trade plan and to the money table; grades stay gross." : "Grades are always gross; a cost is applied to the trade plan and to the money table."));
  }

  // Average result in ATR on a scale centred on zero: bar for today's position, tick for all periods.
  function dbar(value, control, max, grade) {
    const at = (v) => 50 + Math.max(-50, Math.min(50, (v / max) * 50));
    const x0 = at(0), x1 = at(value);
    return el("div", { class: "dbar", "aria-hidden": "true" },
      el("span", { class: "dbar__zero" }),
      el("span", { class: "dbar__bar", style: `left:${Math.min(x0, x1).toFixed(1)}%;width:${Math.max(0.6, Math.abs(x1 - x0)).toFixed(1)}%;background:${gradeFill(grade)}` }),
      control === null || control === undefined ? null : el("span", { class: "dbar__tick", style: `left:${at(control).toFixed(1)}%` }));
  }

  const ordinal = (v) => {
    const n = Math.round(v), t = n % 100;
    return `${n}${t >= 11 && t <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] || "th"}`;
  };

  const PLAN_ROWS = [
    ["long_hold", "Long, held to the end"], ["long_1_1", "Long, stop 1, target 1"], ["long_1_2", "Long, stop 1, target 2"],
    ["short_hold", "Short, held to the end"], ["short_1_1", "Short, stop 1, target 1"], ["short_1_2", "Short, stop 1, target 2"],
  ];

  // What a simple plan taken at the last close returned by the period's end, in today's position against all
  // periods at the same point, gross and after the reader's cost (specification 0005).
  function tilePlan(inst) {
    const cards = ["week", "month"].map((h) => findCard(inst, `plan.${h}`)).filter((c) => c && c.items.length);
    if (!cards.length) return null;
    const kind = inst.instrument.calendar === "24/7" ? "crypto" : "etf";
    const cost = loadCost(kind);
    const costAtr = (c) => (cost.pct > 0 && c.state.atr_start_pct ? cost.pct / c.state.atr_start_pct : 0);
    const graded = (c) => c.items.some((i) => ["A", "B", "C"].includes(i.grade));
    const folded = cards.filter((c, k) => k > 0 && !graded(c));
    let expanded = false;
    const first = cards[0], st0 = first.state || {};
    const lead = [...first.items].sort((a, b) => RANK[a.grade] - RANK[b.grade])[0];
    const c0 = costAtr(first);
    const leadText = PLAN_ROWS.find(([k]) => k === lead.extra?.plan)?.[1] || lead.label;
    const s0 = lead.extra?.same || {}, a0 = lead.extra?.all || {};
    const split = lead.extra?.plan?.endsWith("hold")
      ? el("p", { class: "tile__line" }, `Ended in profit in ${pct(s0.win)} of past ${st0.horizon}s like this, against ${pct(a0.win)} of all ${st0.horizon}s.`)
      : el("div", { class: "split", role: "img", "aria-label": `Target first ${pct(s0.target_first)}, stop first ${pct(s0.stop_first)}, neither ${pct(s0.neither)}` },
          el("span", { class: "split__t", style: `flex:${s0.target_first || 0} 1 0` }, `Target ${pct(s0.target_first)}`),
          el("span", { class: "split__s", style: `flex:${s0.stop_first || 0} 1 0` }, `Stop ${pct(s0.stop_first)}`),
          el("span", { class: "split__n", style: `flex:${s0.neither || 0} 1 0` }, s0.neither >= 12 ? `Neither ${pct(s0.neither)}` : ""));
    const wrap = el("div", { class: "table-wrap" });
    const foldLine = el("p", { class: "tile__line mfold" });
    const renderTable = () => {
      const list = expanded ? cards : cards.filter((c) => !folded.includes(c));
      const scale = Math.max(0.5, ...list.flatMap((c) => c.items.flatMap((i) => [Math.abs(i.observed ?? 0), Math.abs(i.baseline ?? 0)]))) * 1.1;
      const head = el("tr", {}, el("th", {}, ""), ...list.map((c) => el("th", { scope: "col" },
        el("b", {}, capital(c.state.horizon)),
        el("span", {}, `${c.state.sessions_elapsed} of about ${c.state.typical_sessions} ${c.state.session_unit}`),
        el("span", {}, `${num(c.state.analogs)} past ${c.state.horizon}s like this`),
        c.state.atr_start_pct ? el("span", {}, `1 ATR = ${c.state.atr_start_pct.toFixed(2)}%`) : null)));
      const rows = PLAN_ROWS.map(([key, label]) => el("tr", {}, el("th", { scope: "row" }, label), ...list.map((c) => {
        const it = c.items.find((i) => i.extra?.plan === key);
        if (!it || it.observed === null || it.observed === undefined) return el("td", {}, "–");
        const s = it.extra.same, ca = costAtr(c), h = c.state.horizon;
        const mix = key.endsWith("hold") ? `in profit ${pct(s.win)}` : `target ${pct(s.target_first)} · stop ${pct(s.stop_first)}`;
        return el("td", { class: "mcell pcell", title: `${it.label}: average ${signed(it.observed, 2)} ATR in ${num(c.state.analogs)} past ${h}s like this, against ${signed(it.baseline, 2)} ATR in all ${num(c.state.all_periods)} ${h}s at the same point${ca ? `; after your cost (${ca.toFixed(2)} ATR) ${signed(it.observed - ca, 2)} ATR` : ""}; ${confidence(c, it.grade).toLowerCase()} (${it.grade})` },
          el("span", { class: "mcell__top" }, el("b", {}, signed(it.observed, 2)), el("span", { class: `mcell__g ${gradeClass(it.grade)}` }, it.grade)),
          dbar(it.observed, it.baseline, scale, it.grade),
          el("span", { class: "pcell__mix" }, mix),
          ca ? el("span", { class: "pcell__net" }, `after cost ${signed(it.observed - ca, 2)}`) : null);
      })));
      wrap.replaceChildren(el("table", { class: "mtable ptable" }, el("thead", {}, head), el("tbody", {}, ...rows)));
      if (folded.length) {
        const toggle = el("button", { class: "mfold__btn", type: "button", "aria-expanded": expanded ? "true" : "false" },
          expanded ? "Hide it" : `Show ${folded.map((c) => c.state.horizon).join(" and ")}`);
        toggle.addEventListener("click", () => { expanded = !expanded; renderTable(); });
        foldLine.replaceChildren(...folded.map((c) => el("span", {}, `${capital(c.state.horizon)}: ${c.items.every((i) => i.grade === "N/A") ? `too little history to grade (${num(c.state.analogs)} past ${c.state.horizon}s like this; 30 needed)` : `no plan differs reliably from all ${c.state.horizon}s at the same point`}. `)), toggle);
      } else foldLine.replaceChildren();
      foldLine.hidden = !folded.length;
    };
    renderTable();
    const rc = findCard(inst, `plan_regime.${st0.horizon}`);
    const rbest = rc?.items?.length ? [...rc.items].sort((a, b) => RANK[a.grade] - RANK[b.grade])[0] : null;
    const regimeLine = rbest
      ? el("div", { class: "tile__fact" },
          el("span", {}, `Volatility regime: this ${st0.horizon} started ${rc.state.regime} (ATR at the ${ordinal(rc.state.atr_start_percentile)} percentile of all earlier ${rc.state.session_unit}). In ${num(rc.state.analogs)} past ${st0.horizon}s that started ${rc.state.regime}, ${(PLAN_ROWS.find(([k]) => k === rbest.extra?.plan)?.[1] || rbest.label).toLowerCase()}: ${signed(rbest.observed, 2)} ATR against ${signed(rbest.baseline, 2)} ATR in all ${st0.horizon}s.`),
          gradeTag(rbest.grade, confidence(rc, rbest.grade)))
      : null;
    const costNote = cost.pct > 0
      ? `Your cost: ${cost.pct.toFixed(2)}% per round trip, ${cards.map((c) => `${costAtr(c).toFixed(2)} ATR of the ${c.state.horizon}`).join(" and ")}${cost.source ? `. Source: ${cost.source}` : ""}.`
      : "No cost applied. Set your trading cost at the top of the board to see each result after it.";
    return tile("tile--plan", "What would a simple plan have made from here?",
      el("div", { class: "money__body" },
        el("div", { class: "money__main" },
          figure(`${signed(c0 ? lead.observed - c0 : lead.observed, 2)} ATR`,
            `${leadText}, from the last close: average result${c0 ? " after your cost" : ""} in ${num(st0.analogs)} past ${st0.horizon}s like this, against ${signed(lead.baseline - c0, 2)} ATR in all ${num(st0.all_periods)} ${st0.horizon}s at the same point. 1 ATR at the start of the ${st0.horizon} = ${st0.atr_start_pct?.toFixed(2)}%.`,
            gradeTag(lead.grade, confidence(first, lead.grade))),
          split,
          el("p", { class: "tile__line" }, "Bar: average result in today's position; line: all periods at the same point; zero in the middle.")),
        el("div", { class: "money__odds" },
          wrap,
          foldLine,
          regimeLine,
          el("p", { class: "tile__line" }, costNote),
          el("p", { class: "tile__line" }, "Plans start at the last close: held to the period's last close, or with a stop 1 ATR away and a target 1 or 2 ATR away. A bar that reaches both counts as the stop. Results are averages in ATR at the start of each period. The grade says whether today's position differs from all periods at the same point, not whether a plan pays."),
          el("a", { class: "tile__more", href: `#${first.id.replaceAll(".", "-")}` }, "Method and numbers for every plan"))));
  }

  function edgeCounts(inst) {
    const counts = { A: 0, B: 0, C: 0, D: 0, F: 0, "N/A": 0 };
    for (const c of cardsOf(inst)) if (c.kind === "edge") for (const it of c.items) counts[it.grade] = (counts[it.grade] || 0) + 1;
    return counts;
  }

  function scoreBar(counts) {
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    const order = ["A", "B", "C", "D", "F", "N/A"];
    const name = { A: "A strong", B: "B moderate", C: "C weak", D: "D no difference", F: "F contradicted", "N/A": "Too little history" };
    return el("div", { class: "score" },
      el("div", { class: "score__bar", role: "img", "aria-label": order.map((g) => `${name[g]} ${counts[g]}`).join(", ") },
        ...order.filter((g) => counts[g]).map((g) => el("span", { class: `score__seg ${gradeClass(g)}`, style: `flex:${counts[g]} 1 0`, title: `${name[g]}: ${counts[g]} of ${total}` }))),
      el("div", { class: "score__legend" }, ...order.filter((g) => counts[g]).map((g) =>
        el("span", {}, el("i", { class: `score__key ${gradeClass(g)}` }), `${name[g]} `, el("b", {}, counts[g])))));
  }

  // Strongest graded effects with a measurable control, one per family, timing families first.
  function strongest(inst, n = 3) {
    const order = ["volatility", "sessions", "money", "plan", "plan_regime", "revisits", "weekly", "extremes", "paths"];
    const pool = cardsOf(inst).filter((c) => c.kind === "edge" && ["A", "B"].includes(c.grade));
    const strength = (c) => {
      const it = c.items[c.primary ?? 0];
      return it?.baseline ? Math.abs((it.observed - it.baseline) / it.baseline) : 0;
    };
    const out = [];
    for (const fam of order) {
      const best = pool.filter((c) => c.family === fam && c.items[c.primary ?? 0]?.baseline != null)
        .sort((a, b) => RANK[a.grade] - RANK[b.grade] || strength(b) - strength(a))[0];
      if (best) out.push(best);
      if (out.length === n) break;
    }
    return out;
  }

  function tileEvidence(inst) {
    const counts = edgeCounts(inst);
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    if (!total) return null;
    const lines = strongest(inst).map((c) => evidenceBullet(c, c.items[c.primary ?? 0],
      { title: effectTitle(c, c.items[c.primary ?? 0]), href: `#${c.id.replaceAll(".", "-")}` }));
    return tile("tile--evidence", "What does the evidence support?",
      el("div", { class: "evidence" },
        el("div", { class: "evidence__score" },
          figure(`${counts.A + counts.B}`, counts.A + counts.B
            ? `of ${total} effects tested against a control are strong or moderate. Most patterns fail; these survive.`
            : `of ${total} effects tested against a control are strong or moderate so far. None is shown as evidence until it is.`),
          scoreBar(counts)),
        el("div", { class: "evidence__lines" },
          lines.length ? el("p", { class: "tile__line" }, "Strongest effects with a measurable control. Bar: observed; line: control.") : null,
          el("div", { class: "ev-list" }, ...lines),
          el("a", { class: "tile__more", href: "#markets" }, "Every finding, with method and numbers"))));
  }

  // Today: at most three facts that apply to the current position, each linked to its tile (specification
  // 0006). Only strong evidence (A) leads the board; measurements are labelled as such; nothing is shown
  // that is not on a tile.
  const MONEY_PHRASES = {
    up_1: "reached 1 ATR above the close", down_1: "reached 1 ATR below the close",
    up_2: "reached 2 ATR above the close", down_2: "reached 2 ATR below the close",
    end_up: "ended above the close", end_down: "ended below the close",
  };

  function todayPanel(inst, clk, crypto, unit) {
    const facts = [];
    for (const [fam, h] of [["plan", "week"], ["plan_regime", "week"], ["plan", "month"], ["plan_regime", "month"]]) {
      const c = findCard(inst, `${fam}.${h}`);
      const best = (c?.items || []).filter((i) => i.grade === "A" && i.observed !== null && i.baseline !== null)
        .sort((a, b) => Math.abs(b.estimate) - Math.abs(a.estimate))[0];
      if (!best) continue;
      const name = (PLAN_ROWS.find(([k]) => k === best.extra?.plan)?.[1] || best.label).toLowerCase();
      facts.push({ fig: `${signed(best.observed, 2)} ATR`, grade: best.grade, card: c, href: "#tile-plan",
        text: `average result of a ${name.replace("held to the end", `held to the ${h}'s end`)} from the last close, in past ${h}s ${fam === "plan_regime" ? `that started ${c.state.regime}, as this one did` : "in today's position"}, against ${signed(best.baseline, 2)} ATR in all ${h}s (gross)` });
      break;
    }
    for (const h of ["week", "month", "quarter"]) {
      const c = findCard(inst, `money.${h}`);
      const best = (c?.items || []).filter((i) => i.grade === "A" && i.observed !== null && i.baseline !== null)
        .sort((a, b) => Math.abs(b.estimate) - Math.abs(a.estimate))[0];
      if (!best) continue;
      const st = c.state, g = ctl(st);
      const where = st.broke_prior_high && !st.broke_prior_low ? `above last ${h}'s high, not its low`
        : st.broke_prior_low && !st.broke_prior_high ? `below last ${h}'s low, not its high`
        : st.broke_prior_high ? `through last ${h}'s high and low` : `inside last ${h}'s range`;
      facts.push({ fig: `${best.observed.toFixed(0)}%`, grade: best.grade, card: c, href: "#tile-money",
        text: `of past ${h}s in today's position (${where}) ${MONEY_PHRASES[best.extra?.outcome] || best.label.toLowerCase()} before the ${h} ended, against ${best.baseline.toFixed(0)}% of ${g.word} ${h}s` });
      break;
    }
    const vc = crypto ? findCard(inst, "volatility.hour") : findCard(inst, "volatility.halfhour");
    const now = vc?.items?.find((i) => i.label === (crypto ? clk.hour : clk.slot));
    if (now && now.grade === "A") {
      const slot = crypto ? "hour" : "half-hour";
      facts.push({ fig: rel(now.estimate), grade: now.grade, card: vc, href: "#tile-when",
        text: `range in the ${now.label} ${slot}, ${crypto || clk.open ? "now" : "when the next session opens"}, against the average ${slot}` });
    }
    const p = inst.position || {};
    if (p.atr_pct !== null && p.atr_pct !== undefined) {
      const pctl = p.atr_percentile;
      facts.push({ fig: `${p.atr_pct.toFixed(2)}%`, grade: null, href: "#tile-move",
        text: `average daily range over the last 14 ${unit} (ATR)${pctl === null || pctl === undefined ? "" : `, higher than ${pctl.toFixed(0)}% of ${unit} since ${String(p.atr_history_from).slice(0, 4)}`}` });
    }
    if (!facts.length) return null;
    return el("section", { class: "today", "aria-labelledby": "today-title" },
      el("h3", { class: "today__title", id: "today-title" }, "Today"),
      el("div", { class: "today__list" }, ...facts.slice(0, 3).map((f) => el("a", { class: "today__fact", href: f.href },
        el("span", { class: "today__fig" }, f.fig),
        el("span", { class: "today__text" }, f.text),
        f.grade ? gradeTag(f.grade, confidence(f.card, f.grade)) : el("span", { class: "today__measured" }, "Measured, not graded")))),
      facts.some((f) => f.grade) ? null : el("p", { class: "tile__line" }, "No strong effect applies to today's position; the tiles below give the context and the weaker evidence."));
  }

  function renderBoard(inst) {
    const box = document.getElementById("board");
    if (!inst || inst.status !== "ok") { box.replaceChildren(); box.hidden = true; return; }
    box.hidden = false;
    const crypto = inst.instrument.calendar === "24/7";
    const clk = crypto ? cryptoClock(new Date()) : equityClock(new Date(), inst.sessions_ahead);
    const unit = crypto ? "days" : "sessions";
    const st = (state.report.data_status?.instruments || []).find((r) => r.code === inst.code);
    const word = { fresh: "Data up to date", degraded: "Data current, fallback source", stale: "Data out of date" };
    const closeOnly = !inst.position?.horizons?.length;
    const lastDay = inst.position?.as_of || String(inst.coverage?.daily?.end || "").slice(0, 10);
    const when = closeOnly ? `close-only index reference, last close ${dayLabel(lastDay)}`
      : crypto ? `last full day ${dayLabel(lastDay)}; trading around the clock`
      : clk.open ? `${clk.label}` : `last close ${dayLabel(lastDay)}; next session ${clk.weekday} ${clk.dom} ${clk.month}, 09:30 New York${clk.early ? `, early close ${clk.closeText}` : ""}`;
    const tiles = [tileMove(inst, clk, unit, crypto), tileWhen(inst, clk, crypto), tilePosition(inst, unit), tileLevels(inst, unit), tileMoney(inst, unit), tilePlan(inst), tileEvidence(inst)].filter(Boolean);
    const costs = findCard(inst, "money.week") || findCard(inst, "money.month") || findCard(inst, "plan.week") || findCard(inst, "plan.month");
    box.replaceChildren(
      el("div", { class: "board__head" },
        el("h2", { id: "board-title" }, "At a glance"),
        el("p", {}, `${marketName(inst.code)}, ${inst.code}: ${when}`),
        st ? el("span", { class: "board__status" }, el("span", { class: `dot dot--${st.status}` }), word[st.status] || st.status) : null),
      closeOnly ? null : todayPanel(inst, clk, crypto, unit),
      costs && !closeOnly ? el("div", { class: "board__tools" }, costControl(inst)) : null,
      el("div", { class: "board__grid" }, ...tiles),
      el("p", { class: "board__foot" }, closeOnly
        ? `${marketName(inst.code)} is published as closes only, so positions, levels and intraday timing are shown for the tradable funds (SPY, QQQ); its long-history statistics are listed below.`
        : "Every figure is measured on this market's own history and graded against a control. It describes what has happened; it is not a signal or a forecast."));
  }

  // ------------------------------------------------------------------ time to revisit
  // Share of past periods whose high or low was traded again within k sessions (solid), against
  // arbitrary levels at the same volatility-scaled distance (dashed). Dots mark the graded windows.
  function curveOf(card, side) {
    const items = card.items.filter((it) => it.label.startsWith(side === "high" ? "High" : "Low"));
    const windows = items.map((it) => Number(it.label.match(/within (\d+)/)?.[1]));
    const c = items[0]?.extra?.curve;
    if (c?.sessions?.length) return { k: [0, ...c.sessions], real: [0, ...c.real_pct], control: [0, ...c.control_pct], items, windows };
    return { k: [0, ...windows], real: [0, ...items.map((i) => i.observed)], control: [0, ...items.map((i) => i.baseline)], items, windows };
  }

  function revisitChart(card, unit) {
    const w = 300, h = 178, padL = 34, padR = 10, padT = 12, padB = 26;
    const sides = [["high", curveOf(card, "high")], ["low", curveOf(card, "low")]];
    const kmax = Math.max(...sides.flatMap(([, s]) => s.k));
    const x = (k) => padL + (k / kmax) * (w - padL - padR);
    const y = (v) => padT + (1 - v / 100) * (h - padT - padB);
    const root = svg("svg", { viewBox: `0 0 ${w} ${h}`, class: "curves", role: "img", "aria-label": `${card.title}: share revisited by ${unit}, real levels against arbitrary levels` });
    for (const v of [0, 50, 100]) {
      root.append(svg("line", { x1: padL, x2: w - padR, y1: y(v), y2: y(v), class: "curves__grid" }));
      const t = svg("text", { x: padL - 6, y: y(v) + 3, "text-anchor": "end" }); t.textContent = `${v}%`; root.append(t);
    }
    for (const k of [0, Math.round(kmax / 2), kmax]) {
      const t = svg("text", { x: x(k), y: h - 8, "text-anchor": k === 0 ? "start" : k === kmax ? "end" : "middle" });
      t.textContent = k === kmax ? `${k} ${unit}` : `${k}`;
      root.append(t);
    }
    const line = (ks, vs) => ks.map((k, i) => (vs[i] === null || vs[i] === undefined ? null : `${i ? "L" : "M"}${x(k).toFixed(1)},${y(vs[i]).toFixed(1)}`)).filter(Boolean).join(" ");
    for (const [side, s] of sides) {
      root.append(svg("path", { d: line(s.k, s.control), class: `curves__line curves__line--control curves__line--${side}` }));
      root.append(svg("path", { d: line(s.k, s.real), class: `curves__line curves__line--${side}` }));
      s.items.forEach((it, i) => {
        const dot = svg("circle", { cx: x(s.windows[i]), cy: y(it.observed), r: 3.2, class: `curves__dot curves__dot--${side}` });
        const t = svg("title"); t.textContent = `${it.label}: ${it.observed.toFixed(0)}% against ${it.baseline.toFixed(0)}%, grade ${it.grade}`; dot.append(t);
        root.append(dot);
      });
    }
    return root;
  }

  function renderCurves(inst) {
    const box = document.getElementById("revisit-curves");
    const cards = cardsOf(inst || {}).filter((c) => c.family === "revisits" && c.items.length);
    if (!inst || inst.status !== "ok" || !cards.length) { box.replaceChildren(); box.hidden = true; return; }
    box.hidden = false;
    const unit = inst.instrument.calendar === "24/7" ? "days" : "sessions";
    const best = (card, side) => card.items.filter((it) => it.label.startsWith(side)).sort((a, b) => RANK[a.grade] - RANK[b.grade])[0];
    box.replaceChildren(
      el("div", { class: "levels__head" },
        el("h2", {}, "How soon are highs and lows revisited?"),
        el("p", {}, `Share of past periods whose high or low traded again within each number of ${unit} (solid), against arbitrary levels at the same volatility-scaled distance (dashed). The gap between the lines is what the real level adds.`)),
      el("div", { class: "curves-grid" }, ...cards.map((c) => {
        const hi = best(c, "High"), lo = best(c, "Low");
        const line = (it, side) => it ? el("li", { class: `curves__key curves__key--${side}` },
          el("span", {}, `${it.label.replace(" revisited", "")}`), el("b", {}, `${it.observed.toFixed(0)}%`), el("span", { class: "curves__vs" }, `vs ${it.baseline.toFixed(0)}%`), gradeTag(it.grade, null)) : null;
        return el("a", { class: "curves-card", href: `#${c.id.replaceAll(".", "-")}` },
          el("h3", {}, c.title.replace("Time to revisit the prior ", "Prior ").replace("'s high and low", "")),
          revisitChart(c, unit),
          el("ul", {}, line(hi, "high"), line(lo, "low")));
      })));
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
    renderBoard(inst);
    renderTime(inst);
    renderGrid(inst);
    renderCurves(inst);
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
    const AXIS = { now: "Space", money: "Space", plan: "Space", levels: "Space", revisits: "Space", paths: "Space", sessions: "Time", volatility: "Time", weekly: "Time", extremes: "Time", calendar: "Time" };
    const groups = ["Time", "Space"].map((axis) => [axis, inst.sections.filter((s) => (AXIS[s.id] || "Space") === axis)]).filter(([, list]) => list.length);
    index.replaceChildren(...groups.flatMap(([axis, list]) => [el("span", { class: "index__axis" }, axis),
      ...list.map((s) => el("a", { href: `#sec-${code}-${s.id}` }, s.title))]));
    const labels = state.report.grade_labels || {};
    const notes = (inst.notes || []).map((n) => el("div", { class: "notice" }, n));
    panel.replaceChildren(...notes, ...inst.sections.map((s) =>
      el("section", { class: "group", id: `sec-${code}-${s.id}` },
        el("h2", { class: "group__title" }, s.title),
        el("p", { class: "group__count" }, `${s.cards.length} ${s.cards.length === 1 ? "question" : "questions"}`),
        ...groupCards(s.cards, labels))));
  }

  // Graded findings first, strongest first; findings without enough history are grouped at the end.
  function groupCards(cards, labels) {
    const graded = cards.filter((c) => c.grade !== "N/A").sort((a, b) => RANK[a.grade] - RANK[b.grade]);
    const thin = cards.filter((c) => c.grade === "N/A");
    const out = graded.map((c) => renderFinding(c, labels));
    if (thin.length) {
      out.push(el("details", { class: "thin" },
        el("summary", {}, `${thin.length} ${thin.length === 1 ? "question needs" : "questions need"} more history before they can be graded`),
        el("p", { class: "thin__why" }, "These periods are long or recent data is short, so too few comparable cases exist. They are kept visible so nothing is hidden, and they will be graded automatically as history accumulates."),
        ...thin.map((c) => renderFinding(c, labels))));
    }
    return out;
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
    window.matchMedia("(max-width: 720px)").addEventListener("change", () => { if (state.active) selectMarket(state.active); });
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
