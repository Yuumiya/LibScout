# LibScout

A uv workspace for scraping and indexing GitHub library usage, with semantic code search powered by tree-sitter CST embeddings and ChromaDB.

## Roadmap

| Mid March | End March | Mid April | End April |
|-----------|-----------|-----------|-----------|
| Project setup, CI, crawler | Repository injection, tree-sitter integration, CST embeddings | ChromaDB, RAG, MCP server | Web UI, semantic search UX, integration, polishing |

## Project Structure

```
packages/
  scraper/          # libscout-scraper: GitHub scraper service
    src/libscout_scraper/
      __init__.py         # Public API surface
      browser.py          # WebDriver factory (Safari primary, Firefox fallback)
      github_scraper.py   # GitHubScraper crawl logic
      models.py           # Core data models (CrawlSpec, CrawlResult, RepoRef, FileRef)

npins/                    # Nix pin management (npins)
  default.nix             # Pin loader (do not edit; managed by npins)
  sources.json            # Pinned nixpkgs revision

project.nix               # Nix shell definition (python3 + uv)
shell.nix                 # Entry point: `import ./project.nix { }).shell`
pyproject.toml            # uv workspace root; ruff + basedpyright config
```

## Environment Setup

### Nix (recommended)

The project ships a Nix shell that provides `python3` and `uv`. Nixpkgs is pinned via [npins](https://github.com/andir/npins).

```bash
nix-shell          # enter dev shell (python3 + uv)
npins update       # update nixpkgs pin
```

To override a pin locally, set `NPINS_OVERRIDE_<NAME>` to an absolute or relative path.

### Without Nix

Ensure Python 3.11+ and [uv](https://docs.astral.sh/uv/) are available, then:

```bash
uv sync            # create .venv and install all dependencies
```

## Development

```bash
uv run pytest               # run tests
uv run ruff check .         # lint
uv run ruff format .        # format
uv run basedpyright         # type check
```

## Key Conventions

- Python 3.11+, all files start with `from __future__ import annotations`
- Type checking: basedpyright in `recommended` mode
- Linting/formatting: ruff (line length 120, preview mode)
- Tests: pytest with pytest-asyncio
- Frozen dataclasses for immutable models (`@dataclass(frozen=True)`)
- Protocols for injectable behaviours (`ContentFetcher`, `FileTraverser`)
- No `__all__` management beyond what is in `__init__.py`

## Core Abstractions

| Class / Protocol | Location | Purpose |
|------------------|----------|---------|
| `CrawlSpec` | `models.py` | Input: platform, search terms, max_repos |
| `CrawlResult` | `models.py` | Output: matched repos + errors |
| `RepoRef` | `models.py` | A discovered repository with its WebDriver and optional traverser |
| `FileRef` | `models.py` | A file within a repo; exposes `.raw_url` and `.fetch_text()` |
| `ContentFetcher` | `models.py` | Protocol: `(url: str) -> str` |
| `FileTraverser` | `models.py` | Protocol: `(driver, repo) -> Iterator[FileRef]` |
| `GitHubScraper` | `github_scraper.py` | Drives a WebDriver to search GitHub and return `CrawlResult` |
| `BrowserConfig` | `browser.py` | Config for headless mode, implicit wait, user-agent |
| `create_webdriver` | `browser.py` | Factory: tries Safari on macOS, falls back to Firefox |

## Dependencies

- `selenium` — browser automation for GitHub scraping
- `httpx` — async HTTP client
- `fastapi` + `uvicorn` — API service layer
- `python-dotenv` — environment config
