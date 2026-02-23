"""Generate OpenAPI schema containing only portal endpoints.

Filters the full OpenAPI spec to include only /portal/* paths and their
referenced schemas, then adds a JWT Bearer security scheme.
"""

import json
import re
import sys


def collect_refs(obj: object) -> set[str]:
    """Recursively collect all $ref schema names from an OpenAPI object."""
    refs: set[str] = set()
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref = obj["$ref"]
            match = re.search(r"/([^/]+)$", ref)
            if match:
                refs.add(match.group(1))
        for value in obj.values():
            refs |= collect_refs(value)
    elif isinstance(obj, list):
        for item in obj:
            refs |= collect_refs(item)
    return refs


def resolve_all_refs(schema_names: set[str], schemas: dict) -> set[str]:
    """Transitively resolve all schema references."""
    resolved: set[str] = set()
    queue = list(schema_names)
    while queue:
        name = queue.pop()
        if name in resolved or name not in schemas:
            continue
        resolved.add(name)
        nested = collect_refs(schemas[name])
        queue.extend(nested - resolved)
    return resolved


def generate_portal_openapi(full_spec: dict) -> dict:
    """Filter the full OpenAPI spec to portal-only endpoints with JWT auth."""
    portal_paths: dict = {}
    for path, methods in full_spec.get("paths", {}).items():
        if path.startswith("/portal"):
            portal_paths[path] = methods

    if not portal_paths:
        print("Warning: no /portal paths found in spec", file=sys.stderr)

    all_schemas = full_spec.get("components", {}).get("schemas", {})
    referenced = collect_refs(portal_paths)
    all_referenced = resolve_all_refs(referenced, all_schemas)
    portal_schemas = {k: v for k, v in all_schemas.items() if k in all_referenced}

    portal_spec: dict = {
        "openapi": full_spec.get("openapi", "3.1.0"),
        "info": {
            "title": "BXB Customer Portal API",
            "description": (
                "Customer self-service portal API. "
                "Authenticate using a JWT token passed as a query parameter."
            ),
            "version": full_spec.get("info", {}).get("version", "0.1.0"),
        },
        "paths": portal_paths,
        "components": {
            "schemas": portal_schemas,
            "securitySchemes": {
                "PortalJWT": {
                    "type": "apiKey",
                    "in": "query",
                    "name": "token",
                    "description": "JWT token for portal customer authentication.",
                },
            },
        },
        "security": [{"PortalJWT": []}],
    }

    return portal_spec


if __name__ == "__main__":
    try:
        from generate_openapi import _patched_remap  # noqa: F401 — applies the monkey-patch
    except (ImportError, AttributeError):
        pass  # Patch not needed on newer FastAPI versions

    from app.main import app  # noqa: E402

    full_spec = app.openapi()
    portal_spec = generate_portal_openapi(full_spec)
    print(json.dumps(portal_spec, indent=2))
