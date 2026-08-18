"""JSON Schemas for the restful-api.dev Objects API.

Derived from an OBSERVED live response to GET https://api.restful-api.dev/objects,
not from a published OpenAPI document (the service does not publish one). Where a
field's behaviour could not be observed directly it is left permissive rather than
asserted, so the suite does not fail on an assumption.

Observed facts:
  - the collection returns a BARE ARRAY, not an envelope
  - "id" is a STRING, not an integer ("1", "2", ... and a long hex id for new objects)
  - "name" is a non-empty string
  - "data" is an object OR null (object id 2 has data: null)
  - keys inside "data" are free-form and vary per object, including keys with
    spaces ("capacity GB", "CPU model") and mixed value types
"""

OBJECT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
        # Free-form by design: consumers must not assume a fixed inner shape.
        "data": {"type": ["object", "null"]},
        # Present only on create/update responses.
        "createdAt": {"type": "string"},
        "updatedAt": {"type": "string"},
    },
    "additionalProperties": True,
}

OBJECT_LIST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "array",
    "minItems": 1,
    "items": OBJECT_SCHEMA,
}

# The service returns a JSON error body on failures; the exact key was not
# observed, so accept any of the common shapes rather than guess one.
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
