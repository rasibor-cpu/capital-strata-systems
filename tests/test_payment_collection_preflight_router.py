from dashboard.runtime.payment_collection_preflight_router import (
    create_payment_collection_preflight_router,
)


def test_payment_collection_preflight_router_is_get_only():
    router = create_payment_collection_preflight_router()
    routes = {
        getattr(route, "path", ""): set(getattr(route, "methods", set()) or set())
        for route in router.routes
    }
    path = "/api/v1/payment-collection/preflight"
    assert path in routes
    assert routes[path] == {"GET"}
