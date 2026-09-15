from dashboard.runtime.commercialization_release_router import (
    create_commercialization_release_router,
)


def test_commercialization_release_router_is_read_only():
    router = create_commercialization_release_router()
    routes = {
        getattr(route, "path", ""): set(getattr(route, "methods", set()) or set())
        for route in router.routes
    }
    path = "/api/v1/commercialization-release/readiness"
    assert path in routes
    assert routes[path] == {"GET"}
