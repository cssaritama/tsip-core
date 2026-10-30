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
  const HKEY = { week: "week", month: "month", quarter: "quarter", "half-year": "half-year", year: "year" };
  const signed = (v, d = 2) => (v === null || v === undefined ? "–" : `${v > 0 ? "+" : ""}${v.toFixed(d)}`);
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
            el("div", {}, el("div", { class: "outcome__fig" }, out.fig), el("div", { class: "outcome__label" }, out.label)),
            el("div", { class: "outcome__side" }, gradeTag(out.grade, null), el("div", { class: "outcome__n" }, out.n)))
        : el("div", { class: "outcome" }, el("div", { class: "outcome__label" }, "Not enough comparable periods yet")));
  }

  function renderOpenLevels(inst) {
    const box = document.getElementById("open-levels");
    const ol = inst?.open_levels;
    if (!ol || !ol.levels?.length) { box.replaceChildren(); box.hidden = true; return; }
    box.hidden = false;
    const rows = ol.levels.slice(0, 10).map((l) => el("tr", {},
      el("td", {}, `${capital(l.horizon)} ${l.side}`),
      el("td", {}, l.period),
      el("td", {}, l.age_sessions === 0 ? "Just closed" : `${num(l.age_sessions)}`),
      el("td", { class: l.distance_pct >= 0 ? "up" : "down" }, `${signed(l.distance_pct)}%`),
      el("td", {}, l.distance_atr === null ? "–" : signed(l.distance_atr, 1))));
    const revisit = cardsOf(inst).find((c) => c.family === "revisits");
    box.replaceChildren(
      el("div", { class: "levels__head" },
        el("h2", {}, "Open levels"),
        el("p", {}, `Highs and lows of closed periods not traded since, nearest first, as of ${ol.as_of}. ATR ${ol.atr_pct ? ol.atr_pct.toFixed(2) : "–"}% over 14 sessions.`),
        revisit ? el("a", { href: `#sec-${inst.code}-revisits` }, "How soon levels are revisited") : null),
      el("div", { class: "table-wrap" }, el("table", { class: "levels" },
        el("thead", {}, el("tr", {}, ...["Level", "Period", "Age (sessions)", "Distance", "In ATR"].map((h) => el("th", {}, h)))),
        el("tbody", {}, ...rows))));
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

  function equityClock(now) {
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
    return { open, session, label, weekday: DAY_NAMES[wd], month: MONTH_SHORT[z.m - 1], dom: z.d, y: z.y, m: z.m };
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

  function timeCoordinates(inst, now = new Date()) {
    const crypto = inst.instrument.calendar === "24/7";
    const clk = crypto ? cryptoClock(now) : equityClock(now);
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
    coords.push({ name: "Session", value: clk.session, note: clk.label, facts: sessionFacts });
    // weekday
    const wh = findCard(inst, "weekly.week_high"), wl = findCard(inst, "weekly.week_low"), wd = findCard(inst, "calendar.weekday");
    coords.push({ name: "Day of the week", value: clk.weekday, note: crypto ? "" : clk.open ? "Today" : "Next session", facts: [
      fact(wh, findItem(wh, (l) => l.label === clk.weekday), "Week high forms on this day, against a random walk"),
      fact(wl, findItem(wl, (l) => l.label === clk.weekday), "Week low forms on this day, against a random walk"),
      fact(wd, findItem(wd, (l) => l.label === clk.weekday), `Return on ${clk.weekday}, versus ${wd?.contrast || "the other days"}`),
    ] });
    // month
    const mo = findCard(inst, "calendar.month"), tom = findCard(inst, "calendar.turn_of_month");
    const lastDay = new Date(Date.UTC(clk.y, clk.m, 0)).getUTCDate();
    const inTurn = clk.dom <= 3 || clk.dom === lastDay;
    const monthFacts = [fact(mo, findItem(mo, (l) => l.label === clk.month), `Return in ${clk.month}, versus ${mo?.contrast || "the other months"}`)];
    if (tom && inTurn) monthFacts.push(fact(tom, tom.items[0], `Turn-of-month days, versus ${tom?.contrast || "the other days"}`));
    coords.push({ name: "Month", value: `${clk.month}, day ${clk.dom}`,
      note: [!clk.open && "Next session", inTurn && "inside the turn-of-month window"].filter(Boolean).join(", ").replace(/^i/, "I"), facts: monthFacts });
    // quarter and year progress from the position block
    const q = (inst.position?.horizons || []).find((p) => p.horizon === "quarter");
    const yr = (inst.position?.horizons || []).find((p) => p.horizon === "year");
    const mapQ = cardsOf(inst).find((c) => c.family === "map" && c.state?.horizon === "quarter");
    const mapY = cardsOf(inst).find((c) => c.family === "map" && c.state?.horizon === "year");
    const prog = (m) => (m?.state?.typical_sessions ? `${m.state.sessions_elapsed} of about ${m.state.typical_sessions} ${m.state.session_unit || "sessions"}` : "");
    coords.push({ name: "Quarter and year", value: q?.period || "–",
      note: [prog(mapQ) && `Quarter: ${prog(mapQ)}`, prog(mapY) && `Year ${yr?.period}: ${prog(mapY)}`].filter(Boolean).join(". "), facts: [], link: "#space" });
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
      el("ul", { class: "coord__facts" }, ...c.facts.filter(Boolean).map((f) => el("li", {},
        el("a", { href: f.href }, el("span", { class: "coord__fact" }, f.text), el("span", { class: "coord__fig" }, f.value), gradeTag(f.grade, null))))),
      !c.facts.filter(Boolean).length && c.link ? el("a", { class: "coord__more", href: c.link }, "Position against prior quarters and years") : null)));
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
    renderTime(inst);
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
    const AXIS = { now: "Space", levels: "Space", revisits: "Space", paths: "Space", sessions: "Time", weekly: "Time", calendar: "Time" };
    const groups = ["Time", "Space"].map((axis) => [axis, inst.sections.filter((s) => (AXIS[s.id] || "Space") === axis)]).filter(([, list]) => list.length);
    index.replaceChildren(...groups.flatMap(([axis, list]) => [el("span", { class: "index__axis" }, axis),
      ...list.map((s) => el("a", { href: `#sec-${code}-${s.id}` }, s.title))]));
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
