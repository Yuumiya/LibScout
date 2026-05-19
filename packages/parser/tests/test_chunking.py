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


def test_python_chunks_include_module_imports_and_full_call_targets() -> None:
    source = """
import httpx

def fetch_user(user_id: str) -> dict:
    response = httpx.get(f"https://example.test/users/{user_id}")
    return response.json()
""".strip()

    parsed = parse_code(source, language="python")
    chunks = extract_cst_chunks(parsed)
    fetch_chunk = next(chunk for chunk in chunks if chunk.symbol == "fetch_user")

    assert fetch_chunk.scope_type == "function"
    assert "httpx" in fetch_chunk.imports
    assert "httpx.get" in fetch_chunk.calls
    assert "response.json" in fetch_chunk.calls


def test_typescript_chunks_capture_named_exports_and_imports() -> None:
    source = """
import { request } from "./client"

export async function loadUser(userId: string) {
  const response = await request(`/users/${userId}`)
  return response.json()
}
""".strip()

    parsed = parse_code(source, language="typescript")
    chunks = extract_cst_chunks(parsed)

    assert any(chunk.symbol == "loadUser" for chunk in chunks)
    assert any("request" in chunk.imports for chunk in chunks)
    assert any("request" in chunk.calls for chunk in chunks)
