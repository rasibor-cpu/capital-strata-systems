"""CSS Trader Passport: versioned onboarding questionnaire (Issue #102).

Pure data. The server engine, the web UI and the tests all read this one definition, so branching and
validation cannot drift between client and server.

Governance:
- Nothing in this questionnaire grants, changes or implies execution authority. AUTO is recorded as *interest* only.
- Acknowledgements here are educational acknowledgements. Formal acceptance of the legal terms and the trading-risk
  disclosure remains with backend.app.compliance.legal_acceptance* and is not replaced or satisfied by onboarding.
- No question asks for credentials, account numbers or other secrets.
- Wording is original to CSS. It makes no earnings claims and no income-replacement promises.

Stage kinds:
  interstitial  - explanatory screen, may carry an illustration id and optional acknowledgement questions
  question      - one principal decision (one or a few closely related inputs)
  result        - the Trader Passport summary (computed, not answered)

Question types: single, multi, text, email, phone, country, consent, quiz (single answer with a correct key),
boolean (true/false belief check), rank (ordered top-N), matrix (one band per row).

show_if conditions (evaluated by engine.condition_met):
  {"any_of": [cond, ...]}, {"all_of": [cond, ...]}, {"not": cond},
  {"q": "<question id>", "in": [values]}            single/boolean answer is one of values
  {"q": "<question id>", "includes_any": [values]}  multi answer contains any of values
  {"q": "<matrix id>", "row_in": {"rows": [...], "values": [...]}}  any listed row has one of values
"""
from __future__ import annotations

QUESTIONNAIRE_ID = "css_trader_passport"
QUESTIONNAIRE_VERSION = "TP-Q-1.0.0"

EXPERIENCE_BANDS = [
    {"value": "none", "label": "None"},
    {"value": "beginner", "label": "Beginner"},
    {"value": "intermediate", "label": "Intermediate"},
    {"value": "experienced", "label": "Experienced"},
]
ASSET_CLASSES = [
    {"value": "equities", "label": "Stocks (equities)"},
    {"value": "etfs", "label": "ETFs"},
    {"value": "fx", "label": "Currencies (FX)"},
    {"value": "crypto", "label": "Crypto"},
    {"value": "options", "label": "Options"},
    {"value": "futures", "label": "Futures"},
]
LEVERAGED_CLASSES = ["fx", "crypto", "options", "futures"]
NOT_SURE = {"value": "not_sure", "label": "I'm not sure yet"}


def _opts(*pairs):
    return [{"value": v, "label": l} for v, l in pairs]


def _quiz(qid, topic, prompt, options, correct, explain):
    return {"id": qid, "type": "quiz", "topic": topic, "prompt": prompt, "required": True,
            "options": options + [NOT_SURE], "correct": correct, "explain": explain}


