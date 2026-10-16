<!-- css-manual-page: about | 1. About this agreement and who it is for -->
# CSS User Operating Manual, Trading Assumptions and Risk Disclosure Agreement

**Document:** CSS-UOM — CSS User Operating Manual, Trading Assumptions and Risk Disclosure Agreement
**Version:** see the document manifest shown with this agreement (the version, effective date and SHA-256 fingerprint are displayed before you accept and on your receipt).

## 1.1 What this document is

This document explains how Capital Strata Systems ("CSS") trading features work, what CSS assumes when it makes or proposes trading decisions, what those assumptions mean for you, and the risks you take when you use any CSS trading mode. It is both an operating manual and the agreement you must accept before any trading mode, risk personality, copy-trading mandate or risk limit takes effect for your account.

You must review every page. Reaching the end of each page is required before you can acknowledge the risks. Reaching the end of a page is **not** proof that you understood it: please read carefully, and contact support (page 12) before accepting if anything is unclear.

## 1.2 Who CSS trading is intended for

CSS trading features are intended for adults who:

- understand that trading can lose money, including all of the money allocated to it;
- can afford to lose the capital they allocate, without affecting essential living costs or obligations;
- are permitted under the laws of their place of residence to use the instruments involved;
- will monitor their account and respond to alerts.

CSS trading is **not** suitable as a savings product, for money you need in the short term, or for anyone who cannot tolerate losses.

## 1.3 Current release status: simulation and paper only

In the current release **no CSS mode sends orders to a broker and no real capital is exposed by CSS**:

- every mode either simulates trades or evaluates them through a paper (validation-only) pipeline;
- selecting a mode, a personality, a trader or a limit never enables live trading;
- live trading requires separate release approvals that are not part of this agreement and are not currently granted.

Simulated and paper results are **not** indicative of live results. Real markets add partial fills, rejections, latency, gaps and costs that simulation can only approximate.

## 1.4 What you are agreeing to

By accepting you confirm that you have reviewed this document, that you understand the trading assumptions and risks described, and that you bear the investment risks of your trading decisions and of the CSS trading activities you authorize. This agreement does **not** waive any duty, liability or protection that cannot legally be waived, including liability for fraud, negligence or statutory consumer and investor protections. Jurisdiction-specific legal and compliance review of this text is required before any public or live-money use.

<!-- end-of-page -->

<!-- css-manual-page: modes | 2. The four trading modes and who decides -->
# 2. The four trading modes and who makes each decision

You choose exactly one startup mode. CSS remembers your choice, so you are not asked to choose a strategy every time you start. Any change of mode only takes effect after you review this agreement and accept the exact new settings.

| Mode | Who proposes trades | Who decides each trade | Orders |
|---|---|---|---|
| **Simulated Trading** | CSS or you | you (practice) | simulated only; no broker path of any kind |
| **CSS-Assisted Trading** | CSS proposes; you may also enter manual orders | **you approve or reject every single order** | paper evaluation through all CSS safety gates |
| **Copy a CSS Trader** | a CSS trader you choose | CSS applies your risk personality and limits to each of that trader's signals, within your signed mandate | paper evaluation through all CSS safety gates |
| **CSS Autonomous Trading** | the CSS engine | CSS decides, only within the settings and limits you accepted | paper evaluation through all CSS safety gates |

## 2.1 Simulated Trading

Practice with hypothetical capital. No order reaches any broker, paper or live. Results are hypothetical and can be very different from real trading. Simulated mode still applies the CSS safety gates so that the practice is realistic.

## 2.2 CSS-Assisted Trading

CSS proposes trades. Nothing happens until **you** approve the specific order. A proposal expires if you do not act on it, and CSS re-checks every safety gate at the moment you approve, so an approved proposal can still be rejected if conditions changed. Manual orders you enter yourself go through exactly the same gates; manual entry never means unrestricted execution. You are responsible for each approval you give.

## 2.3 Copy a CSS Trader

You choose a CSS trader and authorize a **mandate**: the trader, your risk personality, the asset classes, an allocation ceiling, a currency and an expiry. CSS does **not** copy the trader's orders one-for-one: your personality and your limits decide which signals you take, how large your positions are, and when they exit. Your fills, positions and profit or loss will differ from the trader's.

