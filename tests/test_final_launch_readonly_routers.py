from dashboard.runtime.launch_dossier_router import create_launch_dossier_router
from dashboard.runtime.notification_delivery_preflight_router import (
    create_notification_delivery_preflight_router,
)


def test_launch_dossier_export_is_get_only():
    router = create_launch_dossier_router()
    routes = {
        getattr(route, "path", ""): set(getattr(route, "methods", set()) or set())
        for route in router.routes
    }
    assert routes["/api/v1/launch-dossier/export"] == {"GET"}


def test_notification_preflight_is_get_only():
    router = create_notification_delivery_preflight_router()
    routes = {
        getattr(route, "path", ""): set(getattr(route, "methods", set()) or set())
        for route in router.routes
    }
    assert routes["/api/v1/customer-notifications/preflight"] == {"GET"}
