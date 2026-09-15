from dashboard.runtime.production_charging_router import (
    create_production_charging_router,
)


def test_production_charging_router_is_read_only_get_surface():
    router = create_production_charging_router()
    routes = {
        getattr(route, "path", ""): set(getattr(route, "methods", set()) or set())
        for route in router.routes
    }
    path = "/api/v1/production-charging/readiness"
    assert path in routes
    assert routes[path] == {"GET"}
