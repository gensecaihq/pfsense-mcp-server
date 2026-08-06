#!/usr/bin/env python3
"""Generate a slim wire-contract file from the pfSense REST API OpenAPI spec.

The upstream `openapi.json` (a release asset of pfrest/pfSense-pkg-RESTAPI) is
~4 MB. This distills it to just what a payload contract test needs: for every
writable endpoint, the set of valid field names, their JSON types, any enum
choices, and which fields are required on create (POST) vs update (PATCH).

Usage:
    python generate_contract.py openapi.json contract-v2.9.0.json --version v2.9.0
"""
import argparse
import json
import sys


def _resolve_ref(ref, root):
    node = root
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def _field_spec(prop):
    """Distill an OpenAPI property node to {type, items, enum}."""
    spec = {"type": prop.get("type")}
    if "items" in prop and isinstance(prop["items"], dict):
        spec["items"] = prop["items"].get("type")
    if "enum" in prop:
        spec["enum"] = prop["enum"]
    # nullable/anyOf: capture the non-null branch's type if the top-level type is absent
    if spec["type"] is None and "anyOf" in prop:
        types = [b.get("type") for b in prop["anyOf"] if b.get("type") not in (None, "null")]
        if types:
            spec["type"] = types[0]
    return spec


def _merge_schema(schema, root):
    """Resolve $ref/allOf into a flat {properties, required} dict."""
    properties = {}
    required = []
    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], root)
    if "allOf" in schema:
        for sub in schema["allOf"]:
            merged = _merge_schema(sub, root)
            properties.update(merged["properties"])
            required.extend(merged["required"])
        return {"properties": properties, "required": required}
    for name, prop in schema.get("properties", {}).items():
        properties[name] = _field_spec(prop)
    required.extend(schema.get("required", []))
    return {"properties": properties, "required": required}


def _request_schema(operation, root):
    body = operation.get("requestBody", {})
    content = body.get("content", {})
    media = content.get("application/json") or next(iter(content.values()), None)
    if not media or "schema" not in media:
        return None
    return _merge_schema(media["schema"], root)


def build(spec):
    root = spec
    contract = {}
    for path, methods in spec["paths"].items():
        for method in ("post", "patch"):
            if method not in methods:
                continue
            merged = _request_schema(methods[method], root)
            if merged is None:
                continue
            contract[f"{method.upper()} {path}"] = {
                "properties": merged["properties"],
                "required": sorted(set(merged["required"])),
            }
        # GET: model properties are the valid query-filter fields
        if "get" in methods:
            # The GET response schema references the same model; capture its fields
            # from the sibling POST/PATCH if present, else skip (queries validated
            # against the writable contract in practice).
            pass
    return contract


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("openapi")
    ap.add_argument("out")
    ap.add_argument("--version", required=True)
    args = ap.parse_args()
    spec = json.load(open(args.openapi))
    contract = build(spec)
    out = {
        "_meta": {
            "source": "pfrest/pfSense-pkg-RESTAPI openapi.json",
            "pkg_restapi_version": args.version,
            "endpoint_count": len(contract),
        },
        "endpoints": contract,
    }
    json.dump(out, open(args.out, "w"), indent=1, sort_keys=True)
    print(f"wrote {args.out}: {len(contract)} endpoints", file=sys.stderr)


if __name__ == "__main__":
    main()
