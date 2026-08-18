"""JSON Schemas for the orders API responses.

INFERRED - not contract-backed. These describe the conventional REST shape for
an orders resource. Replace them with schemas generated from your OpenAPI spec
once you have one, or adjust the required fields to match your actual payloads.
"""

ORDER_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["id", "status", "items"],
    "properties": {
        "id": {"type": ["string", "integer"]},
        "customerId": {"type": ["string", "integer"]},
        "status": {
            "type": "string",
            "enum": ["pending", "confirmed", "processing", "shipped", "delivered", "cancelled"],
        },
        "currency": {"type": "string", "minLength": 3, "maxLength": 3},
        "total": {"type": ["number", "string"]},
        "createdAt": {"type": "string"},
        "updatedAt": {"type": ["string", "null"]},
        "items": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["sku", "quantity"],
                "properties": {
                    "sku": {"type": "string"},
                    "quantity": {"type": "integer", "minimum": 1},
                    "unitPrice": {"type": ["number", "string"]},
                },
            },
        },
    },
}

ORDER_LIST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "oneOf": [
        {"type": "array", "items": ORDER_SCHEMA},
        {
            "type": "object",
            "required": ["data"],
            "properties": {
                "data": {"type": "array", "items": ORDER_SCHEMA},
                "total": {"type": "integer"},
                "page": {"type": "integer"},
                "pageSize": {"type": "integer"},
                "nextPage": {"type": ["string", "integer", "null"]},
            },
        },
        {
            "type": "object",
            "required": ["items"],
            "properties": {"items": {"type": "array", "items": ORDER_SCHEMA}},
        },
    ],
}

ERROR_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "anyOf": [
        {"required": ["error"]},
        {"required": ["message"]},
        {"required": ["detail"]},
        {"required": ["title"]},
    ],
}


def extract_orders(payload):
    """Pull the order array out of whichever envelope the API uses."""
    if isinstance(payload, list):
        return payload
    for key in ("data", "items", "orders", "results"):
        if isinstance(payload.get(key), list):
            return payload[key]
    raise AssertionError(f"No order array found in response. Keys: {list(payload)}")
