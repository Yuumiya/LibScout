from __future__ import annotations

import re
from collections.abc import Iterator

from tree_sitter import Node

from .models import CSTChunk, ParseResult

_PREFERRED_NODE_TYPES = {
    "arrow_function",
    "class_declaration",
    "class_definition",
    "enum_declaration",
    "export_statement",
    "function_declaration",
    "function_definition",
    "interface_declaration",
    "lexical_declaration",
    "method_declaration",
    "method_definition",
    "pair",
    "struct_item",
    "trait_item",
    "type_declaration",
    "variable_declaration",
}

_SYMBOL_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)")
_IDENTIFIER_TYPES = {
    "attribute",
    "field_identifier",
    "identifier",
    "property_identifier",
    "shorthand_property_identifier",
    "type_identifier",
}
_CALL_NODE_TYPES = {"call", "call_expression"}
_FUNCTION_FIELD_NODE_TYPES = {
    "attribute",
    "identifier",
    "member_expression",
    "property_identifier",
    "scoped_identifier",
}
_IMPORT_NODE_TYPES = {
    "import",
    "import_clause",
    "import_declaration",
    "import_from_statement",
    "import_specifier",
    "import_statement",
    "namespace_import",
}


def extract_cst_chunks(parse_result: ParseResult, *, max_chars: int = 1600, min_chars: int = 60) -> tuple[CSTChunk, ...]:
    """Extract CST-guided chunks from a parsed source file."""
    source = parse_result.source
    root = parse_result.root_node
    chunks: list[CSTChunk] = []
    seen_spans: set[tuple[int, int]] = set()
    module_imports = _collect_imports(root, source)

    for node in _iter_named_nodes(root):
        node_type = _node_type(node)
        if node_type not in _PREFERRED_NODE_TYPES:
            continue
        text = source[_start_byte(node) : _end_byte(node)].decode("utf-8", errors="replace").strip()
        if len(text) < min_chars or len(text) > max_chars:
            continue
        span = (_start_byte(node), _end_byte(node))
        if span in seen_spans:
            continue
        seen_spans.add(span)
        chunks.append(_build_chunk(parse_result, node, text, module_imports=module_imports))

    if chunks:
        return tuple(chunks)

    fallback_text = source.decode("utf-8", errors="replace")
    if not fallback_text.strip():
        return ()

    lines = fallback_text.splitlines()
    window = 40
    fallback_chunks: list[CSTChunk] = []
    for start in range(0, len(lines), window):
        selected = lines[start : start + window]
        text = "\n".join(selected).strip()
        if len(text) < min_chars:
            continue
        fallback_chunks.append(
            CSTChunk(
                source_path=parse_result.source_path,
                language=parse_result.language,
                node_type="file_window",
                start_byte=0,
                end_byte=len(source),
                start_line=start + 1,
                end_line=min(len(lines), start + window),
                text=text,
                cst_path=parse_result.root_node.type,
                symbol=None,
                scope_type="module",
                identifiers=_collect_identifiers(root, source),
                calls=_collect_calls(root, source),
                imports=module_imports,
            )
        )
    return tuple(fallback_chunks)


def _iter_named_nodes(node: Node) -> Iterator[Node]:
    yield node
    for child in _children(node):
        if _is_named(child):
            yield from _iter_named_nodes(child)


def _build_chunk(parse_result: ParseResult, node: Node, text: str, *, module_imports: tuple[str, ...]) -> CSTChunk:
    cst_path = _build_cst_path(node)
    symbol = _extract_symbol(node, text, parse_result.source)
    imports = _merge_unique(module_imports, _collect_imports(node, parse_result.source))
    return CSTChunk(
        source_path=parse_result.source_path,
        language=parse_result.language,
        node_type=_node_type(node),
        start_byte=_start_byte(node),
        end_byte=_end_byte(node),
        start_line=_point_row(_start_position(node)) + 1,
        end_line=_point_row(_end_position(node)) + 1,
        text=text,
        cst_path=cst_path,
        symbol=symbol,
        scope_type=_normalize_scope_type(parse_result.language, _node_type(node)),
        identifiers=_collect_identifiers(node, parse_result.source),
        calls=_collect_calls(node, parse_result.source),
        imports=imports,
    )


def _build_cst_path(node: Node) -> str:
    types: list[str] = []
    current: Node | None = node
    while current is not None:
        types.append(_node_type(current))
        current = _parent(current)
    return " > ".join(reversed(types))


def _extract_symbol(node: Node, text: str, source: bytes) -> str | None:
    named_child = _child_by_field_name(node, "name")
    if named_child is not None:
        symbol = _node_text(named_child, source).strip()
        if symbol:
            return symbol

    for child in _children(node):
        if not _is_named(child):
            continue
        child_type = _node_type(child)
        if child_type in _IDENTIFIER_TYPES:
            symbol = _node_text(child, source).strip()
            if symbol:
                return symbol
        nested = _extract_symbol(child, "", source)
        if nested:
            return nested
        # Avoid wandering too far into function bodies when looking for the declaration symbol.
        if child_type in {"block", "statement_block", "class_body"}:
            break

    first_line = text.splitlines()[0] if text else _node_type(node)
    symbol_match = _SYMBOL_RE.search(first_line)
    return symbol_match.group(1) if symbol_match else None


