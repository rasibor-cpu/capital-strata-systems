# CSS UI Function Capability Matrix

Phase 176C machine-readable registry export.

**Phase 176D note:** Reports Center HTML/API/mobile now share one canonical
`CSSAuthorizationContext` (session bridge). Pre-176D API ALLOW / HTML DENY
divergence is remediated. Intentionally unavailable COMING_SOON / DISABLED /
FAIL_CLOSED controls are unchanged.

**Phase 176E note:** Canonical launcher (port 8765) mounts
`create_reports_center_router()` so Mission Control Generate
`POST /api/v1/reports/generate` is REGISTERED_AND_REACHABLE on the same host
that serves the Reports UI (relative URL). See
`PHASE_176E_REPORT_GENERATION_ROUTE_RECONCILIATION.md`.

**Phase 176F note:** Report cards / Create selector use canonical
`ui_report_definition` + `evaluate_report_capabilities` so permission *names*
and effective `can_generate` are not stripped by a reduced DTO. See
`PHASE_176F_REPORT_PERMISSION_AND_GENERATABILITY_RECONCILIATION.md`.

- Total controls: **144**
- Pages audited: **49**
- Sub-tabs audited: **5**
- Status counts: `{'FUNCTIONAL': 111, 'FUNCTIONAL_WITH_LIMITATIONS': 16, 'FAIL_CLOSED': 16, 'DISABLED': 1}`

