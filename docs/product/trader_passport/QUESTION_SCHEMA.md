# CSS Trader Passport question schema (TP-Q-1.0.0)

Generated from `backend/app/onboarding/schema.py` by `build_schema_docs.py`. Do not edit by hand.

| # | Stage | Kind | Shown when | Questions |
|---|---|---|---|---|
| 1 | `welcome` — Welcome to your CSS Trader Passport | interstitial | always | `ack_risk_intro` (consent, required): I understand that trading involves risk and that CSS does not guarantee profit. |
| 2 | `identity` — About you | question | always | `display_name` (text, required): Preferred name<br>`full_name` (text, sensitive): Full legal name (optional)<br>`email` (email, required, sensitive): Email<br>`phone` (phone, sensitive): Mobile number (optional)<br>`country` (country, required): Country or region<br>`preferred_channel` (single, required): Preferred way to hear from CSS<br>`consent_service_notifications` (consent): Send me alerts and service notifications for features I turn on.<br>`consent_marketing` (consent): Send me occasional product news. (Optional, and separate from alerts.) |
| 3 | `objective` — Your goals and priorities | question | always | `objectives` (multi, required): Choose up to three.<br>`objective_ranking` (rank, required): Pick your top three, most important first. |
| 4 | `experience` — Your experience by market | question | always | `experience_by_class` (matrix, required): Pick the closest band for each. 'None' is a perfectly good answer. |
| 5 | `knowledge_intro` — A quick knowledge check, not a test | interstitial | always | — |
| 6 | `knowledge_core` — Orders and sizing | question | always | `kq_market_vs_limit` (quiz, required): What does a limit order do?<br>`kq_stop` (quiz, required): A stop-loss order is mainly used to…<br>`kq_position_size` (quiz, required): With a $10,000 account and a 1% risk rule, the most you plan to lose on one trade is…<br>`kq_risk_reward` (quiz, required): A trade risks $50 to make $150. Its reward-to-risk ratio is… |
| 7 | `knowledge_risk` — Volatility, drawdown and diversification | question | always | `kq_volatility` (quiz, required): Higher volatility usually means…<br>`kq_drawdown` (quiz, required): An account falls from $12,000 to $9,000 before recovering. The drawdown was…<br>`kq_diversification` (quiz, required): Diversification aims to…<br>`kq_exposure` (quiz, required): You hold three different tech stocks, each 20% of your account. Your exposure to the tech sector is… |
| 8 | `strengths` — Which of these sound like you? | question | always | `strengths` (multi, required): Choose up to four. |
| 9 | `behaviour` — How you make decisions | question | always | `bh_time_pressure` (single, required): Making decisions under time pressure feels…<br>`bh_after_losses` (single, required): After several losing trades in a row, I usually…<br>`bh_drawdown_reaction` (single, required): If my account dropped sharply but temporarily, I would…<br>`bh_size_after_loss` (single, required): After a loss, I'm tempted to increase my next position size.<br>`bh_exit_rule` (single, required): I decide my exit before I enter a trade.<br>`bh_strategy_switch` (single, required): After a few weeks of poor results, I change my strategy… |
| 10 | `risk_intro` — Two different questions about risk | interstitial | always | — |
| 11 | `risk_capacity` — Your risk capacity | question | always | `rc_capital_band` (single, required): Roughly how much do you intend to trade with?<br>`rc_living_dependence` (single, required): Would losing this money affect your ability to pay living expenses?<br>`rc_emergency_fund` (single, required): Do you have emergency savings separate from this money?<br>`rc_horizon` (single, required): How long could this money stay invested if markets went against you?<br>`rc_max_loss` (single, required): The largest fall in this money you could accept without changing your life plans: |
| 12 | `risk_tolerance` — Your comfort with risk | question | always | `rt_volatility` (single, required): Large day-to-day swings in value…<br>`rt_temporary_loss` (single, required): Seeing a position down 10% before it recovers…<br>`rt_consecutive_losses` (single, required): Five losing trades in a row would…<br>`rt_uncertainty` (single, required): Acting when the outcome is genuinely uncertain…<br>`rt_concentration` (single, required): Putting a large share of this money into one position…<br>`rt_leverage` (single, required): Using leverage (borrowed exposure)… |
| 13 | `barriers` — What holds you back today? | question | always | `barriers` (multi, required): Choose any that apply. |
| 14 | `markets` — Where would you like to trade? | question | always | `preferred_markets` (multi, required): Markets you're interested in<br>`holding_periods` (multi, required): Typical holding periods |
| 15 | `knowledge_leverage` — Leverage and margin | question | {"any_of": [{"q": "experience_by_class", "row_in": {"rows": ["fx", "crypto", "options", "futures"], "values": ["beginner", "intermediate", "experienced"]}}, {"q": "objectives", "includes_any": ["active_trading", "new_markets"]}, {"q": "preferred_markets", "includes_any": ["fx", "crypto", "options", "futures"]}]} | `kq_leverage` (quiz, required): With 10:1 leverage, a 5% move against your position changes your margin by…<br>`kq_margin_call` (quiz, required): A margin call means…<br>`uses_leverage` (single, required): Do you plan to use leverage or margin? |
| 16 | `assistance` — How much help do you want from CSS? | question | always | `assistance_preference` (single, required): Choose the closest fit. |
| 17 | `auto_check` — What Auto does and doesn't change | question | {"q": "assistance_preference", "in": ["auto_interest"]} | `auto_understanding` (single, required): With Auto, which is true? |
| 18 | `features` — What would be most useful? | question | always | `feature_preferences` (multi, required): Choose any. |
| 19 | `time` — Your time | question | always | `engagement_cadence` (single, required): How often will you check in?<br>`monitoring_availability` (single, required): During market hours, I can usually respond…<br>`notification_preference` (single, required): Notifications: |
| 20 | `expectations_intro` — What do you expect from CSS? | interstitial | always | — |
| 21 | `expectations_role` — CSS's role for you | question | always | `ex_role` (single, required): I mainly expect CSS to…<br>`ex_trade_frequency` (single, required): Expected trades:<br>`ex_holding_period` (single, required): Expected holding period:<br>`ex_automation` (single, required): Expected automation:<br>`ex_communication` (single, required): Expected communication: |
| 22 | `expectations_outcomes` — Risk and results | question | always | `ex_risk` (single, required): The level of risk I expect to take:<br>`ex_drawdown` (single, required): A temporary fall I'd accept on the way to my goals:<br>`ex_return_range` (single, required): The yearly result I'm hoping for (an aspiration, not a promise):<br>`ex_success` (multi, required): A successful CSS experience would mean… |
| 23 | `expectations_beliefs` — True or false? | question | always | `bl_every_trade_profitable` (boolean, required): Every trade CSS recommends will be profitable.<br>`bl_losses_possible` (boolean, required): I could lose money, including on trades CSS recommends.<br>`bl_auto_guarantees` (boolean, required): Auto mode guarantees returns.<br>`bl_css_compensates` (boolean, required): CSS will pay me back for trading losses. |
| 24 | `acknowledgements` — CSS trades and your own trades, kept apart | question | always | `ack_attribution` (consent, required): I understand how CSS labels and separates its recommendations from my own trades.<br>`ack_no_guarantee` (consent, required): I understand CSS does not guarantee profits and I may lose money.<br>`ack_recommendation_not_authority` (consent, required): I understand a recommendation is not permission to trade. Execution follows CSS's governed controls, and this questionnaire does not grant any execution authority.<br>`ack_responsibility` (consent, required): I understand I remain responsible for my trading decisions and for checking that CSS suits me. |
| 25 | `passport` — Your CSS Trader Passport | result | always | — |

