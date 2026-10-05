# CSS Trader Passport question schema (TP-Q-2.0.0)

Generated from `backend/app/onboarding/schema.py` by `build_schema_docs.py`. Do not edit by hand.

| # | Stage | Kind | Shown when | Questions |
|---|---|---|---|---|
| 1 | `welcome` — Welcome to your CSS Trader Passport | interstitial | always | `ack_risk_intro` (consent, required): I understand that trading involves risk and that CSS does not guarantee profit. |
| 2 | `identity` — About you | question | always | `display_name` (text, required): Preferred name<br>`full_name` (text, sensitive): Full legal name (optional)<br>`email` (email, required, sensitive): Email<br>`phone` (phone, sensitive): Mobile number (optional)<br>`country` (country, required): Country or region<br>`preferred_channel` (single, required): Preferred way to hear from CSS<br>`consent_service_notifications` (consent): Send me alerts and service notifications for features I turn on.<br>`consent_marketing` (consent): Send me occasional product news. (Optional, and separate from alerts.) |
| 3 | `objective` — Your goals and priorities | question | always | `objectives` (multi, required): What do you want from trading and CSS? Choose up to three.<br>`objective_ranking` (rank, required): Rank your top three financial priorities, most important first. |
| 4 | `experience` — Your experience | question | always | `experience_by_class` (matrix, required): Pick the closest band for each market. 'None' is a perfectly good answer.<br>`css_familiarity` (single, required): Have you used CSS or similar decision-support tools before? |
| 5 | `knowledge_intro` — A quick knowledge check, not a test | interstitial | always | — |
| 6 | `knowledge_core` — Orders and sizing | question | always | `kq_market_vs_limit` (quiz, required): What does a limit order do?<br>`kq_stop` (quiz, required): A stop-loss order is mainly used to…<br>`kq_position_size` (quiz, required): With a $10,000 account and a 1% risk rule, the most you plan to lose on one trade is…<br>`kq_risk_reward` (quiz, required): A trade risks $50 to make $150. Its reward-to-risk ratio is… |
| 7 | `knowledge_risk` — Volatility, drawdown and diversification | question | always | `kq_volatility` (quiz, required): Higher volatility usually means…<br>`kq_drawdown` (quiz, required): An account falls from $12,000 to $9,000 before recovering. The drawdown was…<br>`kq_diversification` (quiz, required): Diversification aims to…<br>`kq_exposure` (quiz, required): You hold three different tech stocks, each 20% of your account. Your exposure to the tech sector is… |
| 8 | `thinking` — How you think about markets | question | always | `thinking_style` (single, required): When you look at a market, what do you notice first?<br>`strengths` (multi, required): Which of these sound like you? Choose up to three. |
| 9 | `behaviour` — How you make decisions | question | always | `bh_decision_speed` (single, required): When a decision needs making quickly, I usually…<br>`bh_after_losses` (single, required): After several losing trades in a row, I usually…<br>`bh_drawdown_reaction` (single, required): If my account dropped sharply but temporarily, I would…<br>`bh_size_after_loss` (single, required): After a loss, I'm tempted to increase my next position size.<br>`bh_exit_rule` (single, required): I decide my exit before I enter a trade.<br>`bh_strategy_switch` (single, required): After a few weeks of poor results, I change my strategy… |
| 10 | `risk_intro` — Two different questions about risk | interstitial | always | — |
| 11 | `risk_capacity` — Your risk capacity | question | always | `rc_capital_band` (single, required): Roughly how much do you intend to trade with?<br>`rc_living_dependence` (single, required): Would losing this money affect your ability to pay living expenses?<br>`rc_emergency_fund` (single, required): Do you have emergency savings separate from this money?<br>`rc_horizon` (single, required): How long could this money stay invested if markets went against you?<br>`rc_max_loss` (single, required): The largest fall in this money you could accept without changing your life plans: |
| 12 | `risk_tolerance` — Your comfort with risk | question | always | `rt_volatility` (single, required): Large day-to-day swings in value…<br>`rt_temporary_loss` (single, required): Seeing a position down 10% before it recovers…<br>`rt_consecutive_losses` (single, required): Five losing trades in a row would…<br>`rt_uncertainty` (single, required): Acting when the outcome is genuinely uncertain…<br>`rt_concentration` (single, required): Putting a large share of this money into one position…<br>`rt_leverage` (single, required): Using leverage (borrowed exposure)… |
| 13 | `barriers` — What holds you back today? | question | always | `barriers` (multi, required): Choose any that apply. |
| 14 | `markets` — Where and how long? | question | always | `preferred_markets` (multi, required): Markets you're interested in<br>`holding_periods` (multi, required): How long do you usually want to hold a trade? |
| 15 | `knowledge_leverage` — Leverage and margin | question | {"any_of": [{"q": "experience_by_class", "row_in": {"rows": ["fx", "crypto", "options", "futures"], "values": ["beginner", "intermediate", "experienced"]}}, {"q": "objectives", "includes_any": ["active_trading", "new_markets"]}, {"q": "preferred_markets", "includes_any": ["fx", "crypto", "options", "futures"]}]} | `kq_leverage` (quiz, required): With 10:1 leverage, a 5% move against your position changes your margin by…<br>`kq_margin_call` (quiz, required): A margin call means…<br>`uses_leverage` (single, required): Do you plan to use leverage or margin? |
| 16 | `assistance` — How much help do you want from CSS? | question | always | `assistance_preference` (single, required): Choose the closest fit. |
| 17 | `auto_check` — What Auto does and doesn't change | question | {"q": "assistance_preference", "in": ["auto_interest"]} | `auto_understanding` (single, required): With Auto, which is true? |
| 18 | `support` — How CSS can support you | question | always | `feature_preferences` (multi, required): Which tools would be most useful?<br>`support_level` (single, required): How much explanation do you want with each idea?<br>`learning_style` (multi, required): How do you like to learn? Choose up to three. |
| 19 | `time` — Your time | question | always | `engagement_cadence` (single, required): How often will you check in?<br>`monitoring_availability` (single, required): During market hours, I can usually respond…<br>`notification_preference` (single, required): Notifications: |
| 20 | `expectations_intro` — What do you expect from CSS? | interstitial | always | — |
| 21 | `expectations` — What you expect from CSS | question | always | `ex_primary_value` (single, required): Above all, I want CSS to help me…<br>`ex_trade_frequency` (single, required): How many trades do you expect to make?<br>`ex_risk` (single, required): The level of risk I expect to take:<br>`ex_return_range` (single, required): The yearly result I'm hoping for (an aspiration, not a promise): |
| 22 | `reality_check` — Reality check | question | always | `bl_every_trade_profitable` (boolean, required): Every trade CSS recommends will be profitable.<br>`bl_losses_possible` (boolean, required): I could lose money, including on trades CSS recommends.<br>`bl_drawdowns_normal` (boolean, required): Even good strategies go through periods of losses.<br>`bl_auto_guarantees` (boolean, required): Auto mode guarantees returns.<br>`bl_css_compensates` (boolean, required): CSS will pay me back for trading losses.<br>`ex_success` (multi, required): A successful CSS experience would mean… |
| 23 | `attribution_paths` — Two kinds of trades, kept apart | interstitial | always | — |
| 24 | `acknowledgements` — Before your Passport | question | always | `ack_attribution` (consent, required): I understand how CSS labels and separates its recommendations from my own trades.<br>`ack_no_guarantee` (consent, required): I understand CSS does not guarantee profits and I may lose money.<br>`ack_recommendation_not_authority` (consent, required): I understand a recommendation is not permission to trade. Execution follows CSS's governed controls, and this questionnaire does not grant any execution authority.<br>`ack_responsibility` (consent, required): I understand I remain responsible for my trading decisions and for checking that CSS suits me. |
| 25 | `passport` — Your CSS Trader Passport | result | always | — |