Only traders approved by two different CSS administrators can be copied, and only for the asset classes they were approved for. CSS accepts a trader's signal only if it is signed with that trader's registered key, is recent and has not been used before. Approval is not an endorsement or a guarantee of the trader's results. If CSS suspends or revokes a trader, no new trades are copied from that moment; your open positions keep their protective exits.

## 2.4 CSS Autonomous Trading

CSS decides without asking you about each trade, but only inside the settings you accepted: your mode, personality, limits and the platform's hard safety limits. Autonomous decisions are made by software that can be wrong. Autonomous mode does not mean unlimited risk, and it is never live trading authorization.

## 2.5 What no mode can do

No mode, personality or user setting can switch off or loosen the CSS safety gates described on page 4, can enable live trading, or can override the kill switch.

<!-- end-of-page -->

<!-- css-manual-page: personalities | 3. Risk personalities and your own limits -->
# 3. Risk personalities and configurable limits

## 3.1 The five risk personalities

Your risk personality governs which trades you take and how much risk each one carries. The values below are **proposed defaults pending owner review**; the exact values that apply to you are shown on the summary screen before you accept and are recorded on your receipt.

| | Safe | Conservative | Balanced | Aggressive | Ultra Aggressive |
|---|---|---|---|---|---|
| Asset classes | FX | FX, crypto | FX, crypto, futures | all | all |
| Minimum trade quality | 80 (EXECUTE only) | 72 | 65 | 58 | 50 (WATCH allowed) |
| Minimum probability | 0.66 | 0.62 | 0.58 | 0.55 | 0.53 |
| Max position (% of equity) | 2 | 4 | 6 | 8 | 10 |
| Max total exposure (% of equity) | 5 | 10 | 20 | 30 | 40 |
| Max open positions | 2 | 3 | 5 | 7 | 8 |
| Max stop distance (%) | 1.0 | 1.5 | 2.0 | 2.5 | 3.0 |
| Daily-loss pause (%) | 1 | 2 | 3 | 4 | 5 |
| Drawdown pause (%) | 3 | 5 | 8 | 12 | 15 |
| Take profit (multiple of the stop) | 1.5 | 1.75 | 2.0 | 2.5 | 3.0 |
| Time exit (hours) | 24 | 48 | 72 | 120 | 168 |

**Platform capital limits also apply.** CSS's capital and portfolio governors cap any single new position at 5% of your available capital (2% for futures and options) and your total exposure at 25% of your equity. Where a personality value above is higher, the lower platform limit applies. Today this means Balanced, Aggressive and Ultra Aggressive positions reach the same maximum size; they still differ in which trades they take, their stops, exits and pauses.

**Implications.** A more aggressive personality takes more trades, larger positions and wider stops, so it can lose more, faster. "Aggressive" and "Ultra Aggressive" do **not** remove any safety gate and do not allow live trading. A safer personality will skip many signals, and a small account may be unable to trade at all because orders below the platform minimum are rejected rather than enlarged.

## 3.2 Your own limits (they can only tighten)

You may set your own, stricter limits: risk per trade, maximum position size, total exposure, open positions, daily-loss and drawdown pauses, stop distance, and eligible asset classes. CSS applies the **most restrictive** of:

1. legal, broker and account eligibility and the platform's hard safety limits;
2. the CSS safety gates (page 4), kill switch, margin and approved pilot caps;
3. your risk personality and, in copy mode, your mandate;
4. your own limits;
5. in CSS-Assisted mode, your approval of each order.

In an approved CAD pilot account, each position, including its estimated fees, is limited to CAD 20, at most two positions may be open at once, and their total is limited to CAD 40. These pilot limits are fixed ceilings: they can be lowered but never raised by configuration. Positions this small are currently below the platform's minimum trade size, so they are rejected rather than enlarged.

A limit you enter that is looser than your personality is rejected. Changing limits takes effect only after you accept the new settings, applies to **new** trades, and never silently changes the protection of positions that are already open.

## 3.3 What is fixed and what you choose

- **Fixed (immutable safety limits):** the safety gates, the platform position caps (10 open positions; at most 3 crypto, 3 FX, 2 futures, 2 options), minimum order size and cost rules, kill switches.
- **You choose:** mode, personality, trader and mandate terms, and any tighter personal limits.
- **Defaults:** the personality values above apply wherever you have not set a tighter limit.