## Options

- `preferred_channel`: `in_app` In the app; `email` Email; `push` Push notifications; `sms` Text message
- `objectives`: `learn` Learn to trade; `improve_process` Improve my existing process; `supplement_investing` Add to my wider investing; `active_trading` Trade actively; `diversify` Diversify my portfolio; `systematic_support` Systematic decision support; `discipline` Become more disciplined; `new_markets` Explore new markets
- `objective_ranking`: `preservation` Protect what I have; `steady_growth` Steady growth; `learning` Learning; `supplement` Supplement other investments; `aggressive_growth` Aggressive growth; `diversification` Diversification
- `experience_by_class`: `none` None; `beginner` Beginner; `intermediate` Intermediate; `experienced` Experienced
  - rows: Stocks (equities), ETFs, Currencies (FX), Crypto, Options, Futures
- `kq_market_vs_limit`: `a` Fills immediately at whatever the market price is; `b` Fills only at your chosen price or better; `c` Closes a trade automatically after a loss; `not_sure` I'm not sure yet — correct: `b`
- `kq_stop`: `a` Guarantee the exit price; `b` Limit a loss by exiting once a price is reached; `c` Increase position size when price falls; `not_sure` I'm not sure yet — correct: `b`
- `kq_position_size`: `a` $10; `b` $100; `c` $1,000; `not_sure` I'm not sure yet — correct: `b`
- `kq_risk_reward`: `a` 1 : 3; `b` 3 : 1; `c` It depends on the win rate only; `not_sure` I'm not sure yet — correct: `b`
- `kq_volatility`: `a` Larger and faster price swings, up and down; `b` Prices only go up; `c` Less risk; `not_sure` I'm not sure yet — correct: `a`
- `kq_drawdown`: `a` $9,000; `b` 25%; `c` 75%; `not_sure` I'm not sure yet — correct: `b`
- `kq_diversification`: `a` Remove all risk; `b` Reduce the impact of any single position going wrong; `c` Guarantee higher returns; `not_sure` I'm not sure yet — correct: `b`
- `kq_exposure`: `a` About 20%; `b` About 60%; `c` Unknown without prices; `not_sure` I'm not sure yet — correct: `b`
- `strengths`: `detail` Detail-oriented; `quantitative` Quantitative; `pattern` Pattern-focused; `disciplined` Disciplined / process-driven; `patient` Patient; `big_picture` Fundamental / big-picture; `research` Research-oriented; `decisive` Decisive; `risk_aware` Risk-aware
- `bh_time_pressure`: `comfortable` Comfortable; `manageable` Manageable; `stressful` Stressful
- `bh_after_losses`: `pause_review` Pause and review; `continue_plan` Keep following my plan; `trade_more` Trade more to win it back; `stop_entirely` Stop trading for a while
- `bh_drawdown_reaction`: `hold_plan` Stick to my plan; `reduce` Reduce my exposure; `exit_all` Close everything; `add_more` Add more to recover faster
- `bh_size_after_loss`: `never` Rarely or never; `sometimes` Sometimes; `often` Often
- `bh_exit_rule`: `always` Almost always; `sometimes` Sometimes; `rarely` Rarely
- `bh_strategy_switch`: `rarely` Rarely; `sometimes` Sometimes; `often` Often
- `rc_capital_band`: `lt_1k` Under $1,000; `1k_10k` $1,000 – $10,000; `10k_50k` $10,000 – $50,000; `50k_250k` $50,000 – $250,000; `gt_250k` Over $250,000; `prefer_not` Prefer not to say
- `rc_living_dependence`: `no` No; `somewhat` Somewhat; `yes` Yes
- `rc_emergency_fund`: `yes_6m` Yes, six months or more of expenses; `yes_lt6m` Yes, less than six months; `no` No
- `rc_horizon`: `lt_1y` Less than a year; `1_3y` One to three years; `gt_3y` More than three years
- `rc_max_loss`: `lt_5` Under 5%; `5_15` 5–15%; `15_30` 15–30%; `gt_30` More than 30%
- `rt_volatility`: `uncomfortable` Make me uncomfortable; `acceptable` Are acceptable; `comfortable` Don't bother me
- `rt_temporary_loss`: `uncomfortable` Would worry me a lot; `acceptable` Is part of trading; `comfortable` Doesn't bother me
- `rt_consecutive_losses`: `uncomfortable` Make me want to stop; `acceptable` Be hard but expected; `comfortable` Not change my approach
- `rt_uncertainty`: `uncomfortable` Is hard for me; `acceptable` Is fine with a plan; `comfortable` Comes naturally
- `rt_concentration`: `uncomfortable` I'd avoid it; `acceptable` Occasionally, with care; `comfortable` I'm comfortable with it
- `rt_leverage`: `uncomfortable` I'd rather not; `acceptable` In small amounts; `comfortable` I'm comfortable with it
- `barriers`: `no_system` No clear system; `time` Not enough time; `complicated` Trading feels complicated; `experience` Not enough experience; `confidence` Lack of confidence; `emotions` Emotional decisions; `interpreting` Hard to read the markets; `discipline` Staying disciplined; `other` Something else
- `preferred_markets`: `equities` Stocks (equities); `etfs` ETFs; `fx` Currencies (FX); `crypto` Crypto; `options` Options; `futures` Futures
- `holding_periods`: `intraday` Within a day; `days` A few days; `weeks` Weeks; `months` Months or longer
- `kq_leverage`: `a` −5%; `b` −50%; `c` Nothing until you close; `not_sure` I'm not sure yet — correct: `b`
- `kq_margin_call`: `a` Your broker is offering a bonus; `b` Your account equity fell below the required margin and you must add funds or reduce positions; `c` Your trade has hit its profit target; `not_sure` I'm not sure yet — correct: `b`
- `uses_leverage`: `no` No; `small` In small amounts; `yes` Yes, regularly; `unsure` Not sure
- `assistance_preference`: `discover` Discover; `confirm` Confirm; `auto_interest` Interested in Auto
- `auto_understanding`: `mechanics_only` Trades are placed for me under governed rules; losses are still possible; `guaranteed` Returns are more reliable because a system is trading; `no_risk` Risk controls mean I can't lose money — correct: `mechanics_only`
- `feature_preferences`: `trade_cards` CSS Trade Cards; `discovery` Opportunity discovery; `explanations` Plain-language market explanations; `alerts` Alerts; `simulator` Simulator / paper trading; `analytics` Performance analytics; `journal` Trade journal; `ai_assist` AI assistance; `education` Education; `risk_monitoring` Risk monitoring
- `engagement_cadence`: `several_daily` Several times a day; `daily` Once a day; `few_weekly` A few times a week; `weekly` Weekly or less
- `monitoring_availability`: `within_minutes` Within minutes; `within_hours` Within a few hours; `end_of_day` By the end of the day
- `notification_preference`: `important_only` Only important ones; `daily_digest` A daily digest; `all` Everything relevant; `none` None for now
- `ex_role`: `educate` Help me learn; `inform` Inform my own decisions; `propose` Propose trades for me to approve; `manage` Trade for me
- `ex_trade_frequency`: `few_monthly` A few a month; `weekly` A few a week; `daily` About one a day; `many_daily` Many a day
- `ex_holding_period`: `intraday` Within a day; `days` Days; `weeks` Weeks; `months` Months
- `ex_automation`: `none` None: I place everything; `suggestions` Suggestions only; `approve` I approve each trade; `full` Fully automated
- `ex_communication`: `on_demand` When I open the app; `summaries` Regular summaries; `realtime` Real-time alerts
- `ex_risk`: `low` Low; `moderate` Moderate; `high` High
- `ex_drawdown`: `none` None at all; `lt_10` Under 10%; `10_20` 10–20%; `gt_20` More than 20%
- `ex_return_range`: `preserve` Mostly preserve capital; `modest` Modest growth; `strong` Strong growth; `double_plus` Double my money or more; `unsure` I don't know
- `ex_success`: `better_decisions` Better, more consistent decisions; `learning` Learning a lot; `discipline` More discipline; `time_saved` Saving time; `returns` Better results over time; `every_trade_wins` Every trade making money