## Why each question is asked

| Question | Feeds | Purpose (shown to the user as "Why we ask") |
|---|---|---|
| `ack_risk_intro` | acknowledgement | Record that the user saw the risk statement before starting |
| `display_name` | profile | So CSS can greet you and personalise your Passport. A first name or nickname is fine. |
| `full_name` | profile | Optional; only needed later for brokerage-account checks |
| `email` | contact | Used for your account and essential service messages, like security notices. |
| `phone` | contact | Only needed if you want messages by text. Leave it blank otherwise. |
| `country` | contact | Which features and rules apply where the user lives |
| `preferred_channel` | engagement | So CSS sends updates where you will actually see them. |
| `consent_service_notifications` | consent | Opt-in for alerts and service notifications |
| `consent_marketing` | consent | Product news is separate from service messages. You can change this any time. |
| `objectives` | objectives | What the user wants from trading and CSS |
| `objective_ranking` | objectives | Financial priorities, which shape risk and mode guidance |
| `experience_by_class` | experience | Experience differs by market. This helps CSS pitch explanations at the right level for each one. |
| `css_familiarity` | css_familiarity | How much product explanation the user needs |
| `kq_market_vs_limit` | market_knowledge | Checks your familiarity with order types, so CSS explains only what is new. It is not graded against you. |
| `kq_stop` | market_knowledge | Checks your familiarity with stop orders, so CSS explains only what is new. It is not graded against you. |
| `kq_position_size` | market_knowledge | Checks your familiarity with position sizing, so CSS explains only what is new. It is not graded against you. |
| `kq_risk_reward` | market_knowledge | Checks your familiarity with risk reward, so CSS explains only what is new. It is not graded against you. |
| `kq_volatility` | market_knowledge | Checks your familiarity with volatility, so CSS explains only what is new. It is not graded against you. |
| `kq_drawdown` | market_knowledge | Checks your familiarity with drawdown, so CSS explains only what is new. It is not graded against you. |
| `kq_diversification` | market_knowledge | Checks your familiarity with diversification, so CSS explains only what is new. It is not graded against you. |
| `kq_exposure` | market_knowledge | Checks your familiarity with portfolio exposure, so CSS explains only what is new. It is not graded against you. |
| `thinking_style` | decision_style | Detail vs pattern vs big-picture tendency, used to tailor Trade Card presentation |
| `strengths` | strengths | Self-described analytical and working strengths |
| `bh_decision_speed` | decision_style | Decision speed; sets alert decision windows |
| `bh_after_losses` | risk_discipline | How you respond after losses helps CSS decide which reminders to show you. |
| `bh_drawdown_reaction` | risk_discipline | Shows how CSS can support you when markets fall sharply. |
| `bh_size_after_loss` | risk_discipline | Increasing size to win back losses is a common risk; CSS can flag it for you. |
| `bh_exit_rule` | risk_discipline | Planning exits in advance is a core habit; this tells CSS how much to prompt for one. |
| `bh_strategy_switch` | decision_style | Strategy consistency under short-term underperformance |
| `rc_capital_band` | risk_capacity | Scale of capital, for context (bands, not precise figures) |
| `rc_living_dependence` | risk_capacity | Dependence on this capital for living expenses |
| `rc_emergency_fund` | risk_capacity | Savings outside trading affect how much loss your finances can absorb. |
| `rc_horizon` | risk_capacity | Money needed soon can absorb less risk. This sets your risk capacity. |
| `rc_max_loss` | loss_tolerance | Largest fall the user's finances can accept (drawdown capacity) |
| `rt_volatility` | risk_tolerance | Measures comfort with price swings, which is separate from what you can afford. |
| `rt_temporary_loss` | loss_tolerance | Comfort with temporary losses (drawdown comfort) |
| `rt_consecutive_losses` | loss_tolerance | Losing runs happen to everyone; this shows how they would feel for you. |
| `rt_uncertainty` | risk_tolerance | Markets never give certainty; this shows how CSS should present probabilities. |
| `rt_concentration` | risk_tolerance | Shows how comfortable you are with a lot in one position. |
| `rt_leverage` | risk_tolerance | Shows your comfort with borrowed exposure, which magnifies gains and losses. |
| `barriers` | development_areas | Principal barriers and weaknesses, to target support |
| `preferred_markets` | markets | So CSS focuses on the markets you actually want to trade. |
| `holding_periods` | holding_period | How long you hold trades should match the time you have to watch them. |
| `kq_leverage` | market_knowledge | Checks your familiarity with leverage, so CSS explains only what is new. It is not graded against you. |
| `kq_margin_call` | market_knowledge | Checks your familiarity with margin, so CSS explains only what is new. It is not graded against you. |
| `uses_leverage` | leverage_familiarity | Lets CSS add the right safeguards and education if you plan to use leverage. |
| `assistance_preference` | assistance | Desired level of CSS assistance (preference only; never authority) |
| `auto_understanding` | expectations | Check the user understands Auto does not remove market risk |
| `feature_preferences` | features | So CSS shows the tools you care about first instead of everything at once. |
| `support_level` | support_preference | How much explanation CSS shows by default |
| `learning_style` | support_preference | So learning material comes in the format that works best for you. |
| `engagement_cadence` | engagement | Available trading time: how often the user checks in |
| `monitoring_availability` | engagement | Typical decision window during market hours |
| `notification_preference` | engagement | So alerts are useful rather than noise. |
| `ex_primary_value` | expectations | What the user mainly expects CSS to do for them |
| `ex_trade_frequency` | expectations | Checks whether your expected pace fits the time you have available. |
| `ex_risk` | expectations | Self-assessed risk appetite, checked against measured capacity |
| `ex_return_range` | expectations | Hoped-for yearly result (aspiration), checked for realism |
| `bl_every_trade_profitable` | expectations | Checks expectations early, because no approach wins every trade. |
| `bl_losses_possible` | expectations | Confirm losses are understood to be possible |
| `bl_drawdowns_normal` | loss_tolerance | Checks that periods of decline are expected, because every approach has them. |
| `bl_auto_guarantees` | expectations | Checks that automation is understood as a way of placing trades, not a guarantee. |
| `bl_css_compensates` | expectations | Makes clear who bears trading losses before you start. |
| `ex_success` | expectations | What a useful CSS experience means to the user |
| `ack_attribution` | acknowledgement | Record understanding of trade-origin labelling |
| `ack_no_guarantee` | acknowledgement | Record understanding that profit is not guaranteed |
| `ack_recommendation_not_authority` | acknowledgement | Record that recommendations are not execution authority |
| `ack_responsibility` | acknowledgement | Record that the user remains responsible |

