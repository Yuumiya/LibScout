# LibScout

A uv workspace for scraping, structurally indexing, and searching GitHub library usage with tree-sitter-first retrieval, ChromaDB storage, and a React web interface.

## Product Direction

LibScout is not intended to be a generic semantic code search engine. The differentiator is tree-sitter:

- index real public-library usage from repositories
- extract syntax-aware snippets at function/class scope
- capture structural metadata such as symbols, calls, imports, node types, and CST ancestry
- retrieve results using tree-sitter-derived structure first
- use vector search only as a secondary support signal

The human web app is search-first. Repository ingestion, seeding, and maintenance exist in the backend and scripts, not as primary user-facing UI.

## Current Roadmap Snapshot

| Mid March                  | End March                                                     | Mid April                         | End April / Early May                                 |
| -------------------------- | ------------------------------------------------------------- | --------------------------------- | ----------------------------------------------------- |
| Project setup, CI, crawler | Repository injection, tree-sitter integration, CST indexing   | ChromaDB, structural search, RAG  | Web UI, Docker Compose, integration, search polishing |

## Project Structure

```text
apps/
  mcp/                # Workspace metadata for MCP integration
  web/                # React + Vite + shadcn/ui search interface

packages/
  scraper/            # libscout-scraper: GitHub discovery and repo download
    src/libscout_scraper/
      __init__.py
      browser.py
      downloader.py
      github_scraper.py
      models.py
    tests/

  parser/             # libscout-parser: tree-sitter parsing and CST chunk extraction
    src/libscout_parser/
      __init__.py
      chunking.py
      detector.py
      models.py
      parser.py
    tests/

  indexer/            # libscout-index: indexing, structural search, RAG API
    src/libscout_index/
      __init__.py
      api.py
      embeddings.py
      models.py
      registry.py
      seeds.py
      service.py
    tests/

scripts/
  reindex_all.py
  run_api.py
  run_crawl.py
  seed_repositories.py

docker/
  nginx.conf

Dockerfile.api
Dockerfile.web
docker-compose.yml
```

## Environment Setup

### Nix

```bash
nix-shell
npins update
```

### Without Nix

Ensure Python 3.11+ and `uv` are available:

```bash
uv sync
```

For the web app, Docker is the supported path in this repo. Local Node/Yarn usage is optional.

## Development

### Python

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run basedpyright
```

### Playwright

```bash
npm install
cd apps/web
npx playwright install chromium
npm run test:e2e
```

The e2e suite starts its own fixture API and Vite server. It does not require a pre-existing `.libscout` index.

### API

```bash
uv run python scripts/run_api.py
```

### Docker Compose

```bash
docker compose up -d api web
docker compose --profile seed run --rm seed
```

## Key Conventions

- Python 3.11+, all files start with `from __future__ import annotations`
- basedpyright in `recommended` mode
- ruff for linting and formatting
- frozen dataclasses for immutable models
- tree-sitter-derived chunk structure is preferred over naive text chunking
- web UI is search-first and intentionally low-distraction
- commit style follows conventional commits, e.g. `feat(indexer): ...`

## Core Abstractions

### libscout-parser

| Abstraction                  | Location       | Purpose |
| --------------------------- | -------------- | ------- |
| `ParseResult`               | `models.py`    | Parsed file result with source bytes and tree-sitter `Tree` |
| `CSTChunk`                  | `models.py`    | Tree-sitter-derived snippet with symbol/call/import metadata |
| `detect_language`           | `detector.py`  | Language detection from file path |
| `parse_file` / `parse_code` | `parser.py`    | Tree-sitter parse entrypoints |
| `extract_cst_chunks`        | `chunking.py`  | Extracts syntax-aware chunks from named CST nodes |

### libscout-index

| Abstraction             | Location      | Purpose |
| ---------------------- | ------------- | ------- |
| `InjectedRepository`   | `models.py`   | Repo registry entry for local/GitHub repositories |
| `SearchHit`            | `models.py`   | Search result including structural metadata |
| `LibScoutService`      | `service.py`  | Injection, indexing, structural search, and RAG |
| `create_app()`         | `api.py`      | FastAPI app factory |
| `DEFAULT_GITHUB_REPO_SEEDS` | `seeds.py` | Curated repo seed list for non-scraper ingestion |

## Tree-Sitter Flow

1. A repository is downloaded or injected locally.
2. Each source file is parsed with `parse_file(...)`.
3. `extract_cst_chunks(...)` walks the CST and extracts function/class-scale chunks.
4. Each chunk captures:
   - declaration symbol
   - identifiers
   - calls
   - imports
   - node type / scope type
   - CST ancestry path
5. The indexer stores both:
   - vector records in ChromaDB
   - structural cache rows on disk for tree-sitter-first retrieval
6. Search prefers structural matches and falls back to vector support when useful.

## Search Behavior

The intended search order is:

1. exact symbol / call / import matches
2. structural scope-aware matches
3. lexical overlap on CST-derived metadata
4. vector similarity as a secondary reranking/support signal

This means queries like `detect_language`, `parse_file`, or `typer.Option` should be resolved primarily through tree-sitter-derived structure rather than generic semantic similarity.

Explicit structural query tags are supported:

```text
symbol:parse_file
call:httpx.get
import:fastapi
scope:function
language:python
```

The same fields are also accepted by `/api/search` and `/mcp/search_usage` as JSON properties. `scope` currently normalizes function, method, class, module/file, and raw tree-sitter node names.

## MCP Usage

`POST /mcp/search_usage` is the agent-facing usage search endpoint. It returns:

- `hits`: syntax-aware search hits with symbol, language, file path, line range, calls, and imports
- `answer`: deterministic fallback best-practices brief
- `content`: MCP-style text content for clients that expect tool-like output
- `sampling_request`: an MCP `sampling/createMessage` payload when `enable_sampling` is true and hits exist

The server prepares the sampling prompt but does not call an LLM directly; MCP hosts decide whether to execute sampling.

## Repo Download Flow

1. GitHub repositories can be discovered with the scraper or seeded from a curated list.
2. `download_repo()` fetches tarballs via the GitHub API.
3. Extracted repositories are stored under `.libscout/repos/`.
4. The indexer walks files via `RepoRef.iter_files()`.
5. Indexed metadata is persisted in:
   - `.libscout/repositories.json`
   - `.libscout/chroma/`
   - `.libscout/chunk_cache/`

## Known Gaps

- Python and TypeScript have first-pass language-specific tuning; other languages still use generic CST traversal
- MCP sampling is prepared as a host-executed prompt, not a server-side LLM call
- snippet expansion beyond the indexed function/class/module chunk is not implemented yet
- syntax highlighting is lightweight and not a replacement for grammar-level highlighting