STAGES = [
    # ------------------------------------------------------------------ 1. WELCOME
    {"id": "welcome", "kind": "interstitial", "group": "Welcome", "illustration": "compass",
     "title": "Welcome to your CSS Trader Passport",
     "body": [
         "CSS is governance-first decision support. It analyses markets, explains what it sees and, where you allow it, "
         "proposes trades as CSS Trade Cards.",
         "Discover: CSS surfaces opportunities and analysis; every decision is yours. "
         "Confirm: CSS proposes governed Trade Cards; nothing happens unless you confirm it. "
         "Auto: governed automated execution, only where it is legally, operationally and technically available "
         "and separately authorised. This questionnaire never switches it on.",
         "Trading involves risk, including the loss of money you put in. CSS does not guarantee profit, and past "
         "results do not predict future results.",
     ],
     "questions": [
         {"id": "ack_risk_intro", "type": "consent", "required": True, "must_be_true": True,
          "prompt": "I understand that trading involves risk and that CSS does not guarantee profit."},
     ]},

    # ------------------------------------------------------------------ 2. IDENTITY + CONTACT
    {"id": "identity", "kind": "question", "group": "About you", "title": "About you",
     "questions": [
         {"id": "display_name", "type": "text", "required": True, "min_len": 2, "max_len": 40,
          "prompt": "Preferred name", "help": "Shown in your Passport and on screen. A nickname is fine."},
         {"id": "full_name", "type": "text", "required": False, "min_len": 0, "max_len": 120, "sensitive": True,
          "prompt": "Full legal name (optional)",
          "help": "Only needed later if you connect a brokerage account, which asks for it under its own checks."},
         {"id": "email", "type": "email", "required": True, "sensitive": True, "prompt": "Email"},
         {"id": "phone", "type": "phone", "required": False, "sensitive": True, "prompt": "Mobile number (optional)",
          "help": "International format, e.g. +1 416 555 0100. Only used if you choose text messages."},
         {"id": "country", "type": "country", "required": True, "prompt": "Country or region",
          "help": "Some CSS features depend on where you live."},
         {"id": "preferred_channel", "type": "single", "required": True, "prompt": "Preferred way to hear from CSS",
          "options": _opts(("in_app", "In the app"), ("email", "Email"), ("push", "Push notifications"),
                           ("sms", "Text message"))},
         {"id": "consent_service_notifications", "type": "consent", "required": False,
          "prompt": "Send me alerts and service notifications for features I turn on."},
         {"id": "consent_marketing", "type": "consent", "required": False,
          "prompt": "Send me occasional product news. (Optional, and separate from alerts.)"},
     ]},

    # ------------------------------------------------------------------ 3. OBJECTIVE
    {"id": "objective", "kind": "question", "group": "Your goals", "title": "Your goals and priorities",
     "questions": [
         {"id": "objectives", "type": "multi", "required": True, "min_select": 1, "max_select": 3,
          "prompt": "Choose up to three.",
          "options": _opts(("learn", "Learn to trade"), ("improve_process", "Improve my existing process"),
                           ("supplement_investing", "Add to my wider investing"), ("active_trading", "Trade actively"),
                           ("diversify", "Diversify my portfolio"), ("systematic_support", "Systematic decision support"),
                           ("discipline", "Become more disciplined"), ("new_markets", "Explore new markets"))},
         {"id": "objective_ranking", "type": "rank", "required": True, "min_select": 3, "max_select": 3,
          "prompt": "Pick your top three, most important first.",
          "options": _opts(("preservation", "Protect what I have"), ("steady_growth", "Steady growth"),
                           ("learning", "Learning"), ("supplement", "Supplement other investments"),
                           ("aggressive_growth", "Aggressive growth"), ("diversification", "Diversification"))},
     ]},

    # ------------------------------------------------------------------ 4. EXPERIENCE
    {"id": "experience", "kind": "question", "group": "Experience", "title": "Your experience by market",
     "questions": [
         {"id": "experience_by_class", "type": "matrix", "required": True, "rows": ASSET_CLASSES,
          "options": EXPERIENCE_BANDS,
          "prompt": "Pick the closest band for each. 'None' is a perfectly good answer.",
          "help": "Beginner: a few trades or paper trading. Intermediate: regular trading for a year or more. "
                  "Experienced: several years, through different market conditions."},
     ]},

    # ------------------------------------------------------------------ 5. KNOWLEDGE
    {"id": "knowledge_intro", "kind": "interstitial", "group": "Knowledge", "illustration": "toolkit",
     "title": "A quick knowledge check, not a test",
     "body": ["A few short questions help CSS decide which explanations to show you.",
              "There is no pass mark. 'I'm not sure yet' is always an option and simply points you to the right lesson."]},
    {"id": "knowledge_core", "kind": "question", "group": "Knowledge", "title": "Orders and sizing",
     "questions": [
         _quiz("kq_market_vs_limit", "order_types", "What does a limit order do?",
               _opts(("a", "Fills immediately at whatever the market price is"),
                     ("b", "Fills only at your chosen price or better"),
                     ("c", "Closes a trade automatically after a loss")), "b",
               "A limit order sets the worst price you accept. It may not fill at all."),
         _quiz("kq_stop", "stop_orders", "A stop-loss order is mainly used to…",
               _opts(("a", "Guarantee the exit price"), ("b", "Limit a loss by exiting once a price is reached"),
                     ("c", "Increase position size when price falls")), "b",
               "A stop triggers an exit at a level you set. In fast markets the fill can be worse than the stop price."),
         _quiz("kq_position_size", "position_sizing",
               "With a $10,000 account and a 1% risk rule, the most you plan to lose on one trade is…",
               _opts(("a", "$10"), ("b", "$100"), ("c", "$1,000")), "b",
               "1% of $10,000 is $100. Position size is then set so that hitting your stop loses about that much."),
         _quiz("kq_risk_reward", "risk_reward",
               "A trade risks $50 to make $150. Its reward-to-risk ratio is…",
               _opts(("a", "1 : 3"), ("b", "3 : 1"), ("c", "It depends on the win rate only")), "b",
               "$150 ÷ $50 = 3. A good ratio still needs a sensible win rate to pay off over time."),
     ]},
    {"id": "knowledge_risk", "kind": "question", "group": "Knowledge", "title": "Volatility, drawdown and diversification",
     "questions": [
         _quiz("kq_volatility", "volatility", "Higher volatility usually means…",
               _opts(("a", "Larger and faster price swings, up and down"), ("b", "Prices only go up"),
                     ("c", "Less risk")), "a",
               "Volatility measures how widely prices move. It widens both gains and losses."),
         _quiz("kq_drawdown", "drawdown",
               "An account falls from $12,000 to $9,000 before recovering. The drawdown was…",
               _opts(("a", "$9,000"), ("b", "25%"), ("c", "75%")), "b",
               "Drawdown is the fall from a peak: $3,000 ÷ $12,000 = 25%."),
         _quiz("kq_diversification", "diversification", "Diversification aims to…",
               _opts(("a", "Remove all risk"), ("b", "Reduce the impact of any single position going wrong"),
                     ("c", "Guarantee higher returns")), "b",
               "Spreading exposure lowers the damage one position can do. It cannot remove market-wide risk."),
         _quiz("kq_exposure", "portfolio_exposure",
               "You hold three different tech stocks, each 20% of your account. Your exposure to the tech sector is…",
               _opts(("a", "About 20%"), ("b", "About 60%"), ("c", "Unknown without prices")), "b",
               "Three positions in one sector add up: 3 × 20% = 60% exposure to that sector."),
     ]},

    # ------------------------------------------------------------------ 6. STRENGTHS
    {"id": "strengths", "kind": "question", "group": "How you work", "title": "Which of these sound like you?",
     "questions": [
         {"id": "strengths", "type": "multi", "required": True, "min_select": 1, "max_select": 4,
          "prompt": "Choose up to four.",
          "options": _opts(("detail", "Detail-oriented"), ("quantitative", "Quantitative"),
                           ("pattern", "Pattern-focused"), ("disciplined", "Disciplined / process-driven"),
                           ("patient", "Patient"), ("big_picture", "Fundamental / big-picture"),
                           ("research", "Research-oriented"), ("decisive", "Decisive"), ("risk_aware", "Risk-aware"))},
     ]},

    # ------------------------------------------------------------------ 7. DECISION BEHAVIOUR
    {"id": "behaviour", "kind": "question", "group": "How you work", "title": "How you make decisions",
     "body": ["There are no right answers here. CSS uses them to pace alerts and reminders, not to judge you."],
     "questions": [
         {"id": "bh_time_pressure", "type": "single", "required": True,
          "prompt": "Making decisions under time pressure feels…",
          "options": _opts(("comfortable", "Comfortable"), ("manageable", "Manageable"), ("stressful", "Stressful"))},
         {"id": "bh_after_losses", "type": "single", "required": True,
          "prompt": "After several losing trades in a row, I usually…",
          "options": _opts(("pause_review", "Pause and review"), ("continue_plan", "Keep following my plan"),
                           ("trade_more", "Trade more to win it back"), ("stop_entirely", "Stop trading for a while"))},
         {"id": "bh_drawdown_reaction", "type": "single", "required": True,
          "prompt": "If my account dropped sharply but temporarily, I would…",
          "options": _opts(("hold_plan", "Stick to my plan"), ("reduce", "Reduce my exposure"),
                           ("exit_all", "Close everything"), ("add_more", "Add more to recover faster"))},
         {"id": "bh_size_after_loss", "type": "single", "required": True,
          "prompt": "After a loss, I'm tempted to increase my next position size.",
          "options": _opts(("never", "Rarely or never"), ("sometimes", "Sometimes"), ("often", "Often"))},
         {"id": "bh_exit_rule", "type": "single", "required": True,
          "prompt": "I decide my exit before I enter a trade.",
          "options": _opts(("always", "Almost always"), ("sometimes", "Sometimes"), ("rarely", "Rarely"))},
         {"id": "bh_strategy_switch", "type": "single", "required": True,
          "prompt": "After a few weeks of poor results, I change my strategy…",
          "options": _opts(("rarely", "Rarely"), ("sometimes", "Sometimes"), ("often", "Often"))},
     ]},

    # ------------------------------------------------------------------ 8-9. RISK CAPACITY / TOLERANCE
    {"id": "risk_intro", "kind": "interstitial", "group": "Risk", "illustration": "capacity_vs_tolerance",
     "title": "Two different questions about risk",
     "body": ["Risk capacity is how much loss your finances can absorb without harming your life.",
              "Risk tolerance is how much ups and downs you are comfortable living with.",
              "They are often different. CSS plans around the lower of the two."]},
    {"id": "risk_capacity", "kind": "question", "group": "Risk", "title": "Your risk capacity",
     "questions": [
         {"id": "rc_capital_band", "type": "single", "required": True,
          "prompt": "Roughly how much do you intend to trade with?",
          "options": _opts(("lt_1k", "Under $1,000"), ("1k_10k", "$1,000 – $10,000"), ("10k_50k", "$10,000 – $50,000"),
                           ("50k_250k", "$50,000 – $250,000"), ("gt_250k", "Over $250,000"),
                           ("prefer_not", "Prefer not to say"))},
         {"id": "rc_living_dependence", "type": "single", "required": True,
          "prompt": "Would losing this money affect your ability to pay living expenses?",
          "options": _opts(("no", "No"), ("somewhat", "Somewhat"), ("yes", "Yes"))},
         {"id": "rc_emergency_fund", "type": "single", "required": True,
          "prompt": "Do you have emergency savings separate from this money?",
          "options": _opts(("yes_6m", "Yes, six months or more of expenses"), ("yes_lt6m", "Yes, less than six months"),
                           ("no", "No"))},
         {"id": "rc_horizon", "type": "single", "required": True,
          "prompt": "How long could this money stay invested if markets went against you?",
          "options": _opts(("lt_1y", "Less than a year"), ("1_3y", "One to three years"), ("gt_3y", "More than three years"))},
         {"id": "rc_max_loss", "type": "single", "required": True,
          "prompt": "The largest fall in this money you could accept without changing your life plans:",
          "options": _opts(("lt_5", "Under 5%"), ("5_15", "5–15%"), ("15_30", "15–30%"), ("gt_30", "More than 30%"))},
     ]},
    {"id": "risk_tolerance", "kind": "question", "group": "Risk", "title": "Your comfort with risk",
     "questions": [
         {"id": "rt_volatility", "type": "single", "required": True, "prompt": "Large day-to-day swings in value…",
          "options": _opts(("uncomfortable", "Make me uncomfortable"), ("acceptable", "Are acceptable"),
                           ("comfortable", "Don't bother me"))},
         {"id": "rt_temporary_loss", "type": "single", "required": True,
          "prompt": "Seeing a position down 10% before it recovers…",
          "options": _opts(("uncomfortable", "Would worry me a lot"), ("acceptable", "Is part of trading"),
                           ("comfortable", "Doesn't bother me"))},
         {"id": "rt_consecutive_losses", "type": "single", "required": True,
          "prompt": "Five losing trades in a row would…",
          "options": _opts(("uncomfortable", "Make me want to stop"), ("acceptable", "Be hard but expected"),
                           ("comfortable", "Not change my approach"))},
         {"id": "rt_uncertainty", "type": "single", "required": True,
          "prompt": "Acting when the outcome is genuinely uncertain…",
          "options": _opts(("uncomfortable", "Is hard for me"), ("acceptable", "Is fine with a plan"),
                           ("comfortable", "Comes naturally"))},
         {"id": "rt_concentration", "type": "single", "required": True,
          "prompt": "Putting a large share of this money into one position…",
          "options": _opts(("uncomfortable", "I'd avoid it"), ("acceptable", "Occasionally, with care"),
                           ("comfortable", "I'm comfortable with it"))},
         {"id": "rt_leverage", "type": "single", "required": True, "prompt": "Using leverage (borrowed exposure)…",
          "options": _opts(("uncomfortable", "I'd rather not"), ("acceptable", "In small amounts"),
                           ("comfortable", "I'm comfortable with it"))},
     ]},

    # ------------------------------------------------------------------ 10. BARRIERS
    {"id": "barriers", "kind": "question", "group": "Your goals", "title": "What holds you back today?",
     "questions": [
         {"id": "barriers", "type": "multi", "required": True, "min_select": 1, "max_select": 9,
          "prompt": "Choose any that apply.",
          "options": _opts(("no_system", "No clear system"), ("time", "Not enough time"),
                           ("complicated", "Trading feels complicated"), ("experience", "Not enough experience"),
                           ("confidence", "Lack of confidence"), ("emotions", "Emotional decisions"),
                           ("interpreting", "Hard to read the markets"), ("discipline", "Staying disciplined"),
                           ("other", "Something else"))},
     ]},

    # ------------------------------------------------------------------ 11. MARKETS
    {"id": "markets", "kind": "question", "group": "Markets", "title": "Where would you like to trade?",
     "questions": [
         {"id": "preferred_markets", "type": "multi", "required": True, "min_select": 1, "max_select": 6,
          "prompt": "Markets you're interested in", "options": ASSET_CLASSES},
         {"id": "holding_periods", "type": "multi", "required": True, "min_select": 1, "max_select": 4,
          "prompt": "Typical holding periods",
          "options": _opts(("intraday", "Within a day"), ("days", "A few days"), ("weeks", "Weeks"),
                           ("months", "Months or longer"))},
     ]},

    {"id": "knowledge_leverage", "kind": "question", "group": "Markets", "title": "Leverage and margin",
     "show_if": {"any_of": [
         {"q": "experience_by_class", "row_in": {"rows": LEVERAGED_CLASSES,
                                                 "values": ["beginner", "intermediate", "experienced"]}},
         {"q": "objectives", "includes_any": ["active_trading", "new_markets"]},
         {"q": "preferred_markets", "includes_any": LEVERAGED_CLASSES},
     ]},
     "questions": [
         _quiz("kq_leverage", "leverage", "With 10:1 leverage, a 5% move against your position changes your margin by…",
               _opts(("a", "−5%"), ("b", "−50%"), ("c", "Nothing until you close")), "b",
               "Leverage multiplies the move: 10 × 5% = 50% of the margin you put up."),
         _quiz("kq_margin_call", "margin", "A margin call means…",
               _opts(("a", "Your broker is offering a bonus"),
                     ("b", "Your account equity fell below the required margin and you must add funds or reduce positions"),
                     ("c", "Your trade has hit its profit target")), "b",
               "If you don't act, the broker may close positions for you, often at a bad moment."),
         {"id": "uses_leverage", "type": "single", "required": True,
          "prompt": "Do you plan to use leverage or margin?",
          "options": _opts(("no", "No"), ("small", "In small amounts"), ("yes", "Yes, regularly"), ("unsure", "Not sure"))},
     ]},
    # ------------------------------------------------------------------ 12. ASSISTANCE MODE
    {"id": "assistance", "kind": "question", "group": "Working with CSS", "illustration": "modes",
     "title": "How much help do you want from CSS?",
     "questions": [
         {"id": "assistance_preference", "type": "single", "required": True, "prompt": "Choose the closest fit.",
          "options": [
              {"value": "discover", "label": "Discover",
               "detail": "CSS surfaces opportunities and analysis. You decide and act; you stay fully responsible."},
              {"value": "confirm", "label": "Confirm",
               "detail": "CSS proposes governed Trade Cards. Nothing is placed unless you confirm the actions allowed."},
              {"value": "auto_interest", "label": "Interested in Auto",
               "detail": "Governed automated execution, where legally, operationally and technically available. "
                         "Choosing this records interest only; it does not switch anything on."},
          ]},
     ]},
    {"id": "auto_check", "kind": "question", "group": "Working with CSS", "title": "What Auto does and doesn't change",
     "show_if": {"q": "assistance_preference", "in": ["auto_interest"]},
     "body": ["Auto would change who presses the button, not how markets behave."],
     "questions": [
         {"id": "auto_understanding", "type": "single", "required": True, "prompt": "With Auto, which is true?",
          "options": _opts(("mechanics_only", "Trades are placed for me under governed rules; losses are still possible"),
                           ("guaranteed", "Returns are more reliable because a system is trading"),
                           ("no_risk", "Risk controls mean I can't lose money")),
          "correct": "mechanics_only"},
     ]},

    # ------------------------------------------------------------------ 13-14. FEATURES / TIME
    {"id": "features", "kind": "question", "group": "Working with CSS", "title": "What would be most useful?",
     "questions": [
         {"id": "feature_preferences", "type": "multi", "required": True, "min_select": 1, "max_select": 10,
          "prompt": "Choose any.",
          "options": _opts(("trade_cards", "CSS Trade Cards"), ("discovery", "Opportunity discovery"),
                           ("explanations", "Plain-language market explanations"), ("alerts", "Alerts"),
                           ("simulator", "Simulator / paper trading"), ("analytics", "Performance analytics"),
                           ("journal", "Trade journal"), ("ai_assist", "AI assistance"), ("education", "Education"),
                           ("risk_monitoring", "Risk monitoring"))},
     ]},
    {"id": "time", "kind": "question", "group": "Working with CSS", "title": "Your time",
     "questions": [
         {"id": "engagement_cadence", "type": "single", "required": True, "prompt": "How often will you check in?",
          "options": _opts(("several_daily", "Several times a day"), ("daily", "Once a day"),
                           ("few_weekly", "A few times a week"), ("weekly", "Weekly or less"))},
         {"id": "monitoring_availability", "type": "single", "required": True,
          "prompt": "During market hours, I can usually respond…",
          "options": _opts(("within_minutes", "Within minutes"), ("within_hours", "Within a few hours"),
                           ("end_of_day", "By the end of the day"))},
         {"id": "notification_preference", "type": "single", "required": True, "prompt": "Notifications:",
          "options": _opts(("important_only", "Only important ones"), ("daily_digest", "A daily digest"),
                           ("all", "Everything relevant"), ("none", "None for now"))},
     ]},

    # ------------------------------------------------------------------ 15. EXPECTATIONS (mandatory)
    {"id": "expectations_intro", "kind": "interstitial", "group": "Expectations", "illustration": "range",
     "title": "What do you expect from CSS?",
     "body": ["Honest expectations make for better decisions. Some questions check common misunderstandings; "
              "if one shows up, CSS will explain rather than judge.",
              "CSS does not guarantee returns. Results vary, and losing trades are a normal part of trading."]},
    {"id": "expectations_role", "kind": "question", "group": "Expectations", "title": "CSS's role for you",
     "questions": [
         {"id": "ex_role", "type": "single", "required": True, "prompt": "I mainly expect CSS to…",
          "options": _opts(("educate", "Help me learn"), ("inform", "Inform my own decisions"),
                           ("propose", "Propose trades for me to approve"), ("manage", "Trade for me"))},
         {"id": "ex_trade_frequency", "type": "single", "required": True, "prompt": "Expected trades:",
          "options": _opts(("few_monthly", "A few a month"), ("weekly", "A few a week"), ("daily", "About one a day"),
                           ("many_daily", "Many a day"))},
         {"id": "ex_holding_period", "type": "single", "required": True, "prompt": "Expected holding period:",
          "options": _opts(("intraday", "Within a day"), ("days", "Days"), ("weeks", "Weeks"), ("months", "Months"))},
         {"id": "ex_automation", "type": "single", "required": True, "prompt": "Expected automation:",
          "options": _opts(("none", "None: I place everything"), ("suggestions", "Suggestions only"),
                           ("approve", "I approve each trade"), ("full", "Fully automated"))},
         {"id": "ex_communication", "type": "single", "required": True, "prompt": "Expected communication:",
          "options": _opts(("on_demand", "When I open the app"), ("summaries", "Regular summaries"),
                           ("realtime", "Real-time alerts"))},
     ]},
    {"id": "expectations_outcomes", "kind": "question", "group": "Expectations", "title": "Risk and results",
     "questions": [
         {"id": "ex_risk", "type": "single", "required": True, "prompt": "The level of risk I expect to take:",
          "options": _opts(("low", "Low"), ("moderate", "Moderate"), ("high", "High"))},
         {"id": "ex_drawdown", "type": "single", "required": True,
          "prompt": "A temporary fall I'd accept on the way to my goals:",
          "options": _opts(("none", "None at all"), ("lt_10", "Under 10%"), ("10_20", "10–20%"), ("gt_20", "More than 20%"))},
         {"id": "ex_return_range", "type": "single", "required": True,
          "prompt": "The yearly result I'm hoping for (an aspiration, not a promise):",
          "help": "CSS does not guarantee any return. Losses are possible in any year.",
          "options": _opts(("preserve", "Mostly preserve capital"), ("modest", "Modest growth"),
                           ("strong", "Strong growth"), ("double_plus", "Double my money or more"),
                           ("unsure", "I don't know"))},
         {"id": "ex_success", "type": "multi", "required": True, "min_select": 1, "max_select": 3,
          "prompt": "A successful CSS experience would mean…",
          "options": _opts(("better_decisions", "Better, more consistent decisions"), ("learning", "Learning a lot"),
                           ("discipline", "More discipline"), ("time_saved", "Saving time"),
                           ("returns", "Better results over time"), ("every_trade_wins", "Every trade making money"))},
     ]},
    {"id": "expectations_beliefs", "kind": "question", "group": "Expectations", "title": "True or false?",
     "questions": [
         {"id": "bl_every_trade_profitable", "type": "boolean", "required": True,
          "prompt": "Every trade CSS recommends will be profitable.", "realistic": False},
         {"id": "bl_losses_possible", "type": "boolean", "required": True,
          "prompt": "I could lose money, including on trades CSS recommends.", "realistic": True},
         {"id": "bl_auto_guarantees", "type": "boolean", "required": True,
          "prompt": "Auto mode guarantees returns.", "realistic": False},
         {"id": "bl_css_compensates", "type": "boolean", "required": True,
          "prompt": "CSS will pay me back for trading losses.", "realistic": False},
     ]},


    # ------------------------------------------------------------------ attribution explainer + acknowledgements
    {"id": "acknowledgements", "kind": "question", "group": "Before your Passport", "illustration": "two_ledgers",
     "title": "CSS trades and your own trades, kept apart",
     "body": ["Every trade is labelled by where it came from. CSS Recommended means it came from a CSS Trade Card "
              "you acted on through CSS. Your own trades are ones you chose without a CSS recommendation.",
              "If you change a recommendation's key details, it is labelled as modified. If the origin can't be "
              "proven, it is held for review rather than guessed. Your results always show both, separately.",
              "These confirmations are for onboarding only. They do not replace the CSS Terms or the Trading Risk "
              "Disclosure, which you accept separately."],
     "questions": [
         {"id": "ack_attribution", "type": "consent", "required": True, "must_be_true": True,
          "prompt": "I understand how CSS labels and separates its recommendations from my own trades."},
         {"id": "ack_no_guarantee", "type": "consent", "required": True, "must_be_true": True,
          "prompt": "I understand CSS does not guarantee profits and I may lose money."},
         {"id": "ack_recommendation_not_authority", "type": "consent", "required": True, "must_be_true": True,
          "prompt": "I understand a recommendation is not permission to trade. Execution follows CSS's governed "
                    "controls, and this questionnaire does not grant any execution authority."},
         {"id": "ack_responsibility", "type": "consent", "required": True, "must_be_true": True,
          "prompt": "I understand I remain responsible for my trading decisions and for checking that CSS suits me."},
     ]},

    # ------------------------------------------------------------------ result
    {"id": "passport", "kind": "result", "group": "Your Passport", "illustration": "passport",
     "title": "Your CSS Trader Passport"},
]

SENSITIVE_QUESTION_IDS = frozenset(q["id"] for s in STAGES for q in s.get("questions", []) if q.get("sensitive"))
QUESTION_INDEX = {q["id"]: (s["id"], q) for s in STAGES for q in s.get("questions", [])}


def public_schema() -> dict:
    """Schema as served to the UI. Quiz answer keys are withheld so the UI cannot reveal them."""
    import copy
    stages = copy.deepcopy(STAGES)
    for s in stages:
        for q in s.get("questions", []):
            q.pop("correct", None)
            q.pop("realistic", None)
            q.pop("explain", None)
    return {"id": QUESTIONNAIRE_ID, "version": QUESTIONNAIRE_VERSION, "stages": stages}