<!-- end-of-page -->

<!-- css-manual-page: gates | 4. Safety gates and trading assumptions -->
# 4. Safety gates, guarantees and trading assumptions

## 4.1 Safety gates every order must pass

Every CSS order — simulated, assisted, manual, copied or autonomous — must pass all of these, in this order:

1. observed platform safety state and kill switches;
2. your accepted settings and a valid, current acceptance of this agreement;
3. your mandate (copy mode) or source restrictions (autonomous mode);
4. your personality and personal limits, including loss and drawdown pauses;
5. trade-quality and capital-allocation scoring floors;
6. the R14F profitability threshold;
7. the R7 unified trade gate (probability, cost versus expected value, position caps);
8. AntiBleedGuard: expected move must exceed fees, spread and slippage by at least 25 basis points; orders below the minimum size are rejected; a cooldown applies per symbol;
9. margin and risk-governor checks;
10. a validation-only execution pipeline that rejects live orders.

## 4.2 What CSS guarantees in this release

- No order is sent to a broker by any CSS mode.
- A missing, stale or mismatched acceptance blocks new trades.
- Orders are never enlarged to pass a minimum.
- Risk-reducing actions (pause, kill switch, protective exits, revoking a mandate) are never blocked by missing acceptance.

## 4.3 What CSS does NOT guarantee

CSS does **not** guarantee profits, loss avoidance, any fill, any fill price, any exit price, that a stop will execute at its level, that a signal is correct, that a copied trader will perform as before, or that the platform will be available at all times.

## 4.4 Trading assumptions and what they mean for you

| Assumption | Implication if it is wrong |
|---|---|
| Market prices and data feeds are accurate and timely | trades may be taken or skipped wrongly; stops may trigger late |
| Estimated fees, spreads and slippage are close to reality | real costs can exceed the edge the trade was approved on |
| Probability and quality scores reflect current conditions | models trained on the past can fail when market regimes change |
| Liquidity is sufficient to enter and exit at modelled sizes | larger losses, partial exits or no exit at the intended price |
| Stops and exits execute close to their levels | gaps and fast markets can cause losses larger than the stop implies |
| Your equity and positions are reported correctly | sizing and loss pauses act on wrong numbers |
| The platform and your connection stay available | you may be unable to act; protective logic may be delayed |

<!-- end-of-page -->

<!-- css-manual-page: instruments | 5. Instrument, cost, margin and exit risks -->
# 5. Instrument, cost, margin and exit risks

## 5.1 Instrument-specific risks

- **Foreign exchange (FX):** prices move with interest rates, central-bank decisions and political events, often outside your trading hours; weekend gaps are common.
- **Crypto-assets:** very high volatility, 24/7 trading, exchange and custody failures, sudden liquidity loss, regulatory change and the possibility of a total loss of value.
- **Futures:** leveraged contracts; small price moves create large gains or losses; margin calls; contract expiry and roll costs; daily limit moves can prevent exits.
- **Options:** can expire worthless; prices depend on volatility and time decay ("Greeks"); sold options can create losses larger than the premium; exercise and assignment risk.

## 5.2 Costs

Fees, commissions, spreads, slippage and, for leveraged or overnight positions, financing costs reduce or reverse returns. CSS estimates these before a trade; actual costs can be higher, especially in fast or thin markets.

## 5.3 Capital allocation and position limits

Personality and personal limits cap the size of each position and of your total exposure. Caps limit, but do not eliminate, losses; several positions can lose at the same time when markets move together.

## 5.4 Margin and leverage

Leverage magnifies losses as well as gains. If margin becomes insufficient, positions may be reduced or closed at unfavourable prices, and losses can exceed the margin you posted. CSS blocks new risk when the margin state is restricted.

## 5.5 Stops, exits and gap risk

Stops, take-profits, trailing stops and time exits are instructions, not guarantees. Prices can jump past a stop ("gap"), so the realized loss can be larger than planned. Exits depend on market liquidity and platform availability.

<!-- end-of-page -->

<!-- css-manual-page: signals | 6. Signals, models, copy-trading and autonomy -->
# 6. Signals, models, copy-trading and autonomous decisions

## 6.1 Signal quality and model uncertainty

