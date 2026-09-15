from fastapi.testclient import TestClient

from dashboard.runtime.trial_contract_router import create_trial_contract_router
from fastapi import FastAPI


def test_trial_contract_router_exposes_required_routes():
    app = FastAPI()
    app.include_router(create_trial_contract_router())
    routes = {route.path for route in app.routes}
    assert "/api/v1/commercial-trial/agreement" in routes
    assert "/api/v1/commercial-trial/enroll" in routes
    assert "/api/v1/commercial-trial/cancel" in routes
    assert "/api/v1/commercial-trial/status" in routes


def test_trial_contract_openapi_keeps_acceptance_and_cancellation_explicit():
    app = FastAPI()
    app.include_router(create_trial_contract_router())
    schema = TestClient(app).get("/openapi.json").json()
    paths = schema["paths"]
    assert "post" in paths["/api/v1/commercial-trial/enroll"]
    assert "post" in paths["/api/v1/commercial-trial/cancel"]
    assert "get" in paths["/api/v1/commercial-trial/status"]
