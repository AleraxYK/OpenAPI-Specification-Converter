"""Generates a Swagger UI-style PDF from an OpenAPI specification (YAML or JSON)."""

import html
import re

import markdown
from weasyprint import HTML

METHOD_ORDER = ["get", "post", "put", "patch", "delete", "options", "head"]

METHOD_COLORS = {
    "get": "#61affe",
    "post": "#49cc90",
    "put": "#fca130",
    "patch": "#50e3c2",
    "delete": "#f93e3e",
    "options": "#0d5aa7",
    "head": "#9012fe",
}


def md_to_html(text):
    if not text:
        return ""
    return markdown.markdown(text, extensions=["fenced_code", "tables"])


def resolve_ref(ref, spec):
    """Resolves a local $ref such as '#/components/schemas/Foo'."""
    node = spec
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def resolve(obj, spec):
    if isinstance(obj, dict) and "$ref" in obj:
        return resolve(resolve_ref(obj["$ref"], spec), spec)
    return obj


def type_label(schema):
    if not isinstance(schema, dict):
        return "any"
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]
    t = schema.get("type")
    if t == "array":
        items = schema.get("items", {})
        return f"array[{type_label(items)}]"
    label = t or "object"
    fmt = schema.get("format")
    if fmt:
        label += f" ({fmt})"
    return label


def render_schema(schema, spec, seen=None, depth=0, max_depth=6):
    """Recursively renders an OpenAPI schema as a nested HTML list."""
    if seen is None:
        seen = set()

    ref_name = None
    if isinstance(schema, dict) and "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        if ref_name in seen or depth >= max_depth:
            return f'<span class="type-ref">{html.escape(ref_name)}</span>'
        seen = seen | {ref_name}
        schema = resolve(schema, spec)

    if not isinstance(schema, dict):
        return ""

    if schema.get("type") == "array" or "items" in schema:
        items = schema.get("items", {})
        inner = render_schema(items, spec, seen, depth + 1, max_depth)
        return f'<span class="type-array">array</span> of ' + inner

    props = schema.get("properties")
    if props:
        required = set(schema.get("required", []))
        rows = []
        for name, prop_schema in props.items():
            resolved_prop = resolve(prop_schema, spec)
            label = type_label(prop_schema)
            req_badge = '<span class="req-badge">required</span>' if name in required else ""
            desc = html.escape(resolved_prop.get("description", "") if isinstance(resolved_prop, dict) else "")
            enum_vals = resolved_prop.get("enum") if isinstance(resolved_prop, dict) else None
            enum_html = f'<div class="enum">enum: {", ".join(html.escape(str(v)) for v in enum_vals)}</div>' if enum_vals else ""
            example = resolved_prop.get("example") if isinstance(resolved_prop, dict) else None
            example_html = f'<div class="example">example: <code>{html.escape(str(example))}</code></div>' if example is not None else ""

            nested = ""
            is_nested_container = isinstance(resolved_prop, dict) and (
                "properties" in resolved_prop
                or (resolved_prop.get("type") == "array" and "properties" in resolve(resolved_prop.get("items", {}), spec) if isinstance(resolve(resolved_prop.get("items", {}), spec), dict) else False)
            )
            if is_nested_container and depth < max_depth:
                nested = f'<div class="nested-schema">{render_schema(prop_schema, spec, seen, depth + 1, max_depth)}</div>'

            desc_html = f'<div class="prop-desc">{desc}</div>' if desc else ""

            rows.append(
                f'<li class="prop-row">'
                f'<span class="prop-name">{html.escape(name)}</span>'
                f'<span class="prop-type">{html.escape(label)}</span>'
                f'{req_badge}'
                f'{desc_html}'
                f'{enum_html}{example_html}{nested}'
                f'</li>'
            )
        return f'<ul class="schema-list">{"".join(rows)}</ul>'

    additional = schema.get("additionalProperties")
    if additional is True:
        return '<span class="type-object">object</span> (free-form key/value)'

    return f'<span class="type-plain">{html.escape(type_label(schema))}</span>'