def _collect_identifiers(node: Node, source: bytes) -> tuple[str, ...]:
    identifiers: list[str] = []
    seen: set[str] = set()
    for child in _iter_named_nodes(node):
        if _node_type(child) not in _IDENTIFIER_TYPES:
            continue
        text = _node_text(child, source).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        identifiers.append(text)
    return tuple(identifiers)


def _collect_calls(node: Node, source: bytes) -> tuple[str, ...]:
    calls: list[str] = []
    seen: set[str] = set()
    for child in _iter_named_nodes(node):
        if _node_type(child) not in _CALL_NODE_TYPES:
            continue
        call_target = _extract_call_target(child, source)
        if not call_target or call_target in seen:
            continue
        seen.add(call_target)
        calls.append(call_target)
    return tuple(calls)


def _collect_imports(node: Node, source: bytes) -> tuple[str, ...]:
    imports: list[str] = []
    seen: set[str] = set()
    for child in _iter_named_nodes(node):
        child_type = _node_type(child)
        if child_type not in _IMPORT_NODE_TYPES and "import" not in child_type:
            continue
        text = _node_text(child, source).strip()
        if not text:
            continue
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_\.]*", text):
            if token in {"import", "from", "as"} or token in seen:
                continue
            seen.add(token)
            imports.append(token)
    return tuple(imports)


def _extract_call_target(node: Node, source: bytes) -> str | None:
    function_node = _child_by_field_name(node, "function")
    if function_node is not None and _node_type(function_node) in _FUNCTION_FIELD_NODE_TYPES:
        target = _node_text(function_node, source).strip()
        if target:
            return target

    for child in _children(node):
        if not _is_named(child):
            continue
        child_type = _node_type(child)
        if child_type in _IDENTIFIER_TYPES:
            return _node_text(child, source).strip()
        if child_type in {"member_expression", "attribute", "scoped_identifier"}:
            text = _node_text(child, source).strip()
            if text:
                return text
        nested = _extract_call_target(child, source)
        if nested:
            return nested
    return None


def _merge_unique(*groups: tuple[str, ...]) -> tuple[str, ...]:
    values: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            if value in seen:
                continue
            seen.add(value)
            values.append(value)
    return tuple(values)


def _node_type(node: Node) -> str:
    node_type = getattr(node, "type", None)
    if isinstance(node_type, str):
        return node_type
    kind = getattr(node, "kind", None)
    if callable(kind):
        return str(kind())
    return str(node_type or "")


def _children(node: Node) -> tuple[Node, ...]:
    children = getattr(node, "children", None)
    if children is not None:
        return tuple(children)
    child_count = getattr(node, "child_count", None)
    child = getattr(node, "child", None)
    if callable(child_count) and callable(child):
        return tuple(child(index) for index in range(int(child_count())))
    return ()


def _is_named(node: Node) -> bool:
    is_named = getattr(node, "is_named", None)
    return bool(is_named() if callable(is_named) else is_named)


def _node_text(node: Node, source: bytes) -> str:
    text = getattr(node, "text", None)
    if isinstance(text, bytes):
        return text.decode("utf-8", errors="replace")
    if isinstance(text, str):
        return text
    return source[_start_byte(node) : _end_byte(node)].decode("utf-8", errors="replace")


def _start_byte(node: Node) -> int:
    value = getattr(node, "start_byte", None)
    return int(value() if callable(value) else value)


def _end_byte(node: Node) -> int:
    value = getattr(node, "end_byte", None)
    return int(value() if callable(value) else value)


def _start_position(node: Node) -> object:
    value = getattr(node, "start_point", None)
    if value is not None:
        return value
    start_position = getattr(node, "start_position", None)
    return start_position() if callable(start_position) else start_position


def _end_position(node: Node) -> object:
    value = getattr(node, "end_point", None)
    if value is not None:
        return value
    end_position = getattr(node, "end_position", None)
    return end_position() if callable(end_position) else end_position


def _point_row(point: object) -> int:
    if isinstance(point, tuple):
        return int(point[0])
    return int(getattr(point, "row", 0))


def _parent(node: Node) -> Node | None:
    parent = getattr(node, "parent", None)
    return parent() if callable(parent) else parent


def _child_by_field_name(node: Node, field_name: str) -> Node | None:
    child_by_field_name = getattr(node, "child_by_field_name", None)
    return child_by_field_name(field_name) if callable(child_by_field_name) else None


def _normalize_scope_type(language: str, node_type: str) -> str:
    if node_type in {"class_declaration", "class_definition"}:
        return "class"
    if node_type in {"function_declaration", "function_definition", "method_declaration", "method_definition"}:
        return "function"
    if language in {"typescript", "tsx", "javascript", "jsx"} and node_type in {
        "arrow_function",
        "lexical_declaration",
        "variable_declaration",
    }:
        return "function"
    return node_type
