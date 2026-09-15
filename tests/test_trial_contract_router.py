from dashboard.runtime.trial_contract_router import create_trial_contract_router


def _route_map():
    router = create_trial_contract_router()
    return {
        getattr(route, "path", ""): set(getattr(route, "methods", set()) or set())
        for route in router.routes
    }


def test_trial_contract_router_exposes_required_routes():
    routes = _route_map()
    assert "/api/v1/commercial-trial/agreement" in routes
    assert "/api/v1/commercial-trial/enroll" in routes
    assert "/api/v1/commercial-trial/cancel" in routes
    assert "/api/v1/commercial-trial/status" in routes


def test_trial_contract_acceptance_and_cancellation_are_explicit_http_actions():
    routes = _route_map()
    assert "GET" in routes["/api/v1/commercial-trial/agreement"]
    assert "POST" in routes["/api/v1/commercial-trial/enroll"]
    assert "POST" in routes["/api/v1/commercial-trial/cancel"]
    assert "GET" in routes["/api/v1/commercial-trial/status"]