CSS signals and scores come from statistical models and rules based on historical data. They can be wrong, become outdated when market regimes change, or perform differently out of sample. A high score is not a promise. Past or simulated performance does not predict future results.

## 6.2 Copied trader versus your results

Your results will differ from the trader you copy because:

- your personality and limits skip some of the trader's signals;
- your position sizes, stops and exits are your own;
- your fills happen at different times and prices, with your own costs;
- your mandate may expire or be revoked while the trader keeps trading.

CSS shows the trader's signal next to your own fill and profit or loss so that the difference is visible. A trader's past results are not a guarantee, and CSS does **not** reimburse ordinary trading losses.

## 6.3 Mandates and reauthorization

A mandate authorizes copying one trader, with one personality, within a scope, an allocation ceiling and an expiry (at most 90 days). It must be renewed at each sign-on or at the interval you agreed. When a mandate expires, is revoked or no longer matches your settings, **no new trades are copied**; existing positions keep their protective exits until they close.

## 6.4 Autonomous decisions

In CSS Autonomous Trading, software decides without asking you. Software can malfunction, act on bad data, or behave unexpectedly in unusual markets. Your accepted limits and the platform's safety gates bound what it can do, but losses within those bounds are possible.

## 6.5 Assisted and manual decisions

In CSS-Assisted Trading each approval is your decision. Approving quickly, or approving proposals you have not reviewed, is your responsibility. Manual orders follow the same gates and limits.

<!-- end-of-page -->

<!-- css-manual-page: operations | 7. Operating procedures, outages and security -->
# 7. Operating procedures, outages, data quality and security

## 7.1 Operating procedures

1. Sign in with your own account; never share credentials. If you have not accepted the current version of this agreement, or your trading is paused, sign-in takes you to the review first, and every new trading action is refused until you accept. Reducing risk (pausing, the kill switch, disarming, revoking a mandate, protective exits) is never blocked.
2. Choose or confirm your mode, personality, limits and (in copy mode) mandate.
3. Review the summary of the exact settings and their implications.
4. Review every page of this agreement and accept the acknowledgement.
5. Keep your receipt; you can view your acceptance history and download this document at any time.
6. Monitor positions, alerts and your statement; pause trading if anything looks wrong.
7. Renew mandates when asked; review the agreement again when a new version is issued.

## 7.2 Platform outages

The platform, data feeds, brokers or your connection can fail. During an outage CSS may be unable to open, manage or close positions, or may act on delayed information. Protective logic resumes when service resumes; prices may have moved substantially in the meantime.

## 7.3 Broker and data quality

Prices, balances and positions come from external providers and can be delayed, wrong or missing. CSS fails closed when required data is unavailable, which can mean missed trades or delayed protective actions.

## 7.4 Security

Protect your device and credentials and use your own session. CSS binds approvals, mandates and acceptances to your authenticated session and records them in tamper-evident logs. Report suspected unauthorized access immediately; you can pause trading and revoke mandates at any time.

<!-- end-of-page -->

<!-- css-manual-page: emergency | 8. Pausing, kill switch and incidents -->
# 8. Pausing, kill switch, errors and incidents

## 8.1 How to reduce risk immediately

You can always, without any further acceptance:

- **pause new trading** for your account;
- **revoke a copy mandate**;
- rely on protective exits (stop-loss, take-profit, trailing and time exits) for open positions.

The platform kill switch blocks all new CSS orders when engaged. Missing or outdated acceptance of this agreement **never** blocks these risk-reducing actions.

## 8.2 Resuming

Resuming new trading re-enables risk-taking and therefore requires your current, valid acceptance of the active settings. If the agreement has changed materially since you accepted, you must review and accept the new version first.

## 8.3 Errors and incidents

If you see an unexpected trade, missing position, wrong balance or system error: pause trading, record what you saw (time, symbol, screen), and contact support (page 12). CSS investigates incidents using its audit records. Corrections follow the CSS incident process; they are not a guarantee of reimbursement.

<!-- end-of-page -->

<!-- css-manual-page: legal | 9. Tax, regulatory and jurisdictional matters -->
# 9. Tax, regulatory and jurisdictional matters

