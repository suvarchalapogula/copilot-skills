"""A minimal in-memory orders API for exercising the test suite.

Implements exactly the contract described in schemas.py so the full suite —
including the destructive lifecycle tests — can run with no external service.
Standard library only; no dependencies to install.

    python mock_server.py            # serves on http://127.0.0.1:8000
    python mock_server.py 9000       # or pick a port

Auth: send "Authorization: Bearer test-token". Anything else gets a 401.

This is a TEST FIXTURE, not a production server. It stores data in memory,
serves one request at a time, and has no persistence or security hardening.
"""

import json
import sys
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

VALID_TOKEN = "test-token"
ORDERS = {}


def _seed():
    """Pre-load orders so list and pagination tests have data to work with."""
    for index in range(12):
        order_id = str(uuid.uuid4())
        ORDERS[order_id] = {
            "id": order_id,
            "customerId": f"seed-customer-{index:02d}",
            "status": "pending",
            "currency": "USD",
            "total": round(19.98 + index, 2),
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": None,
            "items": [{"sku": f"SEED-SKU-{index}", "quantity": 2, "unitPrice": 9.99}],
        }


class OrdersHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # ---------------------------------------------------------------- helpers

    def _send(self, status, payload=None):
        body = json.dumps(payload).encode() if payload is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _authorized(self):
        if self.headers.get("Authorization") == f"Bearer {VALID_TOKEN}":
            return True
        self._send(401, {"error": "unauthorized", "message": "A valid bearer token is required."})
        return False

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return None

    def _route(self):
        """Return (collection_hit, order_id_or_None, query_dict)."""
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        if parts and parts[0] == "v1":
            parts = parts[1:]
        if not parts or parts[0] != "orders":
            return False, None, query
        return True, (parts[1] if len(parts) > 1 else None), query

    def _validate(self, payload):
        if payload is None:
            return "Request body is not valid JSON."
        if not payload.get("items"):
            return "At least one item is required."
        if not payload.get("customerId"):
            return "customerId is required."
        return None

    # ------------------------------------------------------------------ verbs

    def do_GET(self):
        is_orders, order_id, query = self._route()
        if not is_orders:
            return self._send(404, {"error": "not_found"})
        if not self._authorized():
            return

        if order_id:
            order = ORDERS.get(order_id)
            if not order:
                return self._send(404, {"error": "not_found", "message": f"No order {order_id}."})
            return self._send(200, order)

        page = max(1, int(query.get("page", 1)))
        page_size = max(1, min(100, int(query.get("pageSize", 20))))
        everything = list(ORDERS.values())
        start = (page - 1) * page_size
        window = everything[start : start + page_size]
        return self._send(
            200,
            {
                "data": window,
                "total": len(everything),
                "page": page,
                "pageSize": page_size,
                "nextPage": page + 1 if start + page_size < len(everything) else None,
            },
        )

    def do_POST(self):
        is_orders, order_id, _ = self._route()
        if not is_orders or order_id:
            return self._send(404, {"error": "not_found"})
        if not self._authorized():
            return

        payload = self._body()
        problem = self._validate(payload)
        if problem:
            return self._send(400, {"error": "validation_failed", "message": problem})

        new_id = str(uuid.uuid4())
        items = payload["items"]
        order = {
            "id": new_id,
            "customerId": payload["customerId"],
            "status": "pending",
            "currency": payload.get("currency", "USD"),
            "total": round(sum(i.get("quantity", 1) * i.get("unitPrice", 0) for i in items), 2),
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": None,
            "items": items,
        }
        ORDERS[new_id] = order
        return self._send(201, order)

    def _update(self, replace):
        is_orders, order_id, _ = self._route()
        if not is_orders or not order_id:
            return self._send(404, {"error": "not_found"})
        if not self._authorized():
            return
        order = ORDERS.get(order_id)
        if not order:
            return self._send(404, {"error": "not_found"})

        payload = self._body()
        if payload is None:
            return self._send(400, {"error": "validation_failed"})
        if replace:
            problem = self._validate(payload)
            if problem:
                return self._send(400, {"error": "validation_failed", "message": problem})

        order.update({k: v for k, v in payload.items() if k != "id"})
        order["updatedAt"] = datetime.now(timezone.utc).isoformat()
        return self._send(200, order)

    def do_PATCH(self):
        self._update(replace=False)

    def do_PUT(self):
        self._update(replace=True)

    def do_DELETE(self):
        is_orders, order_id, _ = self._route()
        if not is_orders or not order_id:
            return self._send(404, {"error": "not_found"})
        if not self._authorized():
            return
        if ORDERS.pop(order_id, None) is None:
            return self._send(404, {"error": "not_found"})
        return self._send(204)

    def log_message(self, *args):
        pass  # keep the CI log readable


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    _seed()
    print(f"Mock orders API listening on http://127.0.0.1:{port} ({len(ORDERS)} seeded orders)")
    HTTPServer(("127.0.0.1", port), OrdersHandler).serve_forever()
