from __future__ import annotations

from libscout_parser import extract_cst_chunks, parse_code


def test_extract_cst_chunks_prefers_named_definitions() -> None:
    source = """
class Indexer:
    def inject_repository(self, repo_path: str) -> str:
        return repo_path

def helper() -> int:
    return 7
""".strip()

    parsed = parse_code(source, language="python")
    chunks = extract_cst_chunks(parsed)

    assert chunks
    node_types = {chunk.node_type for chunk in chunks}
    assert "function_definition" in node_types or "class_definition" in node_types
    assert any("inject_repository" in chunk.text for chunk in chunks)
