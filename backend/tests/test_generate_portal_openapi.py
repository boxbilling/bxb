"""Tests for the portal OpenAPI spec generator."""

from scripts.generate_portal_openapi import collect_refs, generate_portal_openapi, resolve_all_refs


class TestCollectRefs:
    def test_simple_ref(self):
        obj = {"$ref": "#/components/schemas/Foo"}
        assert collect_refs(obj) == {"Foo"}

    def test_nested_refs(self):
        obj = {
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/Bar"}
                }
            },
            "other": {"$ref": "#/components/schemas/Baz"},
        }
        assert collect_refs(obj) == {"Bar", "Baz"}

    def test_list_refs(self):
        obj = [{"$ref": "#/components/schemas/A"}, {"$ref": "#/components/schemas/B"}]
        assert collect_refs(obj) == {"A", "B"}

    def test_no_refs(self):
        assert collect_refs({"type": "string"}) == set()
        assert collect_refs("plain") == set()
        assert collect_refs(42) == set()


class TestResolveAllRefs:
    def test_transitive_resolution(self):
        schemas = {
            "A": {"properties": {"b": {"$ref": "#/components/schemas/B"}}},
            "B": {"properties": {"c": {"$ref": "#/components/schemas/C"}}},
            "C": {"type": "string"},
            "D": {"type": "integer"},
        }
        result = resolve_all_refs({"A"}, schemas)
        assert result == {"A", "B", "C"}

    def test_missing_schema(self):
        schemas = {"A": {"properties": {"b": {"$ref": "#/components/schemas/Missing"}}}}
        result = resolve_all_refs({"A"}, schemas)
        assert result == {"A"}

    def test_circular_ref(self):
        schemas = {
            "A": {"properties": {"b": {"$ref": "#/components/schemas/B"}}},
            "B": {"properties": {"a": {"$ref": "#/components/schemas/A"}}},
        }
        result = resolve_all_refs({"A"}, schemas)
        assert result == {"A", "B"}


class TestGeneratePortalOpenapi:
    def test_filters_to_portal_paths(self):
        full_spec = {
            "openapi": "3.1.0",
            "info": {"version": "1.0.0"},
            "paths": {
                "/portal/dashboard": {"get": {"responses": {"200": {}}}},
                "/portal/profile": {"get": {"responses": {"200": {}}}},
                "/v1/customers": {"get": {"responses": {"200": {}}}},
            },
            "components": {"schemas": {}},
        }
        result = generate_portal_openapi(full_spec)
        assert set(result["paths"].keys()) == {"/portal/dashboard", "/portal/profile"}
        assert "/v1/customers" not in result["paths"]

    def test_includes_jwt_security_scheme(self):
        full_spec = {
            "openapi": "3.1.0",
            "info": {"version": "1.0.0"},
            "paths": {"/portal/test": {"get": {}}},
            "components": {"schemas": {}},
        }
        result = generate_portal_openapi(full_spec)
        assert "PortalJWT" in result["components"]["securitySchemes"]
        scheme = result["components"]["securitySchemes"]["PortalJWT"]
        assert scheme["type"] == "apiKey"
        assert scheme["in"] == "query"
        assert scheme["name"] == "token"
        assert result["security"] == [{"PortalJWT": []}]

    def test_includes_only_referenced_schemas(self):
        full_spec = {
            "openapi": "3.1.0",
            "info": {"version": "1.0.0"},
            "paths": {
                "/portal/test": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/Used"}
                                    }
                                }
                            }
                        }
                    }
                },
            },
            "components": {
                "schemas": {
                    "Used": {"type": "object", "properties": {"nested": {"$ref": "#/components/schemas/Nested"}}},
                    "Nested": {"type": "string"},
                    "Unused": {"type": "integer"},
                }
            },
        }
        result = generate_portal_openapi(full_spec)
        assert "Used" in result["components"]["schemas"]
        assert "Nested" in result["components"]["schemas"]
        assert "Unused" not in result["components"]["schemas"]

    def test_empty_portal_paths(self, capsys):
        full_spec = {
            "openapi": "3.1.0",
            "info": {"version": "1.0.0"},
            "paths": {"/v1/customers": {"get": {}}},
            "components": {"schemas": {}},
        }
        result = generate_portal_openapi(full_spec)
        assert result["paths"] == {}
        captured = capsys.readouterr()
        assert "no /portal paths found" in captured.err

    def test_info_fields(self):
        full_spec = {
            "openapi": "3.0.3",
            "info": {"version": "2.5.0"},
            "paths": {"/portal/x": {"get": {}}},
            "components": {"schemas": {}},
        }
        result = generate_portal_openapi(full_spec)
        assert result["info"]["title"] == "BXB Customer Portal API"
        assert result["info"]["version"] == "2.5.0"
        assert result["openapi"] == "3.0.3"
