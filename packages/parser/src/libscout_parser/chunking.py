from __future__ import annotations

import re
from collections.abc import Iterator

from tree_sitter import Node

from .models import CSTChunk, ParseResult

_PREFERRED_NODE_TYPES = {
    "class_declaration",
    "class_definition",
    "enum_declaration",
    "function_declaration",
    "function_definition",
    "interface_declaration",
    "method_declaration",
    "method_definition",
    "struct_item",
    "trait_item",
    "type_declaration",
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
_IMPORT_NODE_TYPES = {
    "import_clause",
    "import_from_statement",
    "import_specifier",
    "import_statement",
}


def extract_cst_chunks(parse_result: ParseResult, *, max_chars: int = 1600, min_chars: int = 60) -> tuple[CSTChunk, ...]:
    """Extract CST-guided chunks from a parsed source file."""
    source = parse_result.source
    root = parse_result.root_node
    chunks: list[CSTChunk] = []
    seen_spans: set[tuple[int, int]] = set()

    for node in _iter_named_nodes(root):
        if node.type not in _PREFERRED_NODE_TYPES:
            continue
        text = source[node.start_byte : node.end_byte].decode("utf-8", errors="replace").strip()
        if len(text) < min_chars or len(text) > max_chars:
            continue
        span = (node.start_byte, node.end_byte)
        if span in seen_spans:
            continue
        seen_spans.add(span)
        chunks.append(_build_chunk(parse_result, node, text))

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
            )
        )
    return tuple(fallback_chunks)


def _iter_named_nodes(node: Node) -> Iterator[Node]:
    yield node
    for child in node.children:
        if child.is_named:
            yield from _iter_named_nodes(child)


def _build_chunk(parse_result: ParseResult, node: Node, text: str) -> CSTChunk:
    cst_path = _build_cst_path(node)
    symbol = _extract_symbol(node, text)
    return CSTChunk(
        source_path=parse_result.source_path,
        language=parse_result.language,
        node_type=node.type,
        start_byte=node.start_byte,
        end_byte=node.end_byte,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        text=text,
        cst_path=cst_path,
        symbol=symbol,
        scope_type=node.type,
        identifiers=_collect_identifiers(node),
        calls=_collect_calls(node),
        imports=_collect_imports(node),
    )


def _build_cst_path(node: Node) -> str:
    types: list[str] = []
    current: Node | None = node
    while current is not None:
        types.append(current.type)
        current = current.parent
    return " > ".join(reversed(types))


def _extract_symbol(node: Node, text: str) -> str | None:
    for child in node.children:
        if not child.is_named:
            continue
        if child.type in _IDENTIFIER_TYPES:
            symbol = child.text.decode("utf-8", errors="replace").strip()
            if symbol:
                return symbol
        nested = _extract_symbol(child, "")
        if nested:
            return nested
        # Avoid wandering too far into function bodies when looking for the declaration symbol.
        if child.type in {"block", "statement_block", "class_body"}:
            break

    first_line = text.splitlines()[0] if text else node.type
    symbol_match = _SYMBOL_RE.search(first_line)
    return symbol_match.group(1) if symbol_match else None


def _collect_identifiers(node: Node) -> tuple[str, ...]:
    identifiers: list[str] = []
    seen: set[str] = set()
    for child in _iter_named_nodes(node):
        if child.type not in _IDENTIFIER_TYPES:
            continue
        text = child.text.decode("utf-8", errors="replace").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        identifiers.append(text)
    return tuple(identifiers)


def _collect_calls(node: Node) -> tuple[str, ...]:
    calls: list[str] = []
    seen: set[str] = set()
    for child in _iter_named_nodes(node):
        if child.type not in _CALL_NODE_TYPES:
            continue
        call_target = _extract_call_target(child)
        if not call_target or call_target in seen:
            continue
        seen.add(call_target)
        calls.append(call_target)
    return tuple(calls)


def _collect_imports(node: Node) -> tuple[str, ...]:
    imports: list[str] = []
    seen: set[str] = set()
    for child in _iter_named_nodes(node):
        if child.type not in _IMPORT_NODE_TYPES and "import" not in child.type:
            continue
        text = child.text.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_\.]*", text):
            if token in {"import", "from", "as"} or token in seen:
                continue
            seen.add(token)
            imports.append(token)
    return tuple(imports)


def _extract_call_target(node: Node) -> str | None:
    for child in node.children:
        if not child.is_named:
            continue
        if child.type in _IDENTIFIER_TYPES:
            return child.text.decode("utf-8", errors="replace").strip()
        if child.type in {"member_expression", "attribute", "scoped_identifier"}:
            text = child.text.decode("utf-8", errors="replace").strip()
            if text:
                return text
        nested = _extract_call_target(child)
        if nested:
            return nested
    return None
