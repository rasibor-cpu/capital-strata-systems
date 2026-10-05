/* CSS Trader Passport client (Issue #102, phase 2).
   Server-driven: the API decides which step comes next, validates answers and builds the Passport, so the client
   holds no branching or scoring rules of its own. All user text is inserted with textContent (no HTML injection).
   Accessibility: one h1 per step (focused on change), fieldset/legend groups, labelled inputs, an error summary with
   links plus inline errors linked by aria-describedby, Enter submits the step (real <form>), keyboard-operable
   controls, reduced motion respected by CSS. */
(() => {
  "use strict";
  const API = "/passport";
  const $ = (sel) => document.querySelector(sel);
  const main = $("#main"), live = $("#live"), actions = $("#actions"), nextBtn = $("#next"), backBtn = $("#back");
  let view = null, booted = false;
  const prompts = { knowledge_check: "Knowledge check" };

  const COUNTRIES = [["", "Choose…"], ["US", "United States"], ["CA", "Canada"], ["GB", "United Kingdom"],
    ["IE", "Ireland"], ["AU", "Australia"], ["NZ", "New Zealand"], ["DE", "Germany"], ["FR", "France"],
    ["NL", "Netherlands"], ["ES", "Spain"], ["IT", "Italy"], ["CH", "Switzerland"], ["SE", "Sweden"],
    ["NO", "Norway"], ["DK", "Denmark"], ["SG", "Singapore"], ["HK", "Hong Kong"], ["JP", "Japan"],
    ["IN", "India"], ["AE", "United Arab Emirates"], ["ZA", "South Africa"], ["NG", "Nigeria"], ["KE", "Kenya"],
    ["GH", "Ghana"], ["BR", "Brazil"], ["MX", "Mexico"], ["OT", "Other (tell us later)"]];
  const STATES = ["Foundation", "Developing", "Experienced"];
  const GLYPH = { discover: "◎", confirm: "✓", auto: "⟳", capacity: "▤", tolerance: "≈", css_path: "C", user_path: "Y" };

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
    for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) n.append(c.nodeType ? c : document.createTextNode(c));
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
  function focusTitle() { const h = main.querySelector("h1"); if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); } window.scrollTo(0, 0); }
  const fmtAnswer = (a) => Array.isArray(a) ? a.join(", ") : a && typeof a === "object"
    ? Object.entries(a).map(([k, x]) => `${k}: ${x}`).join("; ") : a === true ? "Yes" : a === false ? "No" : String(a);
  function why(because, basis) {
    if (!(because && because.length) && !basis) return null;
    return el("details", { class: "why-box" }, el("summary", { text: "Why?" }),
      basis ? el("p", { class: "note", text: `Rule: ${basis}` }) : null,
      el("ul", { class: "why" }, (because || []).map((b) => el("li", { "data-qid": b.question_id },
        el("span", { class: "why-q", text: prompts[b.question_id] || b.question_id }), " — ",
        el("strong", { text: fmtAnswer(b.answer) })))));
  }

  // ------------------------------------------------------------------ progress
  function setProgress(p, group) {
    $("#progress").hidden = false;
    const pos = Math.min(p.position, p.total), bar = $("#progressbar");
    bar.setAttribute("aria-valuemax", String(p.total));
    bar.setAttribute("aria-valuenow", String(pos));
    bar.setAttribute("aria-valuetext", `Step ${pos} of ${p.total}${group ? `, ${group}` : ""}`);
    $("#progress-fill").style.width = `${Math.round(100 * pos / p.total)}%`;
    $("#progress-text").textContent = `Step ${pos} of ${p.total}`;
    $("#progress-group").textContent = group || "";
  }

  // ------------------------------------------------------------------ question widgets
  function optionInput(type, name, opt, checked) {
    const id = `${name}-${opt.value}`;
    return el("div", { class: "option" },
      el("input", { type, id, name, value: opt.value, checked: !!checked }),
      el("label", { for: id }, el("span", { class: "tick", "aria-hidden": "true" }),
        el("span", { class: "opt-text" }, el("span", { text: opt.label }),
          opt.detail ? el("span", { class: "opt-detail", text: opt.detail }) : null)));
  }
  const firstControlId = (q) => ["single", "quiz", "multi"].includes(q.type) ? `${q.id}-${q.options[0].value}`
    : q.type === "boolean" ? `${q.id}-true` : q.type === "matrix" ? `${q.id}__${q.rows[0].value}-${q.options[0].value}`
      : q.type === "rank" ? `${q.id}-rank-0` : q.id;
  const selectHint = (q) => {
    const lo = q.min_select ?? (q.required ? 1 : 0), hi = q.max_select ?? q.options.length;
    return lo === hi ? `Choose ${hi}.` : hi < q.options.length ? `Choose up to ${hi}.` : "Choose all that apply.";
  };

  function renderQuestion(q, value) {
    const errId = `err-${q.id}`, helpId = `help-${q.id}`;
    const err = el("p", { class: "error", id: errId, hidden: true });
    const helpText = [q.help, ["multi"].includes(q.type) ? selectHint(q) : null].filter(Boolean).join(" ");
    const help = helpText ? el("p", { class: "help", id: helpId, text: helpText }) : null;
    const described = [help ? helpId : null, errId].filter(Boolean).join(" ");
    const req = q.required || /optional/i.test(q.prompt) ? null : el("span", { class: "note", text: " (optional)" });
    const purpose = q.purpose && !q.must_be_true ? el("details", { class: "purpose" }, el("summary", { text: "Why we ask" }),
      el("p", { text: q.purpose })) : null;
    const wrap = (inner) => el("div", { class: "q", "data-qid": q.id, "data-type": q.type }, inner, err, purpose);

    if (["text", "email", "phone"].includes(q.type)) {
      const attrs = { id: q.id, name: q.id, value: value ?? "", "aria-describedby": described, maxlength: q.max_len || 120,
        type: q.type === "email" ? "email" : q.type === "phone" ? "tel" : "text",
        autocomplete: { display_name: "nickname", full_name: "name", email: "email", phone: "tel" }[q.id] || "off",
        inputmode: q.type === "phone" ? "tel" : q.type === "email" ? "email" : null, required: q.required,
        enterkeyhint: "next" };
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
      const many = opts.length >= 5 && opts.every((o) => !o.detail && o.label.length <= 34);
      return wrap(el("fieldset", { "aria-describedby": described },
        el("legend", {}, q.prompt, req), help,
        el("div", { class: `options${many ? " many" : ""}${q.type === "boolean" ? " pair" : ""}`, role: "radiogroup" },
          opts.map((o) => optionInput("radio", q.id, o, cur === o.value)))));
    }
    if (q.type === "multi") {
      const cur = Array.isArray(value) ? value : [];
      const many = q.options.length >= 5 && q.options.every((o) => !o.detail && o.label.length <= 34);
      return wrap(el("fieldset", { "aria-describedby": described },
        el("legend", {}, q.prompt, req), help,
        el("div", { class: `options${many ? " many" : ""}` }, q.options.map((o) => optionInput("checkbox", q.id, o, cur.includes(o.value))))));
    }
    if (q.type === "matrix") {
      const cur = value || {};
      return wrap(el("fieldset", { "aria-describedby": described }, el("legend", {}, q.prompt), help,
        el("div", { class: "matrix" }, q.rows.map((r) => el("fieldset", { class: "matrix-row", "data-row": r.value },
          el("legend", { text: r.label }),
          el("div", { class: "segmented" }, q.options.map((o) => optionInput("radio", `${q.id}__${r.value}`, o, cur[r.value] === o.value))))))));
    }
    if (q.type === "rank") {
      const max = q.max_select || 3;
      const list = el("div", { class: "options", "data-order": JSON.stringify(Array.isArray(value) ? value : []) });
      const count = el("p", { class: "rank-count note" });
      const paint = () => {
        const ord = JSON.parse(list.dataset.order);
        list.querySelectorAll("button").forEach((b) => {
          const i = ord.indexOf(b.dataset.value);
          b.setAttribute("aria-pressed", i >= 0 ? "true" : "false");
          b.querySelector(".tick").textContent = i >= 0 ? String(i + 1) : "";
          b.setAttribute("aria-label", `${b.dataset.label}${i >= 0 ? `, ranked ${i + 1}` : ""}`);
        });
        count.textContent = `${ord.length} of ${max} chosen`;
        clear.hidden = ord.length === 0;
      };
      const clear = el("button", { type: "button", class: "btn btn-quiet", onclick: () => { list.dataset.order = "[]"; paint(); announce("Ranking cleared"); } }, "Clear ranking");
      q.options.forEach((o, idx) => list.append(el("button", {
        type: "button", class: "rank-btn", id: `${q.id}-rank-${idx}`, "data-value": o.value, "data-label": o.label, "aria-pressed": "false",
        onclick: () => {
          const ord = JSON.parse(list.dataset.order);
          const i = ord.indexOf(o.value);
          if (i >= 0) ord.splice(i, 1); else if (ord.length < max) ord.push(o.value);
          list.dataset.order = JSON.stringify(ord); paint();
          announce(i >= 0 ? `${o.label} removed` : ord.includes(o.value) ? `${o.label} ranked ${ord.length}` : `You've chosen ${max}. Remove one to change.`);
        },
      }, el("span", { class: "tick", "aria-hidden": "true" }), el("span", { text: o.label }))));
      const rankHelp = el("p", { class: "help", id: helpId, text: `${q.help ? q.help + " " : ""}Tap your top ${max} in order. Tap again to remove.` });
      setTimeout(paint);
      return wrap(el("fieldset", { "aria-describedby": `${helpId} ${errId}` }, el("legend", {}, q.prompt), rankHelp, list,
        el("div", { class: "rank-tools" }, count, clear)));
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

  function showErrors(errors, stage) {
    main.querySelectorAll(".error[id^=err-]").forEach((e) => { e.hidden = true; e.textContent = ""; });
    main.querySelectorAll("[aria-invalid]").forEach((n) => n.removeAttribute("aria-invalid"));
    main.querySelectorAll(".error-summary").forEach((n) => n.remove());
    const items = [];
    for (const [qid, msg] of Object.entries(errors)) {
      const q = (stage.questions || []).find((x) => x.id === qid);
      const e = main.querySelector(`#err-${CSS.escape(qid)}`);
      if (!e || !q) continue;
      e.hidden = false; e.textContent = msg;
      const ctl = main.querySelector(`#${CSS.escape(firstControlId(q))}`);
      if (ctl) ctl.setAttribute("aria-invalid", "true");
      items.push(el("li", {}, el("a", { href: `#${firstControlId(q)}`, onclick: (ev) => { ev.preventDefault(); if (ctl) ctl.focus(); } },
        `${q.prompt.length > 70 ? q.prompt.slice(0, 67) + "…" : q.prompt}: ${msg}`)));
    }
    const n = items.length;
    const msg = n === 1 ? "There is one thing to fix on this step." : `There are ${n} things to fix on this step.`;
    if (n > 1) {   // a single error is already beside its field; several get a linked summary at the top
      const box = el("div", { class: "error-summary", tabindex: "-1", "aria-labelledby": "err-sum-title" },
        el("h2", { id: "err-sum-title", text: msg }), el("ul", {}, items));
      main.querySelector("form").prepend(box);
    }
    announce(msg);
    const first = main.querySelector("[aria-invalid=true]");
    if (first) first.focus();
  }

  // ------------------------------------------------------------------ stage rendering
  function banner(v) {
    if (booted) return null;
    if (v.status === "reviewing")
      return el("div", { class: "banner", role: "status" }, el("strong", { text: "Reviewing your answers." }),
        " Your Passport updates when you reach the end again.");
    if (v.status === "in_progress" && v.progress.position > 1)
      return el("div", { class: "banner", role: "status" }, el("strong", { text: "Welcome back." }),
        ` Your answers are saved. You're on step ${v.progress.position} of ${v.progress.total}.`);
    return null;
  }

  function renderStage(v) {
    view = v;
    const s = v.stage;
    main.replaceChildren();
    if (s.kind === "result") { booted = true; return renderResult(v); }
    setProgress(v.progress, s.group);
    const form = el("form", { id: "stage-form", novalidate: true, onsubmit: (e) => { e.preventDefault(); submit(s); } },
      (s.questions || []).map((q) => renderQuestion(q, v.answers[q.id])));
    const content = el("section", { class: `stage stage-${s.kind}`, "aria-labelledby": "stage-title" },
      banner(v),
      el("p", { class: "group", text: s.group }),
      el("h1", { id: "stage-title", text: s.title }),
      s.body ? el("div", { class: "lead" }, s.body.map((p) => el("p", { text: p }))) : null,
      s.points ? el("ul", { class: "points" }, s.points.map((p) => el("li", { class: `point point-${p.icon}` },
        el("span", { class: "point-icon", "aria-hidden": "true", text: GLYPH[p.icon] || "•" }),
        el("span", {}, el("strong", { text: p.title }), el("span", { text: p.text }))))) : null,
      s.callout ? el("p", { class: "callout", role: "note", text: s.callout }) : null,
      form);
    const art = s.illustration ? el("img", { class: "illustration", src: `assets/${s.illustration}.svg`, alt: "" }) : null;
    main.append(art ? el("div", { class: "split" }, art, content) : content);
    booted = true;
    actions.hidden = false;
    backBtn.hidden = v.progress.position <= 1;
    nextBtn.textContent = s.kind === "interstitial" && !(s.questions || []).length ? "Got it, continue" : "Continue";
    nextBtn.setAttribute("form", "stage-form");
    nextBtn.type = "submit";
    nextBtn.onclick = null;
    backBtn.onclick = goBack;
    focusTitle();
    announce(`Step ${Math.min(v.progress.position, v.progress.total)} of ${v.progress.total}: ${s.title}`);
  }

  async function submit(stage) {
    if (nextBtn.disabled) return;
    nextBtn.disabled = true; nextBtn.setAttribute("aria-busy", "true");
    try {
      const { status, data } = await api("POST", "/answer", { stage_id: stage.id, answers: collect(stage) });
      if (status === 200) renderStage(data);
      else if (status === 422 && data && data.detail && data.detail.errors) showErrors(data.detail.errors, stage);
      else if (status === 401) renderSignIn();
      else showProblem("We couldn't save that step. Please try again.");
    } catch (_) { showProblem("Connection problem. Your earlier answers are saved; try again."); }
    finally { nextBtn.disabled = false; nextBtn.removeAttribute("aria-busy"); }
  }
  async function goBack() {
    const { status, data } = await api("POST", "/back");
    if (status === 200) renderStage(data); else if (status === 401) renderSignIn();
  }
  function showProblem(msg) {
    main.querySelectorAll(".alert").forEach((n) => n.remove());
    const box = el("div", { class: "alert", role: "alert", text: msg });
    (main.querySelector("section") || main).prepend(box);
  }

  // ------------------------------------------------------------------ passport
  function stateScale(d) {
    const i = STATES.indexOf(d.state);
    if (i < 0) return el("p", { class: "dim-state descriptive" }, el("span", { class: "tag", text: d.state }));
    return el("div", { class: "dim-state" },
      el("span", { class: "scale", role: "img", "aria-label": `${d.state}: step ${i + 1} of 3 (Foundation, Developing, Experienced)` },
        STATES.map((_, j) => el("span", { class: `pip${j <= i ? " on" : ""}` }))),
      el("strong", { text: d.state }));
  }

  function renderResult(v) {
    $("#progress").hidden = true;
    nextBtn.removeAttribute("form"); nextBtn.type = "button";
    if (!v.passport || v.status !== "complete") {
      const missing = (v.missing_required || []).length;
      main.append(el("section", { class: "stage", "aria-labelledby": "ready-title" },
        el("img", { class: "illustration small", src: "assets/passport.svg", alt: "" }),
        el("p", { class: "group", text: "Your Passport" }),
        el("h1", { id: "ready-title", text: "Ready to build your Passport" }),
        el("div", { class: "lead" }, el("p", { text: "CSS will summarise your answers into six areas and show which answers led to each result." }),
          el("p", { text: "Your Passport is guidance. It doesn't approve you for live trading or switch on any automation." })),
        missing ? el("p", { class: "alert", role: "alert", text: `${missing} required answer${missing > 1 ? "s are" : " is"} missing. Use Back to review.` }) : null));
      actions.hidden = false; backBtn.hidden = false; nextBtn.textContent = "Build my Passport";
      backBtn.onclick = goBack;
      nextBtn.onclick = async () => {
        nextBtn.disabled = true;
        const { status, data } = await api("POST", "/complete");
        nextBtn.disabled = false;
        if (status === 200) renderStage(data);
        else if (status === 422) showProblem("Some required answers are missing. Use Back to review them.");
        else if (status === 401) renderSignIn();
      };
      return focusTitle();
    }
    actions.hidden = true;
    const p = v.passport;
    const modeText = { DISCOVER: "Discover", CONFIRM: "Confirm" }[p.mode.recommended] || p.mode.recommended;
    const levelPct = { LOW: 33, MODERATE: 66, HIGHER: 100 };
    const chips = (items, cls = "") => el("ul", { class: `chips ${cls}` }, (items || []).map((i) => el("li", { text: i })));
    const meter = (label, level) => el("div", { class: "meter" }, el("span", { text: label }),
      el("span", { class: "meter-track", role: "img", "aria-label": `${label}: ${level.toLowerCase()}` },
        el("span", { class: "meter-fill", style: `width:${levelPct[level]}%` })), el("strong", { text: level[0] + level.slice(1).toLowerCase() }));
    const card = (title, cls, ...kids) => el("article", { class: `card ${cls}` }, el("h2", { text: title }), ...kids);

    main.append(el("section", { class: "stage passport", "aria-labelledby": "pp-title" },
      el("div", { class: "pp-hero" },
        el("img", { class: "stamp", src: "assets/passport.svg", alt: "" }),
        el("p", { class: "group", text: "CSS Trader Passport" }),
        el("h1", { id: "pp-title", text: p.preferred_name ? `${p.preferred_name}'s Passport` : "Your Passport" }),
        el("p", { class: "badges" }, el("span", { class: "badge", text: `Starting mode: ${modeText}` }),
          p.mode.simulation_first ? el("span", { class: "badge gold", text: "Practise in the simulator first" }) : null,
          p.mode.auto_interest_recorded ? el("span", { class: "badge violet", text: "Auto interest noted (not enabled)" }) : null),
        el("p", { class: "note", text: `Built from your answers · questionnaire ${p.questionnaire_version} · rules ${p.rules_version}` })),
      el("div", { class: "authority" }, el("h2", { text: "What this Passport is, and isn't" }),
        el("p", { text: p.authority_note }), el("p", { text: p.suitability_note }),
        el("p", { class: "note", text: p.legal_acceptance_note })),
      el("h2", { class: "section-title", text: "Your six areas" }),
      el("div", { class: "dims" }, p.dimensions.map((d) => el("article", { class: "card dim", "data-dimension": d.dimension },
        el("h3", { text: d.dimension }), stateScale(d), el("p", { class: "dim-summary", text: d.summary }), why(d.because, d.basis)))),
      el("div", { class: "cards" },
        card("Strengths", "", el("ul", { class: "list" }, p.strengths.map((s) => el("li", {},
          el("span", { text: s.strength }), " ", el("span", { class: "tag small", text: s.source })))),
          why(p.strengths.flatMap((s) => s.because))),
        card("Areas to develop", "", p.development_areas.length
          ? el("ul", { class: "list" }, p.development_areas.map((d) => el("li", {}, el("strong", { text: d.area }), el("span", { class: "note block", text: d.note }))))
          : el("p", { text: "Nothing specific flagged. CSS will still explain each recommendation." }),
          why(p.development_areas.flatMap((d) => d.because))),
        card("Starting mode", "", el("p", { class: "big", text: modeText }),
          el("ul", { class: "list" }, p.mode.reasons.map((r) => el("li", { text: r }))),
          p.mode.note ? el("p", { class: "note", text: p.mode.note }) : null,
          el("p", { class: "note", text: "Auto is never recommended by onboarding. It needs a separate, governed authorisation." }),
          why(p.mode.because)),
        card("Risk", "", meter("Capacity", p.risk_capacity.level), meter("Tolerance", p.risk_tolerance.level),
          el("p", { class: "note", text: p.risk_posture.note }),
          p.risk_capacity.limiting_factors.length ? el("ul", { class: "list" }, p.risk_capacity.limiting_factors.map((f) => el("li", { text: f }))) : null,
          el("p", { class: "note", text: `Loss you could absorb: ${p.loss_tolerance.capacity_band}; ${p.loss_tolerance.comfort}.` }),
          why([...p.risk_capacity.because, ...p.risk_tolerance.because])),
        card("Markets and engagement", "", el("p", { class: "label", text: "Markets" }), chips(p.preferred_markets),
          el("p", { class: "label", text: "Holding periods" }), chips(p.holding_periods),
          el("p", { class: "label", text: "Engagement style" }), el("p", {}, el("strong", { text: p.engagement.style }), ". ", p.engagement.summary),
          el("p", { class: "note", text: `Leverage: ${p.leverage.familiarity}.` }),
          why([...p.engagement.because, ...p.leverage.because])),
        card("Your learning plan", "", p.education_plan.length
          ? el("ol", { class: "list" }, p.education_plan.map((e) => el("li", {}, el("span", { text: e.item }), el("span", { class: "note block", text: e.why }))))
          : el("p", { text: "No gaps flagged. Learning resources stay available any time." })),
        card("Expectations check", "wide", p.expectations_calibration.length
          ? p.expectations_calibration.map((f) => el("div", { class: `calib ${f.severity}` },
            el("strong", { text: f.code.replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase()) }),
            el("span", { text: f.message }), why(f.because)))
          : el("p", { text: "Your expectations look realistic. CSS still can't guarantee results, and losses remain possible." })),
        card("Your results, kept apart", "wide",
          el("p", { text: "Trades from CSS recommendations and trades you choose yourself are reported separately, with a combined total." }),
          el("div", { class: "row-actions" },
            el("a", { class: "btn btn-primary", href: "#performance" }, "See how results are separated"),
            el("button", { type: "button", class: "btn", onclick: goBack }, "Review my answers"))))));
    focusTitle();
    announce("Your Trader Passport is ready.");
  }

  // ------------------------------------------------------------------ performance (separated results)
  async function renderPerformance() {
    $("#progress").hidden = true; actions.hidden = true;
    main.replaceChildren(el("p", { class: "note", text: "Loading separated results…" }));
    const { status, data } = await api("GET", "/performance");
    main.replaceChildren();
    const back = el("a", { href: "#", class: "btn" }, "Back to my Passport");
    if (status === 401) return renderSignIn();
    if (status !== 200) {
      main.append(el("section", { class: "stage", "aria-labelledby": "perf-title" }, el("img", { class: "illustration small", src: "assets/two_ledgers.svg", alt: "" }),
        el("h1", { id: "perf-title", text: "Your results, kept apart" }),
        el("p", { class: "lead", text: (data && data.detail && data.detail.message) || "Results aren't available yet." }), back));
      return focusTitle();
    }
    const views = data.views;
    const cls = (x) => x > 0 ? "pos" : x < 0 ? "neg" : "zero";
    const kpi = (dot, label, real, unreal, sub) => el("div", { class: `kpi kpi-${dot}` },
      el("div", { class: "k-label" }, el("span", { class: `dot ${dot}`, "aria-hidden": "true" }), label),
      el("div", { class: `k-value ${cls(real)}`, text: money(real) }),
      el("div", { class: "k-sub", text: `Realised. Open positions ${money(unreal)}${sub ? ` · ${sub}` : ""}` }));
    const segs = Object.fromEntries(data.segments.map((s) => [s.origin, s]));
    const closed = (...o) => o.reduce((n, k) => n + segs[k].closed_trades, 0);
    const max = Math.max(1, ...data.segments.map((s) => Math.abs(s.realized_pnl + s.unrealized_pnl)));
    const colors = { CSS_RECOMMENDED: "#42d9b8", CSS_RECOMMENDED_MODIFIED: "#a7a1ff", USER_INDEPENDENT: "#f4c25b", ORIGIN_UNDER_REVIEW: "#8a94a8" };
    const short = { CSS_RECOMMENDED: "CSS", CSS_RECOMMENDED_MODIFIED: "CSS, modified", USER_INDEPENDENT: "Your own", ORIGIN_UNDER_REVIEW: "Under review" };
    const bars = data.segments.map((s, i) => {
      const v = s.realized_pnl + s.unrealized_pnl, w = Math.round(80 * Math.abs(v) / max), y = 10 + i * 44;
      return `<text x="0" y="${y + 20}" fill="#eef3fb" font-size="17" font-weight="600">${short[s.origin]}</text>` +
        `<rect x="${v >= 0 ? 220 : 220 - w}" y="${y + 4}" width="${Math.max(w, 1)}" height="22" rx="5" fill="${colors[s.origin]}"/>`;
    }).join("");
    const chart = el("figure", { class: "card chart wide" },
      el("figcaption", { text: "Each origin, realised + unrealised. The vertical line is zero." }));
    const svg = new DOMParser().parseFromString(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 190" role="img" aria-label="Bar chart of profit and loss by trade origin; values are in the table">` +
      `<line x1="220" y1="4" x2="220" y2="186" stroke="#a9b6cf" stroke-width="2"/>${bars}</svg>`, "image/svg+xml").documentElement;
    chart.append(document.importNode(svg, true));
    const row = (s) => el("tr", {}, el("th", { scope: "row" }, el("span", { class: "dot", style: `background:${colors[s.origin]}`, "aria-hidden": "true" }), " ", s.label),
      el("td", { text: money(s.realized_pnl) }), el("td", { text: money(s.unrealized_pnl) }), el("td", { text: String(s.closed_trades) }),
      el("td", { text: `${s.wins}/${s.losses}` }), el("td", { text: String(s.open_positions) }));
    main.append(el("section", { class: "stage", "aria-labelledby": "perf-title" },
      data.data_source === "SAMPLE" ? el("p", { class: "sample", role: "note", text: data.sample_notice }) : null,
      el("p", { class: "group", text: "Separated results" }),
      el("h1", { id: "perf-title", text: "What came from CSS, and what came from you" }),
      el("div", { class: "kpis" },
        kpi("css", views.css_attributable.label, views.css_attributable.realized_pnl, views.css_attributable.unrealized_pnl,
          `${closed("CSS_RECOMMENDED", "CSS_RECOMMENDED_MODIFIED")} closed`),
        kpi("user", views.independent.label, views.independent.realized_pnl, views.independent.unrealized_pnl,
          `${closed("USER_INDEPENDENT")} closed`),
        kpi("total", views.combined.label, views.combined.realized_pnl, views.combined.unrealized_pnl, "everything together")),
      el("p", { class: "note", text: `CSS-attributable includes trades you modified (${money(segs.CSS_RECOMMENDED_MODIFIED.realized_pnl)} realised), shown separately below. ` +
        `Origin under review: ${money(views.under_review.realized_pnl)} realised, not counted as CSS or yours until resolved.` }),
      el("h2", { class: "section-title", text: "By origin" }),
      el("div", { class: "cards" }, chart,
        el("div", { class: "card wide table-wrap", tabindex: "0", role: "region", "aria-label": "Results by origin table" }, el("table", {},
          el("caption", { text: `Combined: realised ${money(data.total.realized_pnl)}, unrealised ${money(data.total.unrealized_pnl)}` }),
          el("thead", {}, el("tr", {}, ["Origin", "Realised", "Unrealised", "Closed", "Won/lost", "Open"].map((h) => el("th", { scope: "col", text: h })))),
          el("tbody", {}, data.segments.map(row))))),
      el("p", { class: "note", text: "CSS recommendations are not guaranteed profits. You remain responsible for every trade you place." }),
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
      otpField, msg, el("button", { class: "btn btn-primary full", type: "submit" }, "Continue"));
    main.replaceChildren(el("section", { class: "stage" }, el("h1", { text: "Sign in to start your Passport" }),
      el("p", { class: "lead", text: "Your answers are saved to your CSS account so you can stop and resume any time." }), form));
    focusTitle();
  }

  // ------------------------------------------------------------------ boot
  async function loadPrompts() {
    if (Object.keys(prompts).length > 1) return;
    try {
      const { status, data } = await api("GET", "/schema");
      if (status === 200) for (const s of data.stages) for (const q of s.questions || []) prompts[q.id] = q.prompt;
    } catch (_) { /* Why? falls back to question ids */ }
  }
  async function start() {
    await loadPrompts();
    if (location.hash === "#performance") return renderPerformance();
    if (!token()) return renderSignIn();
    const { status, data } = await api("GET", "/session");
    if (status === 200) renderStage(data); else renderSignIn();
  }
  window.addEventListener("hashchange", start);
  start();
})();
