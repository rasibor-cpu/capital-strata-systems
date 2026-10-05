/* CSS Trader Passport client (Issue #102).
   Server-driven: the API decides which step comes next, validates answers and builds the Passport, so the client
   holds no branching or scoring rules of its own. All user text is inserted with textContent (no HTML injection).
   Accessibility: one h1 per step (focused on change), fieldset/legend groups, labelled inputs, errors announced via
   aria-live and linked with aria-describedby, keyboard-operable controls, reduced-motion respected by CSS. */
(() => {
  "use strict";
  const API = "/passport";
  const $ = (sel) => document.querySelector(sel);
  const main = $("#main"), live = $("#live"), actions = $("#actions"), nextBtn = $("#next"), backBtn = $("#back");
  let view = null;

  const COUNTRIES = [["", "Choose…"], ["US", "United States"], ["CA", "Canada"], ["GB", "United Kingdom"],
    ["IE", "Ireland"], ["AU", "Australia"], ["NZ", "New Zealand"], ["DE", "Germany"], ["FR", "France"],
    ["NL", "Netherlands"], ["ES", "Spain"], ["IT", "Italy"], ["CH", "Switzerland"], ["SE", "Sweden"],
    ["NO", "Norway"], ["DK", "Denmark"], ["SG", "Singapore"], ["HK", "Hong Kong"], ["JP", "Japan"],
    ["IN", "India"], ["AE", "United Arab Emirates"], ["ZA", "South Africa"], ["NG", "Nigeria"], ["KE", "Kenya"],
    ["GH", "Ghana"], ["BR", "Brazil"], ["MX", "Mexico"], ["OT", "Other (tell us later)"]];

  // ------------------------------------------------------------------ helpers
  function el(tag, attrs = {}, ...children) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const c of children.flat()) if (c !== null && c !== undefined) n.append(c.nodeType ? c : document.createTextNode(c));
    return n;
  }
  const token = () => sessionStorage.getItem("css_token");
  async function api(method, path, body) {
    const res = await fetch(API + path, {
      method, headers: { "Content-Type": "application/json", ...(token() ? { Authorization: "Bearer " + token() } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = null;
    try { data = await res.json(); } catch (_) { /* no body */ }
    return { status: res.status, data };
  }
  function announce(msg) { live.textContent = ""; setTimeout(() => { live.textContent = msg; }, 30); }
  function money(v) { const s = v < 0 ? "−" : v > 0 ? "+" : ""; return s + "$" + Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function focusTitle() { const h = main.querySelector("h1"); if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: false }); } window.scrollTo(0, 0); }

  // ------------------------------------------------------------------ progress
  function setProgress(p, group) {
    $("#progress").hidden = false;
    const bar = $("#progressbar");
    bar.setAttribute("aria-valuemax", String(p.total));
    bar.setAttribute("aria-valuenow", String(Math.min(p.position, p.total)));
    bar.setAttribute("aria-valuetext", `Step ${Math.min(p.position, p.total)} of ${p.total}`);
    $("#progress-fill").style.width = `${Math.round(100 * Math.min(p.position, p.total) / p.total)}%`;
    $("#progress-text").textContent = `Step ${Math.min(p.position, p.total)} of ${p.total}`;
    $("#progress-group").textContent = group || "";
  }

  // ------------------------------------------------------------------ question widgets
  function optionInput(type, name, opt, checked, describedBy) {
    const id = `${name}-${opt.value}`;
    return el("div", { class: "option" },
      el("input", { type, id, name, value: opt.value, checked: !!checked, "aria-describedby": describedBy }),
      el("label", { for: id }, el("span", { class: "tick", "aria-hidden": "true" }),
        el("span", { class: "opt-text" }, el("span", { text: opt.label }),
          opt.detail ? el("span", { class: "opt-detail", text: opt.detail }) : null)));
  }

  function renderQuestion(q, value) {
    const errId = `err-${q.id}`, helpId = q.help ? `help-${q.id}` : null;
    const described = [helpId, errId].filter(Boolean).join(" ");
    const err = el("p", { class: "error", id: errId, hidden: true });
    const help = q.help ? el("p", { class: "help", id: helpId, text: q.help }) : null;
    const req = q.required ? null : el("span", { class: "note", text: " (optional)" });
    const wrap = (inner) => { const n = el("div", { class: "q", "data-qid": q.id, "data-type": q.type }, inner, err); return n; };

    if (["text", "email", "phone"].includes(q.type)) {
      const attrs = { id: q.id, name: q.id, value: value ?? "", "aria-describedby": described, maxlength: q.max_len || 120,
        type: q.type === "email" ? "email" : q.type === "phone" ? "tel" : "text",
        autocomplete: { display_name: "nickname", full_name: "name", email: "email", phone: "tel" }[q.id] || "off",
        inputmode: q.type === "phone" ? "tel" : q.type === "email" ? "email" : null, required: q.required };
      return wrap(el("div", { class: "field" }, el("label", { for: q.id }, q.prompt, req), help, el("input", attrs)));
    }
    if (q.type === "country") {
      const sel = el("select", { id: q.id, name: q.id, "aria-describedby": described, required: q.required, autocomplete: "country" },
        COUNTRIES.map(([v, l]) => el("option", { value: v, selected: v === value, text: l })));
      return wrap(el("div", { class: "field" }, el("label", { for: q.id, text: q.prompt }), help, sel));
    }
    if (q.type === "consent") {
      return wrap(el("label", { class: "consent", for: q.id },
        el("input", { type: "checkbox", id: q.id, name: q.id, checked: value === true, "aria-describedby": described,
          required: !!q.must_be_true }),
        el("span", {}, q.prompt, req)));
    }
    if (["single", "quiz", "boolean"].includes(q.type)) {
      const opts = q.type === "boolean" ? [{ value: "true", label: "True" }, { value: "false", label: "False" }] : q.options;
      const cur = q.type === "boolean" ? (value === true ? "true" : value === false ? "false" : null) : value;
      return wrap(el("fieldset", { "aria-describedby": described },
        el("legend", {}, q.prompt, req), help,
        el("div", { class: "options", role: "radiogroup" }, opts.map((o) => optionInput("radio", q.id, o, cur === o.value)))));
    }
    if (q.type === "multi") {
      const cur = Array.isArray(value) ? value : [];
      return wrap(el("fieldset", { "aria-describedby": described },
        el("legend", {}, q.prompt, req), help,
        el("div", { class: "options" }, q.options.map((o) => optionInput("checkbox", q.id, o, cur.includes(o.value))))));
    }
    if (q.type === "matrix") {
      const cur = value || {};
      return wrap(el("div", {}, el("p", { class: "help", id: helpId || undefined, text: q.prompt }),
        q.help ? el("p", { class: "help", text: q.help }) : null,
        q.rows.map((r) => el("fieldset", { class: "matrix-row", "data-row": r.value },
          el("legend", { text: r.label }),
          el("div", { class: "segmented" }, q.options.map((o) => optionInput("radio", `${q.id}__${r.value}`, o, cur[r.value] === o.value)))))));
    }
    if (q.type === "rank") {
      const order = Array.isArray(value) ? [...value] : [];
      const list = el("div", { class: "options", "data-order": JSON.stringify(order) });
      const max = q.max_select || 3;
      const paint = () => {
        const ord = JSON.parse(list.dataset.order);
        list.querySelectorAll("button").forEach((b) => {
          const i = ord.indexOf(b.dataset.value);
          b.setAttribute("aria-pressed", i >= 0 ? "true" : "false");
          b.querySelector(".tick").textContent = i >= 0 ? String(i + 1) : "";
          b.setAttribute("aria-label", `${b.dataset.label}${i >= 0 ? `, ranked ${i + 1}` : ""}`);
        });
      };
      q.options.forEach((o) => list.append(el("button", {
        type: "button", class: "rank-btn", "data-value": o.value, "data-label": o.label, "aria-pressed": "false",
        onclick: () => {
          const ord = JSON.parse(list.dataset.order);
          const i = ord.indexOf(o.value);
          if (i >= 0) ord.splice(i, 1); else if (ord.length < max) ord.push(o.value);
          list.dataset.order = JSON.stringify(ord); paint();
          announce(i >= 0 ? `${o.label} removed` : ord.includes(o.value) ? `${o.label} ranked ${ord.length}` : `You can rank ${max}`);
        },
      }, el("span", { class: "tick", "aria-hidden": "true" }), el("span", { text: o.label }))));
      setTimeout(paint);
      return wrap(el("fieldset", { "aria-describedby": described }, el("legend", {}, q.prompt), help, list));
    }
    return wrap(el("p", { class: "error", text: `Unsupported question: ${q.id}` }));
  }

  function collect(stage) {
    const out = {};
    for (const q of stage.questions || []) {
      const node = main.querySelector(`[data-qid="${q.id}"]`);
      if (!node) continue;
      if (["text", "email", "phone", "country"].includes(q.type)) out[q.id] = node.querySelector("input,select").value.trim();
      else if (q.type === "consent") out[q.id] = node.querySelector("input").checked;
      else if (q.type === "boolean") { const c = node.querySelector("input:checked"); out[q.id] = c ? c.value === "true" : null; }
      else if (["single", "quiz"].includes(q.type)) { const c = node.querySelector("input:checked"); out[q.id] = c ? c.value : null; }
      else if (q.type === "multi") out[q.id] = [...node.querySelectorAll("input:checked")].map((i) => i.value);
      else if (q.type === "matrix") {
        const m = {}; let complete = true;
        for (const r of q.rows) { const c = node.querySelector(`input[name="${q.id}__${r.value}"]:checked`); if (c) m[r.value] = c.value; else complete = false; }
        out[q.id] = complete ? m : (Object.keys(m).length ? m : null);
      } else if (q.type === "rank") out[q.id] = JSON.parse(node.querySelector("[data-order]").dataset.order);
      if (out[q.id] === "" && !q.required) out[q.id] = null;
    }
    return out;
  }

  function showErrors(errors) {
    let first = null;
    main.querySelectorAll(".error[id^=err-]").forEach((e) => { e.hidden = true; e.textContent = ""; });
    main.querySelectorAll("[aria-invalid]").forEach((n) => n.removeAttribute("aria-invalid"));
    for (const [qid, msg] of Object.entries(errors)) {
      const e = main.querySelector(`#err-${CSS.escape(qid)}`);
      if (!e) continue;
      e.hidden = false; e.textContent = msg;
      const ctl = main.querySelector(`[data-qid="${CSS.escape(qid)}"] input, [data-qid="${CSS.escape(qid)}"] select, [data-qid="${CSS.escape(qid)}"] button`);
      if (ctl) { ctl.setAttribute("aria-invalid", "true"); first = first || ctl; }
    }
    const n = Object.keys(errors).length;
    announce(n === 1 ? "There is one thing to fix on this step." : `There are ${n} things to fix on this step.`);
    if (first) first.focus();
  }

  // ------------------------------------------------------------------ stage rendering
  function renderStage(v) {
    view = v;
    const s = v.stage;
    main.replaceChildren();
    if (s.kind === "result") return renderResult(v);
    setProgress(v.progress, s.group);
    const content = el("section", { class: "stage", "aria-labelledby": "stage-title" },
      el("p", { class: "group", text: s.group }),
      el("h1", { id: "stage-title", text: s.title }),
      s.body ? el("div", { class: "lead" }, s.body.map((p) => el("p", { text: p }))) : null,
      (s.questions || []).map((q) => renderQuestion(q, v.answers[q.id])));
    const art = s.illustration ? el("img", { class: "illustration", src: `assets/${s.illustration}.svg`, alt: "" }) : null;
    main.append(art ? el("div", { class: "split" }, art, content) : content);
    actions.hidden = false;
    backBtn.hidden = v.progress.position <= 1;
    nextBtn.textContent = "Continue";
    nextBtn.onclick = () => submit(s);
    backBtn.onclick = goBack;
    focusTitle();
    announce(`Step ${v.progress.position} of ${v.progress.total}: ${s.title}`);
  }

  async function submit(stage) {
    nextBtn.disabled = true;
    try {
      const { status, data } = await api("POST", "/answer", { stage_id: stage.id, answers: collect(stage) });
      if (status === 200) renderStage(data);
      else if (status === 422 && data && data.detail && data.detail.errors) showErrors(data.detail.errors);
      else if (status === 401) renderSignIn();
      else showProblem("We couldn't save that step. Please try again.");
    } catch (_) { showProblem("Connection problem. Your earlier answers are saved; try again."); }
    finally { nextBtn.disabled = false; }
  }
  async function goBack() {
    const { status, data } = await api("POST", "/back");
    if (status === 200) renderStage(data); else if (status === 401) renderSignIn();
  }
  function showProblem(msg) {
    const box = el("div", { class: "alert", role: "alert", text: msg });
    main.prepend(box);
  }

  // ------------------------------------------------------------------ passport
  function renderResult(v) {
    $("#progress").hidden = true;
    if (!v.passport || v.status !== "complete") {
      main.append(el("section", { class: "stage" },
        el("img", { class: "illustration", src: "assets/passport.svg", alt: "" }),
        el("p", { class: "group", text: "Your Passport" }),
        el("h1", { text: "Ready to build your Passport" }),
        el("p", { class: "lead", text: "CSS will summarise your answers and explain every recommendation it makes." })));
      actions.hidden = false; backBtn.hidden = false; nextBtn.textContent = "Build my Passport";
      backBtn.onclick = goBack;
      nextBtn.onclick = async () => {
        nextBtn.disabled = true;
        const { status, data } = await api("POST", "/complete");
        nextBtn.disabled = false;
        if (status === 200) renderStage(data);
        else if (status === 422) showProblem("Some required answers are missing. Use Back to review them.");
      };
      return focusTitle();
    }
    actions.hidden = true;
    const p = v.passport;
    const modeText = { DISCOVER: "Discover", CONFIRM: "Confirm" }[p.mode.recommended] || p.mode.recommended;
    const levelPct = { LOW: 33, MODERATE: 66, HIGHER: 100 };
    const why = (because) => because && because.length ? el("details", {}, el("summary", { text: "Why?" }),
      el("ul", { class: "why" }, because.map((b) => el("li", { text: `${b.question_id}: ${Array.isArray(b.answer) ? b.answer.join(", ") : typeof b.answer === "object" ? Object.entries(b.answer).map(([k, x]) => `${k}: ${x}`).join("; ") : b.answer}` })))) : null;
    const chips = (items) => el("ul", { class: "chips" }, (items || []).map((i) => el("li", { text: i })));
    const meter = (label, level) => el("div", { class: "meter" }, el("span", { text: label }),
      el("span", { class: "meter-track", role: "img", "aria-label": `${label}: ${level.toLowerCase()}` },
        el("span", { class: "meter-fill", style: `width:${levelPct[level]}%` })), el("strong", { text: level[0] + level.slice(1).toLowerCase() }));

    main.append(el("section", { class: "stage", "aria-labelledby": "pp-title" },
      el("div", { class: "pp-hero" },
        el("img", { class: "stamp", src: "assets/passport.svg", alt: "" }),
        el("p", { class: "group", text: "CSS Trader Passport" }),
        el("h1", { id: "pp-title", text: p.preferred_name || "Your Passport" }),
        el("p", {}, el("span", { class: "badge", text: `Recommended mode: ${modeText}` }), " ",
          p.mode.simulation_first ? el("span", { class: "badge gold", text: "Start in the simulator" }) : null, " ",
          p.mode.auto_interest_recorded ? el("span", { class: "badge violet", text: "Auto interest recorded" }) : null),
        el("p", { class: "note", text: `Experience: ${p.experience.overall}. Questionnaire ${p.questionnaire_version}, rules ${p.rules_version}.` })),
      el("div", { class: "cards" },
        el("article", { class: "card wide authority" }, el("h2", { text: "What this Passport is, and isn't" }),
          el("p", { text: p.authority_note }), el("p", { class: "note", text: p.legal_acceptance_note }),
          p.mode.note ? el("p", { class: "note", text: p.mode.note }) : null),
        el("article", { class: "card" }, el("h2", { text: "Recommended mode" }), el("p", { text: modeText }),
          el("ul", {}, p.mode.reasons.map((r) => el("li", { text: r }))), why(p.mode.because)),
        el("article", { class: "card" }, el("h2", { text: "Risk" }),
          meter("Capacity", p.risk_capacity.level), meter("Tolerance", p.risk_tolerance.level),
          el("p", { class: "note", text: p.risk_posture.note }),
          p.risk_capacity.limiting_factors.length ? el("ul", {}, p.risk_capacity.limiting_factors.map((f) => el("li", { text: f }))) : null,
          why([...p.risk_capacity.because, ...p.risk_tolerance.because])),
        el("article", { class: "card" }, el("h2", { text: "Strengths" }), chips(p.strengths.self_reported),
          p.strengths.indicated_by_answers.length ? el("p", { class: "note", text: "Indicated by your answers:" }) : null,
          chips(p.strengths.indicated_by_answers.map((s) => s.attribute)), el("p", { class: "note", text: p.strengths.note })),
        el("article", { class: "card" }, el("h2", { text: "Knowledge" }),
          el("p", { class: "note", text: "Shown confidently:" }), chips(p.knowledge.demonstrated),
          el("p", { class: "note", text: "Worth learning next:" }), chips(p.knowledge.gaps.length ? p.knowledge.gaps : ["Nothing flagged"])),
        el("article", { class: "card wide" }, el("h2", { text: "Expectations check" }),
          p.expectations_calibration.length ? p.expectations_calibration.map((f) => el("div", { class: "calib" },
            el("strong", { text: f.code.replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase()) }),
            el("span", { text: f.message }), why(f.because)))
            : el("p", { text: "Your expectations look realistic. CSS still can't guarantee results, and losses remain possible." })),
        p.behavioural_considerations.length ? el("article", { class: "card" }, el("h2", { text: "How CSS will support you" }),
          p.behavioural_considerations.map((b) => el("div", { class: "calib" }, el("strong", { text: b.consideration }), el("span", { text: b.support })))) : null,
        el("article", { class: "card" }, el("h2", { text: "Your learning plan" }),
          el("ol", {}, p.education_plan.map((e) => el("li", { text: e.item })))),
        el("article", { class: "card" }, el("h2", { text: "Markets and timing" }), chips(p.preferred_markets), chips(p.holding_periods),
          el("p", { class: "note", text: Object.values(p.engagement).join(" · ") })),
        el("article", { class: "card" }, el("h2", { text: "Features you chose" }), chips(p.feature_preferences)),
        el("article", { class: "card wide" }, el("h2", { text: "Your results, kept apart" }),
          el("p", { text: "See how CSS-recommended trades and your own trades are reported separately." }),
          el("a", { class: "btn btn-primary", href: "#performance", style: "display:inline-flex;text-decoration:none" }, "View separated results"),
          " ",
          el("button", { type: "button", class: "btn", onclick: goBack }, "Review my answers")))));
    focusTitle();
    announce("Your Trader Passport is ready.");
  }

  // ------------------------------------------------------------------ performance (separated results)
  async function renderPerformance() {
    $("#progress").hidden = true; actions.hidden = true;
    main.replaceChildren(el("p", { class: "note", text: "Loading separated results…" }));
    const { status, data } = await api("GET", "/performance");
    main.replaceChildren();
    const back = el("a", { href: "#", class: "btn", style: "display:inline-flex;text-decoration:none;margin-top:1rem" }, "Back to my Passport");
    if (status === 401) return renderSignIn();
    if (status !== 200) {
      main.append(el("section", { class: "stage" }, el("img", { class: "illustration", src: "assets/two_ledgers.svg", alt: "" }),
        el("h1", { text: "Your results, kept apart" }),
        el("p", { class: "lead", text: (data && data.detail && data.detail.message) || "Results aren't available yet." }), back));
      return focusTitle();
    }
    const segs = Object.fromEntries(data.segments.map((s) => [s.origin, s]));
    const kpi = (dot, s, sub) => el("div", { class: "kpi" },
      el("div", { class: "k-label" }, el("span", { class: `dot ${dot}`, "aria-hidden": "true" }), s.label),
      el("div", { class: `k-value ${s.realized_pnl > 0 ? "pos" : s.realized_pnl < 0 ? "neg" : "zero"}`, text: money(s.realized_pnl) }),
      el("div", { class: "k-sub", text: `${sub} · unrealised ${money(s.unrealized_pnl)} · ${s.wins} won, ${s.losses} lost` }));
    const max = Math.max(1, ...data.segments.map((s) => Math.abs(s.realized_pnl + s.unrealized_pnl)));
    const bars = data.segments.map((s, i) => {
      const v = s.realized_pnl + s.unrealized_pnl, w = Math.round(80 * Math.abs(v) / max), y = 10 + i * 44;
      const color = ["#42d9b8", "#a7a1ff", "#f4c25b", "#8a94a8"][i];
      return [`<text x="0" y="${y + 20}" fill="#eef3fb" font-size="18" font-weight="600">${["CSS", "CSS modified", "Your own", "Review"][i]}</text>`,
        `<rect x="${v >= 0 ? 220 : 220 - w}" y="${y + 4}" width="${Math.max(w, 1)}" height="22" rx="5" fill="${color}"/>`].join("");
    }).join("");
    const chart = el("figure", { class: "card wide", style: "margin:0" },
      el("figcaption", { text: "Profit and loss by origin (realised + unrealised). The line in the middle is zero." }));
    const svg = new DOMParser().parseFromString(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 190" role="img" aria-label="Bar chart of profit and loss by trade origin">` +
      `<line x1="220" y1="4" x2="220" y2="186" stroke="#a9b6cf" stroke-width="2"/>${bars}</svg>`, "image/svg+xml").documentElement;
    chart.append(document.importNode(svg, true));
    const row = (s) => el("tr", {}, el("th", { scope: "row", text: s.label }), el("td", { text: money(s.realized_pnl) }),
      el("td", { text: money(s.unrealized_pnl) }), el("td", { text: String(s.closed_trades) }),
      el("td", { text: `${s.wins}/${s.losses}` }), el("td", { text: String(s.open_positions) }));
    main.append(el("section", { class: "stage", "aria-labelledby": "perf-title" },
      data.data_source === "SAMPLE" ? el("p", { class: "sample", role: "note", text: data.sample_notice }) : null,
      el("p", { class: "group", text: "Separated results" }),
      el("h1", { id: "perf-title", text: "What came from CSS, and what came from you" }),
      el("div", { class: "kpis" },
        kpi("css", segs.CSS_RECOMMENDED, `${segs.CSS_RECOMMENDED.closed_trades} closed`),
        kpi("mod", segs.CSS_RECOMMENDED_MODIFIED, `${segs.CSS_RECOMMENDED_MODIFIED.closed_trades} closed`),
        kpi("user", segs.USER_INDEPENDENT, `${segs.USER_INDEPENDENT.closed_trades} closed`),
        kpi("rev", segs.UNATTRIBUTED_REVIEW_REQUIRED, `${segs.UNATTRIBUTED_REVIEW_REQUIRED.closed_trades} closed`)),
      el("div", { class: "cards", style: "margin-top:.8rem" }, chart,
        el("div", { class: "card wide table-wrap", tabindex: "0", role: "region", "aria-label": "Results by origin table" }, el("table", {},
          el("caption", { text: `Total portfolio: realised ${money(data.total.realized_pnl)}, unrealised ${money(data.total.unrealized_pnl)}` }),
          el("thead", {}, el("tr", {}, ["Origin", "Realised", "Unrealised", "Closed", "Won/lost", "Open"].map((h) => el("th", { scope: "col", text: h })))),
          el("tbody", {}, data.segments.map(row))))),
      el("p", { class: "note", text: data.commercial_note }),
      data.unrealized_incomplete_for.length ? el("p", { class: "note", text: `No current price for: ${data.unrealized_incomplete_for.join(", ")}` }) : null,
      back));
    focusTitle();
  }

  // ------------------------------------------------------------------ sign in (existing CSS auth)
  function renderSignIn() {
    $("#progress").hidden = true; actions.hidden = true;
    const msg = el("p", { class: "error", id: "signin-error", role: "alert", hidden: true });
    const otpField = el("div", { class: "field", hidden: true }, el("label", { for: "otp", text: "One-time code" }),
      el("input", { id: "otp", inputmode: "numeric", autocomplete: "one-time-code" }));
    let stage = "login";
    const form = el("form", {
      onsubmit: async (e) => {
        e.preventDefault(); msg.hidden = true;
        const username = $("#username").value.trim();
        if (stage === "login") {
          const r = await fetch("/auth/login", { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password: $("#password").value }) });
          if (r.ok) { stage = "otp"; otpField.hidden = false; $("#otp").focus(); }
          else { msg.hidden = false; msg.textContent = "Sign-in failed."; }
        } else {
          const r = await fetch("/auth/verify", { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, otp: $("#otp").value.trim() }) });
          const d = r.ok ? await r.json() : null;
          if (d && d.token) { sessionStorage.setItem("css_token", d.token); start(); }
          else { msg.hidden = false; msg.textContent = "That code didn't work."; }
        }
      },
    },
      el("div", { class: "field" }, el("label", { for: "username", text: "Username" }), el("input", { id: "username", autocomplete: "username", required: true })),
      el("div", { class: "field" }, el("label", { for: "password", text: "Password" }), el("input", { id: "password", type: "password", autocomplete: "current-password", required: true })),
      otpField, msg, el("button", { class: "btn btn-primary", type: "submit", style: "width:100%" }, "Continue"));
    main.replaceChildren(el("section", { class: "stage" }, el("h1", { text: "Sign in to start your Passport" }),
      el("p", { class: "lead", text: "Your answers are saved to your CSS account so you can stop and resume any time." }), form));
    focusTitle();
  }

  // ------------------------------------------------------------------ boot
  async function start() {
    if (location.hash === "#performance") return renderPerformance();
    if (!token()) return renderSignIn();
    const { status, data } = await api("GET", "/session");
    if (status === 200) renderStage(data); else renderSignIn();
  }
  window.addEventListener("hashchange", start);
  start();
})();