def render_parameters(parameters, spec):
    if not parameters:
        return ""
    resolved_params = [resolve(p, spec) for p in parameters]
    rows = []
    for p in resolved_params:
        name = html.escape(p.get("name", ""))
        loc = html.escape(p.get("in", ""))
        required = p.get("required", False)
        schema = p.get("schema", {})
        type_str = html.escape(type_label(schema))
        desc = md_to_html(p.get("description", ""))
        req_badge = '<span class="req-badge">required</span>' if required else ""
        rows.append(
            f"<tr><td><code>{name}</code>{req_badge}</td><td>{loc}</td>"
            f"<td>{type_str}</td><td>{desc}</td></tr>"
        )
    return (
        '<table class="params-table"><thead><tr>'
        "<th>Name</th><th>In</th><th>Type</th><th>Description</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def render_request_body(request_body, spec):
    if not request_body:
        return ""
    body = resolve(request_body, spec)
    required = body.get("required", False)
    content = body.get("content", {})
    blocks = []
    for content_type, media in content.items():
        schema = media.get("schema", {})
        req_badge = ' <span class="req-badge">required</span>' if required else ""
        blocks.append(
            f'<div class="content-block">'
            f'<div class="content-type">{html.escape(content_type)}{req_badge}</div>'
            f'{render_schema(schema, spec)}'
            f"</div>"
        )
    return "".join(blocks)


def render_responses(responses, spec):
    if not responses:
        return ""
    rows = []
    for status, resp in responses.items():
        resp = resolve(resp, spec)
        desc = md_to_html(resp.get("description", ""))
        content = resp.get("content", {})
        content_html = ""
        for content_type, media in content.items():
            schema = media.get("schema", {})
            content_html += (
                f'<div class="content-block">'
                f'<div class="content-type">{html.escape(content_type)}</div>'
                f"{render_schema(schema, spec)}"
                f"</div>"
            )
        status_class = "status-2xx" if status.startswith("2") else (
            "status-4xx" if status.startswith("4") else (
                "status-5xx" if status.startswith("5") else "status-other"
            )
        )
        rows.append(
            f'<div class="response-row">'
            f'<span class="status-badge {status_class}">{html.escape(status)}</span>'
            f'<div class="response-body"><div class="response-desc">{desc}</div>{content_html}</div>'
            f"</div>"
        )
    return "".join(rows)


def render_operation(path, method, operation, spec):
    method = method.lower()
    color = METHOD_COLORS.get(method, "#999999")
    summary = html.escape(operation.get("summary", ""))
    description = md_to_html(operation.get("description", ""))
    deprecated = operation.get("deprecated", False)
    deprecated_badge = '<span class="deprecated-badge">DEPRECATED</span>' if deprecated else ""

    parameters_html = render_parameters(operation.get("parameters"), spec)
    request_body_html = render_request_body(operation.get("requestBody"), spec)
    responses_html = render_responses(operation.get("responses"), spec)

    security = operation.get("security")
    security_html = ""
    if security is not None:
        if len(security) == 0:
            security_html = '<div class="security-note">No authentication required</div>'
        else:
            names = []
            for s in security:
                names.extend(s.keys())
            if names:
                security_html = f'<div class="security-note">Authentication: {html.escape(", ".join(names))}</div>'

    sections = ""
    if parameters_html:
        sections += f'<div class="section-title">Parameters</div>{parameters_html}'
    if request_body_html:
        sections += f'<div class="section-title">Request body</div>{request_body_html}'
    if responses_html:
        sections += f'<div class="section-title">Responses</div>{responses_html}'

    return f"""
    <div class="operation">
      <div class="operation-header" style="border-color:{color}">
        <span class="method-badge" style="background:{color}">{method.upper()}</span>
        <span class="operation-path">{html.escape(path)}</span>
        {deprecated_badge}
      </div>
      <div class="operation-body">
        {f'<div class="operation-summary">{summary}</div>' if summary else ''}
        {f'<div class="operation-description">{description}</div>' if description else ''}
        {security_html}
        {sections}
      </div>
    </div>
    """


def group_by_tags(paths, tags_order):
    grouped = {name: [] for name in tags_order}
    grouped.setdefault("Other", [])
    for path, path_item in paths.items():
        shared_params = path_item.get("parameters", [])
        for method in METHOD_ORDER:
            operation = path_item.get(method)
            if not operation:
                continue
            if shared_params:
                operation = dict(operation)
                operation["parameters"] = shared_params + operation.get("parameters", [])
            op_tags = operation.get("tags") or ["Other"]
            for tag in op_tags:
                grouped.setdefault(tag, []).append((path, method, operation))
    return grouped


CSS = """
@page {
    size: A4;
    margin: 2.2cm 1.8cm;
    @bottom-center {
        content: counter(page) " / " counter(pages);
        font-size: 9px;
        color: #888;
    }
}
* { box-sizing: border-box; }
body {
    font-family: "Helvetica Neue", Arial, sans-serif;
    color: #222;
    font-size: 10.5px;
    line-height: 1.5;
}
.cover {
    text-align: center;
    padding-top: 5cm;
}
.cover h1 {
    font-size: 30px;
    color: #1b1b1b;
    margin-bottom: 4px;
}
.cover .version {
    display: inline-block;
    background: #444;
    color: #fff;
    border-radius: 12px;
    padding: 3px 14px;
    font-size: 12px;
    margin-bottom: 24px;
}
.cover .description {
    max-width: 15cm;
    margin: 0 auto;
    text-align: left;
    color: #444;
    font-size: 11px;
}
.cover .servers {
    margin-top: 30px;
    text-align: left;
    max-width: 13cm;
    margin-left: auto;
    margin-right: auto;
}
.cover .servers table { width: 100%; border-collapse: collapse; }
.cover .servers td { padding: 4px 8px; border-bottom: 1px solid #eee; font-size: 10px; }
.page-break { page-break-before: always; }

.tag-section { page-break-before: always; }
.tag-title {
    font-size: 20px;
    color: #1b1b1b;
    border-bottom: 2px solid #ddd;
    padding-bottom: 6px;
    margin-bottom: 4px;
}
.tag-description { color: #666; font-size: 10px; margin-bottom: 16px; }

.operation {
    border: 1px solid #e2e2e2;
    border-radius: 4px;
    margin-bottom: 14px;
    page-break-inside: avoid;
}
.operation-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    background: #fafafa;
    border-left: 5px solid;
    border-bottom: 1px solid #eee;
}
.method-badge {
    color: #fff;
    font-weight: bold;
    font-size: 10px;
    padding: 3px 10px;
    border-radius: 3px;
    min-width: 56px;
    text-align: center;
    display: inline-block;
}
.operation-path {
    font-family: "Courier New", monospace;
    font-size: 11.5px;
    color: #222;
}
.deprecated-badge {
    background: #f93e3e;
    color: #fff;
    font-size: 8px;
    padding: 2px 6px;
    border-radius: 3px;
}
.operation-body { padding: 10px 14px; }
.operation-summary { font-weight: bold; font-size: 12px; margin-bottom: 4px; }
.operation-description { color: #444; font-size: 10px; margin-bottom: 6px; }
.operation-description code, .prop-desc code, .response-desc code { background: #f2f2f2; padding: 1px 4px; border-radius: 2px; font-family: "Courier New", monospace; }
.security-note { font-size: 9px; color: #856404; background: #fff3cd; padding: 4px 8px; border-radius: 3px; margin-bottom: 6px; display: inline-block; }

.section-title {
    font-size: 10.5px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: .03em;
    color: #555;
    margin: 10px 0 4px 0;
    border-bottom: 1px solid #eee;
    padding-bottom: 2px;
}

.params-table { width: 100%; border-collapse: collapse; margin-bottom: 6px; }
.params-table th {
    text-align: left;
    background: #f5f5f5;
    font-size: 9px;
    text-transform: uppercase;
    color: #666;
    padding: 4px 6px;
    border-bottom: 1px solid #ddd;
}
.params-table td {
    padding: 4px 6px;
    border-bottom: 1px solid #f0f0f0;
    font-size: 9.5px;
    vertical-align: top;
}
.params-table code { font-family: "Courier New", monospace; background: #f2f2f2; padding: 1px 4px; border-radius: 2px; }

.req-badge {
    background: #f93e3e;
    color: #fff;
    font-size: 7.5px;
    padding: 1px 5px;
    border-radius: 3px;
    margin-left: 5px;
    vertical-align: middle;
}

.content-block { margin-bottom: 6px; }
.content-type {
    font-family: "Courier New", monospace;
    font-size: 9.5px;
    color: #61affe;
    margin-bottom: 3px;
    font-weight: bold;
}

.schema-list { list-style: none; margin: 0; padding-left: 12px; border-left: 2px solid #eee; }
.prop-row { margin-bottom: 5px; }
.prop-name { font-family: "Courier New", monospace; font-weight: bold; font-size: 10px; color: #333; }
.prop-type { color: #999; font-size: 9px; margin-left: 6px; }
.prop-desc { color: #555; font-size: 9px; margin-top: 1px; }
.enum, .example { color: #666; font-size: 8.5px; margin-top: 1px; }
.enum { color: #a06a00; }
.nested-schema { margin-top: 3px; }
.type-ref { font-family: "Courier New", monospace; color: #61affe; font-size: 9.5px; }
.type-array, .type-object, .type-plain { color: #444; font-size: 9.5px; }

.response-row { display: flex; gap: 10px; margin-bottom: 8px; align-items: flex-start; }
.status-badge {
    font-family: "Courier New", monospace;
    font-weight: bold;
    font-size: 10px;
    padding: 3px 8px;
    border-radius: 3px;
    min-width: 34px;
    text-align: center;
    height: fit-content;
}
.status-2xx { background: #d4edda; color: #1c7c3e; }
.status-4xx { background: #fde2e2; color: #b02a2a; }
.status-5xx { background: #f5c6cb; color: #7a1f1f; }
.status-other { background: #eee; color: #555; }
.response-body { flex: 1; }
.response-desc { font-size: 9.5px; color: #444; margin-bottom: 3px; }

.schemas-section .schema-block {
    border: 1px solid #e2e2e2;
    border-radius: 4px;
    padding: 10px 14px;
    margin-bottom: 12px;
    page-break-inside: avoid;
}
.schemas-section .schema-name {
    font-family: "Courier New", monospace;
    font-size: 12px;
    font-weight: bold;
    color: #333;
    margin-bottom: 6px;
}
"""


def build_html(spec):
    info = spec.get("info", {})
    title = html.escape(info.get("title", "API"))
    version = html.escape(str(info.get("version", "")))
    description = md_to_html(info.get("description", ""))
    servers = spec.get("servers", [])
    tags = spec.get("tags", [])
    tags_order = [t["name"] for t in tags]
    tag_descriptions = {t["name"]: t.get("description", "") for t in tags}

    servers_html = ""
    if servers:
        rows = "".join(
            f"<tr><td><code>{html.escape(s.get('url', ''))}</code></td><td>{html.escape(s.get('description', ''))}</td></tr>"
            for s in servers
        )
        servers_html = f'<div class="servers"><table>{rows}</table></div>'

    cover = f"""
    <div class="cover">
      <h1>{title}</h1>
      <div class="version">v{version}</div>
      <div class="description">{description}</div>
      {servers_html}
    </div>
    """

    grouped = group_by_tags(spec.get("paths", {}), tags_order)

    tag_sections = ""
    for tag_name in tags_order + [t for t in grouped if t not in tags_order and grouped[t]]:
        operations = grouped.get(tag_name, [])
        if not operations:
            continue
        ops_html = "".join(
            render_operation(path, method, op, spec) for path, method, op in operations
        )
        tag_desc = md_to_html(tag_descriptions.get(tag_name, ""))
        tag_sections += f"""
        <div class="tag-section">
          <div class="tag-title">{html.escape(tag_name)}</div>
          {f'<div class="tag-description">{tag_desc}</div>' if tag_desc else ''}
          {ops_html}
        </div>
        """

    schemas = spec.get("components", {}).get("schemas", {})
    schemas_html = ""
    if schemas:
        blocks = "".join(
            f'<div class="schema-block"><div class="schema-name">{html.escape(name)}</div>{render_schema(sch, spec)}</div>'
            for name, sch in schemas.items()
        )
        schemas_html = f"""
        <div class="tag-section schemas-section">
          <div class="tag-title">Schemas</div>
          {blocks}
        </div>
        """

    return f"""<!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><style>{CSS}</style></head>
    <body>
      {cover}
      {tag_sections}
      {schemas_html}
    </body>
    </html>
    """


def generate_pdf(spec, output_path):
    html_content = build_html(spec)
    HTML(string=html_content).write_pdf(output_path)