- **Tax:** trading can create taxable gains, losses and reporting duties. CSS does not provide tax advice; consult a qualified tax adviser.
- **Regulation and eligibility:** some instruments, leverage levels or copy-trading features may be restricted or prohibited where you live. You are responsible for using CSS only where permitted.
- **No investment advice:** CSS signals, scores, personalities and summaries are tools, not personalised investment advice, unless separately agreed in writing.
- **Jurisdiction:** the governing law and dispute terms will be set out after jurisdiction-specific legal review. Until then this agreement is used for simulation and paper evaluation only.
- **Non-waivable rights:** nothing in this agreement limits liability that cannot legally be limited, including for fraud, negligence or statutory consumer and investor protections.

<!-- end-of-page -->

<!-- css-manual-page: scenarios | 10. Example scenarios -->
# 10. Example scenarios

**A. Same signal, different personalities.** A CSS trader issues one FX signal. With a 10,000 account, a Safe follower may skip it (quality too low for Safe), a Conservative follower may take a 400 position with a 1.5% stop, and an Ultra Aggressive follower a 500 position (its 10% personality cap reduced to the platform's 5% single-position cap) with a 2.5% stop. Each gets a different fill, exit and result.

**B. Small account.** A Conservative follower with a 1,000 account is sized at 40. The platform minimum is 50, so the order is rejected rather than enlarged. The follower sees "trade size too small".

**C. Gap through a stop.** A position with a 1.5% stop opens after a weekend 4% lower. The exit happens near the new price, so the loss is about 4%, not 1.5%.

**D. Mandate expiry.** A mandate expires on Friday. On Monday the trader issues new signals; none are copied. An open position from last week still exits at its stop or target.

**E. Assisted proposal.** CSS proposes a trade at 10:00. You approve at 10:20; CSS re-checks the gates, finds the cooldown or costs no longer acceptable, and rejects it. Nothing is ordered.

**F. Agreement update.** CSS publishes a materially changed version of this agreement. New trades are blocked until you review and accept it; pausing and protective exits still work.

<!-- end-of-page -->

<!-- css-manual-page: glossary | 11. Glossary -->
# 11. Glossary

- **AntiBleedGuard:** the CSS gate that rejects trades whose expected move does not cover costs plus a 25 basis-point margin, orders below the minimum size, and repeated trades in a symbol during a cooldown.
- **Basis point (bps):** one hundredth of a percent (0.01%).
- **Drawdown:** the fall in equity from its highest point.
- **Gap:** a jump in price with no trading in between, often after a market closes.
- **Kill switch:** a control that blocks all new CSS orders immediately.
- **Leverage / margin:** borrowing to hold a position larger than your capital; margin is the collateral required.
- **Mandate:** your signed authorization to copy one trader, with a personality, scope, allocation and expiry.
- **Paper / simulated trading:** evaluation or practice without real orders or real capital.
- **Personality:** one of Safe, Conservative, Balanced, Aggressive, Ultra Aggressive.
- **R7 / R14F:** CSS gates for probability, cost versus expected value, position caps, and minimum profitability.
- **Slippage:** the difference between the expected and the actual fill price.
- **Spread:** the difference between buying and selling prices.
- **Stop-loss / take-profit / trailing stop / time exit:** automatic exit instructions at a loss limit, a profit target, a retreat from the best price, or after a maximum holding time.

<!-- end-of-page -->

<!-- css-manual-page: support | 12. Support, escalation and acknowledgement -->
# 12. Support, escalation, document control and acknowledgement

## 12.1 Support and escalation

- **Support contact:** [SUPPORT CONTACT — TO BE PROVIDED BY THE OWNER BEFORE RELEASE]
- **Urgent issues:** pause trading first, then contact support.
- **Escalation:** if an issue is not resolved, ask for escalation to the CSS operations lead; incidents are reviewed using the audit records.

## 12.2 Document control

This document is version-controlled. Each version has a version number, an effective date, a SHA-256 fingerprint and a change history, all shown before you accept and on your receipt. You can view your acceptance history and download the current or accepted version at any time. When a version contains a **material change**, you must review and accept it again before new risk-taking resumes.

## 12.3 Acknowledgement

To accept, you will be asked to check the following statement. It is never pre-checked:

> I understand that trading involves substantial risk, including the possible loss of my invested capital. I accept responsibility for the trading decisions and authorizations I make, subject to applicable law.

Your acceptance is recorded with your account, session, this document's version and fingerprint, and the exact settings you are activating.

<!-- end-of-page -->