## Options

- `preferred_channel`: `in_app` In the app; `email` Email; `push` Push notifications; `sms` Text message
- `objectives`: `learn` Learn to trade; `improve_process` Improve my existing process; `supplement_investing` Add to my wider investing; `active_trading` Trade actively; `diversify` Diversify my portfolio; `systematic_support` Systematic decision support; `discipline` Become more disciplined; `new_markets` Explore new markets
- `objective_ranking`: `preservation` Protect what I have; `steady_growth` Steady growth; `long_term_wealth` Long-term wealth; `supplement` Supplement other investments; `aggressive_growth` Aggressive growth; `accessibility` Keep money accessible
- `experience_by_class`: `none` None; `beginner` Beginner; `intermediate` Intermediate; `experienced` Experienced
  - rows: Stocks (equities), ETFs, Currencies (FX), Crypto, Options, Futures
- `css_familiarity`: `new` No, this is new to me; `other_tools` I've used other trading or analysis tools; `css_before` I've used CSS before
- `kq_market_vs_limit`: `a` Fills immediately at whatever the market price is; `b` Fills only at your chosen price or better; `c` Closes a trade automatically after a loss; `not_sure` I'm not sure yet — correct: `b`
- `kq_stop`: `a` Guarantee the exit price; `b` Limit a loss by exiting once a price is reached; `c` Increase position size when price falls; `not_sure` I'm not sure yet — correct: `b`
- `kq_position_size`: `a` $10; `b` $100; `c` $1,000; `not_sure` I'm not sure yet — correct: `b`
- `kq_risk_reward`: `a` 1 : 3; `b` 3 : 1; `c` It depends on the win rate only; `not_sure` I'm not sure yet — correct: `b`
- `kq_volatility`: `a` Larger and faster price swings, up and down; `b` Prices only go up; `c` Less risk; `not_sure` I'm not sure yet — correct: `a`
- `kq_drawdown`: `a` $9,000; `b` 25%; `c` 75%; `not_sure` I'm not sure yet — correct: `b`
- `kq_diversification`: `a` Remove all risk; `b` Reduce the impact of any single position going wrong; `c` Guarantee higher returns; `not_sure` I'm not sure yet — correct: `b`
- `kq_exposure`: `a` About 20%; `b` About 60%; `c` Unknown without prices; `not_sure` I'm not sure yet — correct: `b`
- `thinking_style`: `detail` The details; `pattern` The patterns; `big_picture` The big picture
- `strengths`: `quantitative` Comfortable with numbers; `disciplined` Disciplined / process-driven; `patient` Patient; `research` Research-oriented; `decisive` Decisive; `risk_aware` Risk-aware; `adaptable` Adaptable
- `bh_decision_speed`: `quick` Decide quickly and confidently; `considered` Decide, but prefer a little time; `slow` Need time; quick decisions stress me
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
- `feature_preferences`: `trade_cards` CSS Trade Cards; `discovery` Opportunity discovery; `alerts` Alerts; `simulator` Simulator / paper trading; `analytics` Performance analytics; `journal` Trade journal; `ai_assist` AI assistance; `risk_monitoring` Risk monitoring
- `support_level`: `full` Walk me through it; `key_points` Just the key points; `minimal` Minimal: I'll ask if I need more
- `learning_style`: `short_reads` Short reads; `worked_examples` Worked examples; `video` Short videos; `practice` Practice in the simulator; `checklists` Checklists
- `engagement_cadence`: `several_daily` Several times a day; `daily` Once a day; `few_weekly` A few times a week; `weekly` Weekly or less
- `monitoring_availability`: `within_minutes` Within minutes; `within_hours` Within a few hours; `end_of_day` By the end of the day
- `notification_preference`: `important_only` Only important ones; `daily_digest` A daily digest; `all` Everything relevant; `none` None for now
- `ex_primary_value`: `find` Find opportunities; `understand` Understand what markets are doing; `stick_to_plan` Stick to a plan; `manage_risk` Manage risk; `save_time` Save time
- `ex_trade_frequency`: `few_monthly` A few a month; `weekly` A few a week; `daily` About one a day; `many_daily` Many a day
- `ex_risk`: `low` Low; `moderate` Moderate; `high` High
- `ex_return_range`: `preserve` Mostly preserve capital; `modest` Modest growth; `strong` Strong growth; `double_plus` Double my money or more; `unsure` I don't know
- `ex_success`: `better_decisions` Better, more consistent decisions; `learning` Learning a lot; `discipline` More discipline; `time_saved` Saving time; `returns` Better results over time; `every_trade_wins` Every trade making money
