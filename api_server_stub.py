"""
api_server_stub.py — REA Capital Trading Engine (Local API Stub)
---------------------------------------------------------------
READ-ONLY v1 API surface. Standard library only.

Endpoints:
- GET /health
- GET /api/ledger/list
- GET /api/ledger/balances?ledger=...&currency=...&as_of=YYYY-MM-DD
- GET /api/ledger/state/eod?as_of=YYYY-MM-DD
- GET /api/reports/ageing?as_of=YYYY-MM-DD
- GET /api/eod/validations?as_of=YYYY-MM-DD
- GET /api/financials?as_of=YYYY-MM-DD&period=daily|monthly|yearly

Notes:
- Uses an Adapter interface. DemoAdapter is provided to run immediately.
- Later we replace DemoAdapter with a RealAdapter that reads from:
  batch_close.py, ageing.py, eod_validations.py, posting_ledger.py
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone
import json
import uuid
from typing import Any, Dict, Optional, List


# =====================================================
# Helpers
# =====================================================

def _utc_now() -> str:
    # Python 3.14+ safe (timezone-aware)
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json(handler: BaseHTTPRequestHandler, status_code: int, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _bad_request(handler: BaseHTTPRequestHandler, request_id: str, message: str) -> None:
    _json(handler, 400, {
        "status": "ERROR",
        "timestamp": _utc_now(),
        "request_id": request_id,
        "error": {"message": message}
    })


def _not_found(handler: BaseHTTPRequestHandler, request_id: str) -> None:
    _json(handler, 404, {
        "status": "ERROR",
        "timestamp": _utc_now(),
        "request_id": request_id,
        "error": {"message": "Not found"}
    })


def _get_qs(qs: Dict[str, Any], key: str) -> Optional[str]:
    v = qs.get(key)
    if not v:
        return None
    if isinstance(v, list) and len(v) > 0:
        return str(v[0])
    return str(v)


# =====================================================
# Adapter Interface (documented by behavior)
# =====================================================

class Adapter:
    def list_ledgers(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def get_ledger_balances(self, ledger: str, currency: str, as_of: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_eod_state(self, as_of: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_ageing(self, as_of: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_eod_validations(self, as_of: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_financials(self, as_of: str, period: str) -> Dict[str, Any]:
        raise NotImplementedError


# =====================================================
# Demo Adapter (runs immediately)
# Replace later with RealAdapter wiring to your engines.
# =====================================================

class DemoAdapter(Adapter):
    def list_ledgers(self) -> List[Dict[str, Any]]:
        return [
            {"ledger": "LEDGER-ACME-USD", "currency": "USD", "domain": "TREASURY"},
            {"ledger": "LEDGER-SUSPENSE-USD", "currency": "USD", "domain": "TREASURY"},
            {"ledger": "LEDGER-SUNDRY-USD", "currency": "USD", "domain": "TREASURY"},
        ]

    def get_ledger_balances(self, ledger: str, currency: str, as_of: str) -> Dict[str, Any]:
        return {
            "status": "OK",
            "ledger": ledger,
            "currency": currency,
            "as_of": as_of,
            "opening_balance": 0.0,
            "debits": 0.0,
            "credits": 0.0,
            "closing_balance": 0.0
        }

    def get_eod_state(self, as_of: str) -> Dict[str, Any]:
        return {
            "status": "OK",
            "as_of": as_of,
            "ledgers": []
        }

    def get_ageing(self, as_of: str) -> Dict[str, Any]:
        return {
            "status": "OK",
            "as_of": as_of,
            "ageing": {}
        }

    def get_eod_validations(self, as_of: str) -> Dict[str, Any]:
        return {
            "status": "OK",
            "as_of": as_of,
            "breaches": []
        }

    def get_financials(self, as_of: str, period: str) -> Dict[str, Any]:
        return {
            "status": "OK",
            "period": period,
            "as_of": as_of,
            "balance_sheet": {"assets": 0.0, "liabilities": 0.0, "equity": 0.0},
            "pnl": {"income": 0.0, "expenses": 0.0, "net": 0.0}
        }


# =====================================================
# HTTP Handler
# =====================================================

class APIServerHandler(BaseHTTPRequestHandler):
    adapter: Adapter = DemoAdapter()

    def log_message(self, format: str, *args: Any) -> None:
        # quiet default logging
        return

    def do_GET(self) -> None:
        request_id = str(uuid.uuid4())
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        # Health check
        if path == "/health":
            return _json(self, 200, {
                "status": "OK",
                "timestamp": _utc_now(),
                "request_id": request_id,
                "service": "rea-api-stub",
                "version": "v1"
            })

        # GET /api/ledger/list
        if path == "/api/ledger/list":
            items = self.adapter.list_ledgers()
            return _json(self, 200, {
                "status": "OK",
                "timestamp": _utc_now(),
                "request_id": request_id,
                "ledgers": items
            })

        # GET /api/ledger/balances
        if path == "/api/ledger/balances":
            ledger = _get_qs(qs, "ledger")
            currency = _get_qs(qs, "currency")
            as_of = _get_qs(qs, "as_of")
            if not ledger or not currency or not as_of:
                return _bad_request(self, request_id, "Missing required params: ledger, currency, as_of")

            payload = self.adapter.get_ledger_balances(ledger, currency, as_of)
            payload["request_id"] = request_id
            payload["timestamp"] = _utc_now()
            return _json(self, 200, payload)

        # GET /api/ledger/state/eod
        if path == "/api/ledger/state/eod":
            as_of = _get_qs(qs, "as_of")
            if not as_of:
                return _bad_request(self, request_id, "Missing required param: as_of")

            payload = self.adapter.get_eod_state(as_of)
            payload["request_id"] = request_id
            payload["timestamp"] = _utc_now()
            return _json(self, 200, payload)

        # GET /api/reports/ageing
        if path == "/api/reports/ageing":
            as_of = _get_qs(qs, "as_of")
            if not as_of:
                return _bad_request(self, request_id, "Missing required param: as_of")

            payload = self.adapter.get_ageing(as_of)
            payload["request_id"] = request_id
            payload["timestamp"] = _utc_now()
            return _json(self, 200, payload)

        # GET /api/eod/validations
        if path == "/api/eod/validations":
            as_of = _get_qs(qs, "as_of")
            if not as_of:
                return _bad_request(self, request_id, "Missing required param: as_of")

            payload = self.adapter.get_eod_validations(as_of)
            payload["request_id"] = request_id
            payload["timestamp"] = _utc_now()
            return _json(self, 200, payload)

        # GET /api/financials
        if path == "/api/financials":
            as_of = _get_qs(qs, "as_of")
            period = _get_qs(qs, "period") or "daily"
            if not as_of:
                return _bad_request(self, request_id, "Missing required param: as_of")
            if period not in ("daily", "monthly", "yearly"):
                return _bad_request(self, request_id, "Invalid period. Use daily|monthly|yearly")

            payload = self.adapter.get_financials(as_of, period)
            payload["request_id"] = request_id
            payload["timestamp"] = _utc_now()
            return _json(self, 200, payload)

        return _not_found(self, request_id)


# =====================================================
# Main
# =====================================================

def main() -> None:
    host = "127.0.0.1"
    port = 8080
    httpd = HTTPServer((host, port), APIServerHandler)
    print(f"REA API stub running on http://{host}:{port}")
    print("Try:")
    print("  http://127.0.0.1:8080/health")
    print("  http://127.0.0.1:8080/api/ledger/list")
    print("  http://127.0.0.1:8080/api/ledger/balances?ledger=LEDGER-ACME-USD&currency=USD&as_of=2026-01-30")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
