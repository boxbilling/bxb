"""Generate OpenAPI schema from the FastAPI app.

Works around a bug in FastAPI 0.121.x where _remap_definitions_and_field_mappings
crashes on field_mapping entries that don't contain a $ref key (e.g. inline
primitive/enum schemas).
"""

import json

from fastapi._compat import v2 as fastapi_v2


_original_remap = fastapi_v2._remap_definitions_and_field_mappings


def _patched_remap(
    *, model_name_map, definitions, field_mapping  # type: ignore[no-untyped-def]
):  # type: ignore[no-untyped-def]
    old_name_to_new_name_map: dict[str, str] = {}
    for field_key, schema in field_mapping.items():
        model = field_key[0].type_
        if model not in model_name_map:
            continue
        new_name = model_name_map[model]
        if "$ref" not in schema:
            continue
        old_name = schema["$ref"].split("/")[-1]
        if old_name in {f"{new_name}-Input", f"{new_name}-Output"}:
            continue
        old_name_to_new_name_map[old_name] = new_name

    new_field_mapping = {}
    for field_key, schema in field_mapping.items():
        new_schema = fastapi_v2._replace_refs(
            schema=schema,
            old_name_to_new_name_map=old_name_to_new_name_map,
        )
        new_field_mapping[field_key] = new_schema

    new_definitions = {}
    for key, value in definitions.items():
        new_key = old_name_to_new_name_map.get(key, key)
        new_value = fastapi_v2._replace_refs(
            schema=value,
            old_name_to_new_name_map=old_name_to_new_name_map,
        )
        new_definitions[new_key] = new_value
    return new_field_mapping, new_definitions


fastapi_v2._remap_definitions_and_field_mappings = _patched_remap  # type: ignore[assignment]

from app.main import app  # noqa: E402

if __name__ == "__main__":
    print(json.dumps(app.openapi()))