| control_id | page | label | type | desktop_route | mobile_route | api/service | status | desktop/mobile | limitation | test_id |
|---|---|---|---|---|---|---|---|---|---|---|
| `mc.nav.executive_overview` | mission_control_shell | Executive Overview | nav | /mission-control/executive-overview | — | GET /mission-control/executive-overview | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_mc_nav_routes_render` |
| `mc.nav.reports_center` | mission_control_shell | Reports | nav | /mission-control/reports | — | GET /mission-control/reports | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_mc_nav_routes_render` |
| `mc.nav.runtime_operations` | mission_control_shell | Runtime Operations | nav | /mission-control/runtime-operations | — | GET /mission-control/runtime-operations | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_mc_nav_routes_render` |
| `mc.nav.trade_operations` | mission_control_shell | Trade Operations | nav | /mission-control/trade-operations | — | GET /mission-control/trade-operations | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_mc_nav_routes_render` |
| `mc.nav.portfolio` | mission_control_shell | Portfolio | nav | /mission-control/portfolio | — | GET /mission-control/portfolio | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_mc_nav_routes_render` |
| `mc.nav.market_intelligence` | mission_control_shell | Market Intelligence | nav | /mission-control/market-intelligence | — | GET /mission-control/market-intelligence | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_mc_nav_routes_render` |
| `mc.nav.risk_command` | mission_control_shell | Risk Command | nav | /mission-control/risk-command | — | GET /mission-control/risk-command | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_mc_nav_routes_render` |
| `mc.nav.options_income` | mission_control_shell | Options Income | nav | /mission-control/options-income | — | GET /mission-control/options-income | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_mc_nav_routes_render` |
| `mc.nav.broker_management` | mission_control_shell | Broker Management | nav | /mission-control/broker-management | — | GET /mission-control/broker-management | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_mc_nav_routes_render` |
| `mc.nav.alerts_incidents` | mission_control_shell | Alerts and Incidents | nav | /mission-control/alerts-incidents | — | GET /mission-control/alerts-incidents | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_mc_nav_routes_render` |
| `mc.nav.certification_readiness` | mission_control_shell | Certification and Readiness | nav | /mission-control/certification-readiness | — | GET /mission-control/certification-readiness | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_mc_nav_routes_render` |
| `mc.nav.audit_explainability` | mission_control_shell | Audit and Explainability | nav | /mission-control/audit-explainability | — | GET /mission-control/audit-explainability | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_mc_nav_routes_render` |
| `mc.nav.learning_performance` | mission_control_shell | Learning and Performance | nav | /mission-control/learning-performance | — | GET /mission-control/learning-performance | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_mc_nav_routes_render` |
| `mc.nav.users_governance` | mission_control_shell | Users and Governance | nav | /mission-control/users-governance | — | GET /mission-control/users-governance | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_mc_nav_routes_render` |
| `mc.nav.system_configuration` | mission_control_shell | System Configuration | nav | /mission-control/system-configuration | — | GET /mission-control/system-configuration | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_mc_nav_routes_render` |
| `mc.nav.documentation_runbooks` | mission_control_shell | Documentation / Runbooks | nav | /mission-control/documentation-runbooks | — | GET /mission-control/documentation-runbooks | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_mc_nav_routes_render` |
| `mc.page.executive_overview.ssr` | executive_overview | Executive Overview SSR view | display | /mission-control/executive-overview | — | GET /mission-control/executive-overview | **FUNCTIONAL_WITH_LIMITATIONS** | DESKTOP_ONLY | SSR metrics/tables only; institutional 'links' cells are escaped text (not hyperlinks) by design to avoid absolute path exposure. | `test_mc_readonly_pages_ssr` |
| `mc.page.executive_overview.mutations` | executive_overview | Executive Overview mutation controls | display | /mission-control/executive-overview | — | — | **FAIL_CLOSED** | DESKTOP_ONLY | Mission Control is GET-only; mutations are intentionally absent. | `test_mc_readonly_pages_ssr` |
| `mc.page.runtime_operations.ssr` | runtime_operations | Runtime Operations SSR view | display | /mission-control/runtime-operations | — | GET /mission-control/runtime-operations | **FUNCTIONAL_WITH_LIMITATIONS** | DESKTOP_ONLY | Read-only runtime evidence; restart/recovery UI not exposed on MC. | `test_mc_readonly_pages_ssr` |
| `mc.page.runtime_operations.mutations` | runtime_operations | Runtime Operations mutation controls | display | /mission-control/runtime-operations | — | — | **FAIL_CLOSED** | DESKTOP_ONLY | Mission Control is GET-only; mutations are intentionally absent. | `test_mc_readonly_pages_ssr` |
| `mc.page.trade_operations.ssr` | trade_operations | Trade Operations SSR view | display | /mission-control/trade-operations | — | GET /mission-control/trade-operations | **FUNCTIONAL_WITH_LIMITATIONS** | DESKTOP_ONLY | No executable trade tickets from Mission Control. | `test_mc_readonly_pages_ssr` |
| `mc.page.trade_operations.mutations` | trade_operations | Trade Operations mutation controls | display | /mission-control/trade-operations | — | — | **FAIL_CLOSED** | DESKTOP_ONLY | Mission Control is GET-only; mutations are intentionally absent. | `test_mc_readonly_pages_ssr` |
| `mc.page.portfolio.ssr` | portfolio | Portfolio SSR view | display | /mission-control/portfolio | — | GET /mission-control/portfolio | **FUNCTIONAL_WITH_LIMITATIONS** | DESKTOP_ONLY | Read-only portfolio projections from runtime state. | `test_mc_readonly_pages_ssr` |
| `mc.page.portfolio.mutations` | portfolio | Portfolio mutation controls | display | /mission-control/portfolio | — | — | **FAIL_CLOSED** | DESKTOP_ONLY | Mission Control is GET-only; mutations are intentionally absent. | `test_mc_readonly_pages_ssr` |
| `mc.page.market_intelligence.ssr` | market_intelligence | Market Intelligence SSR view | display | /mission-control/market-intelligence | — | GET /mission-control/market-intelligence | **FUNCTIONAL_WITH_LIMITATIONS** | DESKTOP_ONLY | Read-only market/overnight intelligence projections. | `test_mc_readonly_pages_ssr` |
| `mc.page.market_intelligence.mutations` | market_intelligence | Market Intelligence mutation controls | display | /mission-control/market-intelligence | — | — | **FAIL_CLOSED** | DESKTOP_ONLY | Mission Control is GET-only; mutations are intentionally absent. | `test_mc_readonly_pages_ssr` |
| `mc.page.risk_command.ssr` | risk_command | Risk Command SSR view | display | /mission-control/risk-command | — | GET /mission-control/risk-command | **FUNCTIONAL_WITH_LIMITATIONS** | DESKTOP_ONLY | Display-only; limits/gates cannot be changed from MC. | `test_mc_readonly_pages_ssr` |
| `mc.page.risk_command.mutations` | risk_command | Risk Command mutation controls | display | /mission-control/risk-command | — | — | **FAIL_CLOSED** | DESKTOP_ONLY | Mission Control is GET-only; mutations are intentionally absent. | `test_mc_readonly_pages_ssr` |
| `mc.page.options_income.ssr` | options_income | Options Income SSR view | display | /mission-control/options-income | — | GET /mission-control/options-income | **FUNCTIONAL_WITH_LIMITATIONS** | DESKTOP_ONLY | Advisory Options Income projections only; no execution. | `test_mc_readonly_pages_ssr` |
| `mc.page.options_income.mutations` | options_income | Options Income mutation controls | display | /mission-control/options-income | — | — | **FAIL_CLOSED** | DESKTOP_ONLY | Mission Control is GET-only; mutations are intentionally absent. | `test_mc_readonly_pages_ssr` |
| `mc.page.broker_management.ssr` | broker_management | Broker Management SSR view | display | /mission-control/broker-management | — | GET /mission-control/broker-management | **FUNCTIONAL_WITH_LIMITATIONS** | DESKTOP_ONLY | Selection/onboarding controls disabled; display-only registry/status. | `test_mc_readonly_pages_ssr` |
| `mc.page.broker_management.mutations` | broker_management | Broker Management mutation controls | display | /mission-control/broker-management | — | — | **FAIL_CLOSED** | DESKTOP_ONLY | Mission Control is GET-only; mutations are intentionally absent. | `test_mc_readonly_pages_ssr` |
| `mc.page.alerts_incidents.ssr` | alerts_incidents | Alerts and Incidents SSR view | display | /mission-control/alerts-incidents | — | GET /mission-control/alerts-incidents | **FUNCTIONAL_WITH_LIMITATIONS** | DESKTOP_ONLY | Acknowledgement actions are DISABLED_READ_ONLY strings, not buttons. | `test_mc_readonly_pages_ssr` |
| `mc.page.alerts_incidents.mutations` | alerts_incidents | Alerts and Incidents mutation controls | display | /mission-control/alerts-incidents | — | — | **FAIL_CLOSED** | DESKTOP_ONLY | Mission Control is GET-only; mutations are intentionally absent. | `test_mc_readonly_pages_ssr` |
| `mc.page.certification_readiness.ssr` | certification_readiness | Certification and Readiness SSR view | display | /mission-control/certification-readiness | — | GET /mission-control/certification-readiness | **FUNCTIONAL_WITH_LIMITATIONS** | DESKTOP_ONLY | Readiness summaries from SSR certification projections. | `test_mc_readonly_pages_ssr` |
| `mc.page.certification_readiness.mutations` | certification_readiness | Certification and Readiness mutation controls | display | /mission-control/certification-readiness | — | — | **FAIL_CLOSED** | DESKTOP_ONLY | Mission Control is GET-only; mutations are intentionally absent. | `test_mc_readonly_pages_ssr` |
| `mc.page.audit_explainability.ssr` | audit_explainability | Audit and Explainability SSR view | display | /mission-control/audit-explainability | — | GET /mission-control/audit-explainability | **FUNCTIONAL_WITH_LIMITATIONS** | DESKTOP_ONLY | Deletion/editing disabled; read-only audit/evidence tables. | `test_mc_readonly_pages_ssr` |
| `mc.page.audit_explainability.mutations` | audit_explainability | Audit and Explainability mutation controls | display | /mission-control/audit-explainability | — | — | **FAIL_CLOSED** | DESKTOP_ONLY | Mission Control is GET-only; mutations are intentionally absent. | `test_mc_readonly_pages_ssr` |
| `mc.page.learning_performance.ssr` | learning_performance | Learning and Performance SSR view | display | /mission-control/learning-performance | — | GET /mission-control/learning-performance | **FUNCTIONAL_WITH_LIMITATIONS** | DESKTOP_ONLY | Advisory strategy/learning metrics only. | `test_mc_readonly_pages_ssr` |
| `mc.page.learning_performance.mutations` | learning_performance | Learning and Performance mutation controls | display | /mission-control/learning-performance | — | — | **FAIL_CLOSED** | DESKTOP_ONLY | Mission Control is GET-only; mutations are intentionally absent. | `test_mc_readonly_pages_ssr` |
| `mc.page.users_governance.ssr` | users_governance | Users and Governance SSR view | display | /mission-control/users-governance | — | GET /mission-control/users-governance | **FUNCTIONAL_WITH_LIMITATIONS** | DESKTOP_ONLY | Role editing disabled on MC; operator console is display-only. | `test_mc_readonly_pages_ssr` |
| `mc.page.users_governance.mutations` | users_governance | Users and Governance mutation controls | display | /mission-control/users-governance | — | — | **FAIL_CLOSED** | DESKTOP_ONLY | Mission Control is GET-only; mutations are intentionally absent. | `test_mc_readonly_pages_ssr` |
| `mc.page.system_configuration.ssr` | system_configuration | System Configuration SSR view | display | /mission-control/system-configuration | — | GET /mission-control/system-configuration | **FUNCTIONAL_WITH_LIMITATIONS** | DESKTOP_ONLY | Cannot edit limits/credentials from MC; editing_enabled=false. | `test_mc_readonly_pages_ssr` |
| `mc.page.system_configuration.mutations` | system_configuration | System Configuration mutation controls | display | /mission-control/system-configuration | — | — | **FAIL_CLOSED** | DESKTOP_ONLY | Mission Control is GET-only; mutations are intentionally absent. | `test_mc_readonly_pages_ssr` |
| `mc.page.documentation_runbooks.ssr` | documentation_runbooks | Documentation / Runbooks SSR view | display | /mission-control/documentation-runbooks | — | GET /mission-control/documentation-runbooks | **FUNCTIONAL_WITH_LIMITATIONS** | DESKTOP_ONLY | Document index is display-only text (absolute filesystem paths intentionally not hyperlinked). | `test_mc_readonly_pages_ssr` |
| `mc.page.documentation_runbooks.mutations` | documentation_runbooks | Documentation / Runbooks mutation controls | display | /mission-control/documentation-runbooks | — | — | **FAIL_CLOSED** | DESKTOP_ONLY | Mission Control is GET-only; mutations are intentionally absent. | `test_mc_readonly_pages_ssr` |
| `mc.reports.subtab.rc-categories` | reports_center | Categories | subtab | /mission-control/reports#rc-categories | — | dashboard.ui_interaction.CSSUIInteraction | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_subtabs_functional` |
| `mc.reports.subtab.rc-frequent` | reports_center | Generatable | subtab | /mission-control/reports#rc-frequent | — | dashboard.ui_interaction.CSSUIInteraction | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_subtabs_functional` |
| `mc.reports.subtab.rc-create` | reports_center | Create Report | subtab | /mission-control/reports#rc-create | — | dashboard.ui_interaction.CSSUIInteraction | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_subtabs_functional` |
| `mc.reports.subtab.rc-library` | reports_center | Library | subtab | /mission-control/reports#rc-library | — | dashboard.ui_interaction.CSSUIInteraction | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_subtabs_functional` |
| `mc.reports.subtab.rc-detail` | reports_center | Detail | subtab | /mission-control/reports#rc-detail | — | dashboard.ui_interaction.CSSUIInteraction | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_subtabs_functional` |
| `mc.reports.expand_all` | reports_center | Expand all | button | /mission-control/reports | — | CSSUIInteraction | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_disclosure_workflow` |
| `mc.reports.collapse_all` | reports_center | Collapse all | button | /mission-control/reports | — | CSSUIInteraction | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_disclosure_workflow` |
| `mc.reports.category.executive_intelligence` | reports_center | Category executive_intelligence | disclosure | /mission-control/reports#cat-executive_intelligence | — | CSSUIInteraction.openDisclosureForTarget | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_category_deeplink` |
| `mc.reports.category.trading_transactions` | reports_center | Category trading_transactions | disclosure | /mission-control/reports#cat-trading_transactions | — | CSSUIInteraction.openDisclosureForTarget | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_category_deeplink` |
| `mc.reports.category.accounts_cash` | reports_center | Category accounts_cash | disclosure | /mission-control/reports#cat-accounts_cash | — | CSSUIInteraction.openDisclosureForTarget | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_category_deeplink` |
| `mc.reports.category.portfolio_performance` | reports_center | Category portfolio_performance | disclosure | /mission-control/reports#cat-portfolio_performance | — | CSSUIInteraction.openDisclosureForTarget | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_category_deeplink` |
| `mc.reports.category.risk_exposure` | reports_center | Category risk_exposure | disclosure | /mission-control/reports#cat-risk_exposure | — | CSSUIInteraction.openDisclosureForTarget | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_category_deeplink` |
| `mc.reports.category.broker_execution` | reports_center | Category broker_execution | disclosure | /mission-control/reports#cat-broker_execution | — | CSSUIInteraction.openDisclosureForTarget | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_category_deeplink` |
| `mc.reports.category.treasury` | reports_center | Category treasury | disclosure | /mission-control/reports#cat-treasury | — | CSSUIInteraction.openDisclosureForTarget | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_category_deeplink` |
| `mc.reports.category.compliance_audit` | reports_center | Category compliance_audit | disclosure | /mission-control/reports#cat-compliance_audit | — | CSSUIInteraction.openDisclosureForTarget | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_category_deeplink` |
| `mc.reports.category.operations_system` | reports_center | Category operations_system | disclosure | /mission-control/reports#cat-operations_system | — | CSSUIInteraction.openDisclosureForTarget | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_category_deeplink` |
| `mc.reports.category.distribution_print_audit` | reports_center | Category distribution_print_audit | disclosure | /mission-control/reports#cat-distribution_print_audit | — | CSSUIInteraction.openDisclosureForTarget | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_category_deeplink` |
| `mc.reports.action.view_readiness` | reports_center | view readiness | api_action | /mission-control/reports | — | GET /mission-control/api/reports/readiness/{code} | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_workflow_e2e` |
| `mc.reports.action.generate` | reports_center | generate | api_action | /mission-control/reports | — | POST /api/v1/reports/generate | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_workflow_e2e` |
| `mc.reports.action.library_refresh` | reports_center | library refresh | api_action | /mission-control/reports | — | GET /mission-control/api/reports | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_workflow_e2e` |
| `mc.reports.action.library_open` | reports_center | library open | api_action | /mission-control/reports | — | GET /mission-control/api/reports/{id} | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_workflow_e2e` |
| `mc.reports.action.detail_print` | reports_center | detail print | api_action | /mission-control/reports | — | GET /mission-control/api/reports/{id}/print | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_workflow_e2e` |
| `mc.reports.action.detail_pdf` | reports_center | detail pdf | api_action | /mission-control/reports | — | GET /mission-control/api/reports/{id}/pdf | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_workflow_e2e` |
| `mc.reports.action.detail_versions` | reports_center | detail versions | api_action | /mission-control/reports | — | GET /mission-control/api/reports/{id}/versions | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_workflow_e2e` |
| `mc.reports.action.detail_audit` | reports_center | detail audit | api_action | /mission-control/reports | — | GET /mission-control/api/reports/{id}/audit | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_workflow_e2e` |
| `mc.reports.action.verify_integrity` | reports_center | verify integrity | api_action | /mission-control/reports | — | POST /api/v1/reports/{id}/verify-integrity | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_workflow_e2e` |
| `mc.reports.action.printable_html` | reports_center | printable html | api_action | /mission-control/reports | — | GET /api/v1/reports/{id}/print | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_reports_workflow_e2e` |
| `mc.reports.non_generatable` | reports_center | Not generatable / unauthorized Generate | button | /mission-control/reports | — | — | **FAIL_CLOSED** | DESKTOP_ONLY | — | `test_reports_rbac_generate_disabled` |
| `web.nav.dashboard` | web_dashboard | Dashboard | nav | /dashboard | — | GET /dashboard | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_nav_functional` |
| `web.nav.positions` | web_positions | Positions | nav | /positions | — | GET /positions | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_nav_functional` |
| `web.nav.trade` | web_trade | Trade | nav | /trade | — | GET /trade | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_nav_functional` |
| `web.nav.trade_summary` | web_trade_summary | Trade Summary | nav | /trade-summary | — | GET /trade-summary | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_nav_functional` |
| `web.nav.command_centre` | web_command_centre | Command Centre | nav | /session-command-centre | — | GET /session-command-centre | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_nav_functional` |
| `web.nav.live_readiness_certification` | web_live_readiness_certification | Live Cert | nav | /live-readiness-certification | — | GET /live-readiness-certification | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_nav_functional` |
| `web.nav.execution` | web_execution | Execution | nav | /execution | — | GET /execution | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_nav_functional` |
| `web.nav.risk_governance` | web_risk_governance | Risk & Governance | nav | /risk-governance | — | GET /risk-governance | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_nav_functional` |
| `web.nav.market_opportunities` | web_market_opportunities | Market | nav | /market-opportunities | — | GET /market-opportunities | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_nav_functional` |
| `web.nav.broker` | web_broker | Broker | nav | /broker | — | GET /broker | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_nav_functional` |
| `web.nav.margin` | web_margin | Margin | nav | /margin | — | GET /margin | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_nav_functional` |
| `web.refresh.dashboard` | web_dashboard | Refresh | refresh | /dashboard | — | GET /api/v1/frontend-state; GET /api/v1/capital-allocation-intelligence | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_refresh_apis` |
| `web.refresh.positions` | web_positions | Refresh | refresh | /positions | — | GET /api/v1/frontend-state | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_refresh_apis` |
| `web.refresh.execution` | web_execution | Refresh | refresh | /execution | — | GET /api/v1/frontend-state | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_refresh_apis` |
| `web.refresh.risk_governance` | web_risk_governance | Refresh | refresh | /risk-governance | — | GET /api/v1/frontend-state | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_refresh_apis` |
| `web.refresh.trade` | web_trade | Refresh | refresh | /trade | — | GET /api/v1/frontend-state | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_refresh_apis` |
| `web.refresh.market_opportunities` | web_market_opportunities | Refresh | refresh | /market-opportunities | — | GET /api/v1/frontend-state | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_refresh_apis` |
| `web.refresh.broker` | web_broker | Refresh | refresh | /broker | — | GET /api/v1/frontend-state | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_refresh_apis` |
| `web.refresh.margin` | web_margin | Refresh | refresh | /margin | — | GET /api/v1/margin-snapshot | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_refresh_apis` |
| `web.trade.search` | web_trade | Trade search | filter | /trade | — | client_filter | **FUNCTIONAL** | DESKTOP_ONLY | Client-side only; does not mutate backend state. | `test_web_trade_filters_present` |
| `web.trade.asset_filter` | web_trade | Asset class filter | filter | /trade | — | client_filter | **FUNCTIONAL** | DESKTOP_ONLY | Client-side only; does not mutate backend state. | `test_web_trade_filters_present` |
| `web.trade.sort` | web_trade | Trade sort | filter | /trade | — | client_filter | **FUNCTIONAL** | DESKTOP_ONLY | Client-side only; does not mutate backend state. | `test_web_trade_filters_present` |
| `web.trade.watch_only` | web_trade | Watchlist only | filter | /trade | — | localStorage | **FUNCTIONAL** | DESKTOP_ONLY | Client-side only; does not mutate backend state. | `test_web_trade_filters_present` |
| `web.trade.watch_toggle` | web_trade | WATCH/WATCHED | filter | /trade | — | localStorage | **FUNCTIONAL** | DESKTOP_ONLY | Client-side only; does not mutate backend state. | `test_web_trade_filters_present` |
| `web.scc.autoload` | web_command_centre | Session Command Centre load | api_action | /session-command-centre | — | GET /api/v1/session-command-centre | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_scc_api` |
| `web.scc.nav_links` | web_command_centre | SCC Navigation Links | link | /session-command-centre | — | GET /api/v1/session-command-centre | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_scc_nav_links_clickable` |
| `web.live_cert.autoload` | web_live_readiness_certification | Live readiness load | api_action | /live-readiness-certification | — | GET /api/v1/live-readiness-certification | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_live_cert_api` |
| `web.trade_summary.autoload` | web_trade_summary | Trade summary load | api_action | /trade-summary | — | GET /api/v1/trade-summary | **FUNCTIONAL** | DESKTOP_ONLY | — | `test_web_trade_summary_api` |
| `mobile.nav.dashboard` | mobile_dashboard | Dashboard | nav | — | /dashboard | GET /dashboard | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.reports` | mobile_reports | Reports | nav | — | /reports | GET /reports | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.positions` | mobile_positions | Positions | nav | — | /positions | GET /positions | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.history` | mobile_history | History | nav | — | /history | GET /history | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.risk` | mobile_risk | Risk | nav | — | /risk | GET /risk | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.governance` | mobile_governance | Governance | nav | — | /governance | GET /governance | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.opportunities` | mobile_opportunities | Opportunities | nav | — | /opportunities | GET /opportunities | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.market` | mobile_market | Market | nav | — | /market | GET /market | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.broker` | mobile_broker | Broker | nav | — | /broker | GET /broker | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.session-command-centre` | mobile_session_command_centre | Command Centre | nav | — | /session-command-centre | GET /session-command-centre | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.trade-status` | mobile_trade_status | Trade Status | nav | — | /trade-status | GET /trade-status | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.trade-summary` | mobile_trade_summary | Trade Summary | nav | — | /trade-summary | GET /trade-summary | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.live-micro-pilot` | mobile_live_micro_pilot | Micro-Pilot | nav | — | /live-micro-pilot | GET /live-micro-pilot | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.live-readiness-certification` | mobile_live_readiness_certification | Live Cert | nav | — | /live-readiness-certification | GET /live-readiness-certification | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.alerts` | mobile_alerts | Alert Centre | nav | — | /alerts | GET /alerts | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.margin` | mobile_margin | Margin | nav | — | /margin | GET /margin | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.audit` | mobile_audit | Audit | nav | — | /audit | GET /audit | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.trade` | mobile_trade | Trade | nav | — | /trade | GET /trade | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.controls` | mobile_controls | Controls | nav | — | /controls | GET /controls | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.users` | mobile_users | Users | nav | — | /users | GET /users | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_nav_active` |
| `mobile.nav.logout` | mobile_shell | Logout | form | — | /logout | POST /logout | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_logout_route` |
| `mobile.reports.category.executive_intelligence` | mobile_reports | Reports category executive_intelligence | disclosure | — | /reports?category=executive_intelligence | ReportsCenterService / ui_contract | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_reports_categories` |
| `mobile.reports.category.trading_transactions` | mobile_reports | Reports category trading_transactions | disclosure | — | /reports?category=trading_transactions | ReportsCenterService / ui_contract | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_reports_categories` |
| `mobile.reports.category.accounts_cash` | mobile_reports | Reports category accounts_cash | disclosure | — | /reports?category=accounts_cash | ReportsCenterService / ui_contract | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_reports_categories` |
| `mobile.reports.category.portfolio_performance` | mobile_reports | Reports category portfolio_performance | disclosure | — | /reports?category=portfolio_performance | ReportsCenterService / ui_contract | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_reports_categories` |
| `mobile.reports.category.risk_exposure` | mobile_reports | Reports category risk_exposure | disclosure | — | /reports?category=risk_exposure | ReportsCenterService / ui_contract | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_reports_categories` |
| `mobile.reports.category.broker_execution` | mobile_reports | Reports category broker_execution | disclosure | — | /reports?category=broker_execution | ReportsCenterService / ui_contract | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_reports_categories` |
| `mobile.reports.category.treasury` | mobile_reports | Reports category treasury | disclosure | — | /reports?category=treasury | ReportsCenterService / ui_contract | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_reports_categories` |
| `mobile.reports.category.compliance_audit` | mobile_reports | Reports category compliance_audit | disclosure | — | /reports?category=compliance_audit | ReportsCenterService / ui_contract | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_reports_categories` |
| `mobile.reports.category.operations_system` | mobile_reports | Reports category operations_system | disclosure | — | /reports?category=operations_system | ReportsCenterService / ui_contract | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_reports_categories` |
| `mobile.reports.category.distribution_print_audit` | mobile_reports | Reports category distribution_print_audit | disclosure | — | /reports?category=distribution_print_audit | ReportsCenterService / ui_contract | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_reports_categories` |
| `mobile.reports.create` | mobile_reports | Create Report | form | — | /reports/create | POST /reports/generate | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_reports_generate` |
| `mobile.reports.library` | mobile_reports | Report Library | filter | — | /reports/library | ReportsCenterService.list_library | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_reports_library_latest` |
| `mobile.reports.library.latest` | mobile_reports | Latest Reports | link | — | /reports/library?view=latest | ReportsCenterService.list_library | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_reports_library_latest` |
| `mobile.reports.print` | mobile_reports | Print preview | link | — | /reports/detail/{id} | GET /api/v1/reports/{id}/print | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_reports_print_mounted` |
| `mobile.reports.pdf` | mobile_reports | PDF info | link | — | /reports/detail/{id} | GET /api/v1/reports/{id}/pdf | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_reports_print_mounted` |
| `mobile.alerts.filter` | mobile_alerts | Alert severity filters | filter | — | /alerts | — | **FUNCTIONAL** | MOBILE_ONLY | Client-side filterAlerts; no backend mutation. | `test_mobile_alerts_filters_present` |
| `mobile.controls.save` | mobile_controls | Save Controls | form | — | /controls | POST /controls | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_controls_rbac` |
| `mobile.users.create` | mobile_users | Create User | form | — | /users | POST /users | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_users_rbac` |
| `mobile.trade.submit` | mobile_trade | Submit Ticket | form | — | /trade | POST /trade | **FUNCTIONAL_WITH_LIMITATIONS** | MOBILE_ONLY | Live trading remains blocked unless explicitly armed under governance; advisory/paper path only by default. | `test_mobile_trade_form_present` |
| `mobile.margin.refresh` | mobile_margin | Refresh Margin | refresh | — | /margin | GET /api/margin-snapshot | **FUNCTIONAL** | MOBILE_ONLY | — | `test_mobile_margin_api` |
| `mobile.micro_pilot.arm_apis` | mobile_live_micro_pilot | Micro-pilot arm/configure APIs | api_action | — | /live-micro-pilot | POST /api/live-micro-pilot/* | **DISABLED** | MOBILE_ONLY | APIs exist but page is display-only; no visible arm/configure controls (honest DISABLED). | `test_mobile_micropilot_display_only` |

## Status legend

- FUNCTIONAL — end-to-end intended workflow verified
- FUNCTIONAL_WITH_LIMITATIONS — works with documented limits
- FAIL_CLOSED — intentionally non-writable / denied
- DISABLED / COMING_SOON — not presented as operational
- BROKEN — must be zero at phase completion
- UNVERIFIED — must be zero at phase completion
