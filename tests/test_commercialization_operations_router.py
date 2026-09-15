from dashboard.runtime.commercialization_operations_router import (
    create_commercialization_operations_router,
)


def test_commercialization_operations_router_is_read_only():
    router = create_commercialization_operations_router()
    routes = {
        getattr(route, "path", ""): set(getattr(route, "methods", set()) or set())
        for route in router.routes
    }
    path = "/api/v1/commercialization-operations/status"
    assert path in routes
    assert routes[path] == {"GET"}
