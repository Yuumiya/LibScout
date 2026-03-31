# LibScout

A uv workspace for scraping and indexing GitHub library usage, with semantic code search powered by tree-sitter CST embeddings and ChromaDB.

## Roadmap

| Mid March                  | End March                                                     | Mid April                 | End April                                          |
| -------------------------- | ------------------------------------------------------------- | ------------------------- | -------------------------------------------------- |
| Project setup, CI, crawler | Repository injection, tree-sitter integration, CST embeddings | ChromaDB, RAG, MCP server | Web UI, semantic search UX, integration, polishing |

## Project Structure

```
packages/
  scraper/          # libscout-scraper: GitHub scraper service
    src/libscout_scraper/
      __init__.py         # Public API surface
      browser.py          # WebDriver factory (Safari primary, Firefox fallback)
      downloader.py       # GitHub API tarball download & extraction
      github_scraper.py   # GitHubScraper crawl logic
      models.py           # Core data models (CrawlSpec, CrawlResult, RepoRef, FileRef)
    tests/
      test_download_holonomy.py  # Integration tests against WeetHet/holonomy

  parser/           # libscout-parser: tree-sitter CST parser with language detection
    src/libscout_parser/
      __init__.py         # Public API surface
      detector.py         # Language detection from file path/extension
      models.py           # ParseResult, ParseError, UnsupportedLanguageError
      parser.py           # parse_file() and parse_code() entry points

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

### libscout-scraper

| Class / Protocol    | Location            | Purpose                                                                              |
| ------------------- | ------------------- | ------------------------------------------------------------------------------------ |
| `CrawlSpec`         | `models.py`         | Input: platform, search terms, max_repos                                             |
| `CrawlResult`       | `models.py`         | Output: matched repos + errors                                                       |
| `RepoRef`           | `models.py`         | A discovered repository with optional local checkout dir, WebDriver, and traverser   |
| `FileRef`           | `models.py`         | A file within a repo; reads from local dir or exposes `.raw_url` and `.fetch_text()` |
| `ContentFetcher`    | `models.py`         | Protocol: `(url: str) -> str` (legacy remote-fetch fallback)                         |
| `FileTraverser`     | `models.py`         | Protocol: `(driver, repo) -> Iterator[FileRef]` (legacy traversal fallback)          |
| `DownloadResult`    | `downloader.py`     | Result of downloading a repo: owner, name, local_dir, default_branch                 |
| `RepoDownloadError` | `downloader.py`     | Exception raised on download/extraction failure                                      |
| `download_repo`     | `downloader.py`     | Downloads a GitHub repo tarball via API and extracts to a local directory            |
| `GitHubScraper`     | `github_scraper.py` | Drives a WebDriver to search GitHub, downloads repos via API, returns `CrawlResult`  |
| `BrowserConfig`     | `browser.py`        | Config for headless mode, implicit wait, user-agent                                  |
| `create_webdriver`  | `browser.py`        | Factory: tries Safari on macOS, falls back to Firefox                                |

### libscout-parser

| Class / Function           | Location      | Purpose                                                                    |
| -------------------------- | ------------- | -------------------------------------------------------------------------- |
| `ParseResult`              | `models.py`   | Holds source path, detected language, tree-sitter `Tree`, and source bytes |
| `ParseError`               | `models.py`   | Base exception for parsing failures                                        |
| `UnsupportedLanguageError` | `models.py`   | Raised when language cannot be detected or is not supported by tree-sitter |
| `detect_language`          | `detector.py` | Detects programming language from a file path/extension                    |
| `is_language_supported`    | `detector.py` | Checks whether a language name has a tree-sitter grammar available         |
| `parse_file`               | `parser.py`   | Reads a file from disk, auto-detects language, and returns a `ParseResult` |
| `parse_code`               | `parser.py`   | Parses source code bytes/string with an explicitly specified language      |

## Parsing Flow

1. `parse_file(path)` reads source bytes from disk.
2. If no language is specified, `detect_language(path)` uses `tree-sitter-language-pack` to identify the language from the file extension.
3. `get_parser(language)` obtains a pre-configured tree-sitter parser (grammars are downloaded on demand).
4. `parser.parse(source_bytes)` produces a concrete syntax tree (`tree_sitter.Tree`).
5. The result is returned as a `ParseResult` with `.root_node`, `.s_expression`, and the raw `.source` bytes.

`parse_code(source, language=...)` follows steps 3–5 for inline source code with an explicit language.

## Repo Download Flow

1. `GitHubScraper.crawl()` uses Selenium to search GitHub and extract repo owner/name slugs.
2. For each discovered repo, `download_repo()` calls the GitHub API (`/repos/{owner}/{name}/tarball`) to fetch the tarball.
3. The tarball is extracted into a temporary directory; `RepoRef.local_dir` points to the extracted tree.
4. `RepoRef.iter_files()` walks the local directory, yielding `FileRef` objects for every file.
5. `FileRef.fetch_text()` reads directly from the local filesystem when `local_dir` is set.

Authentication is via an optional `github_token` parameter or the `GITHUB_TOKEN` environment variable.

## Dependencies

### libscout-scraper

- `selenium` — browser automation for GitHub search page scraping
- `httpx` — HTTP client for GitHub API tarball downloads
- `fastapi` + `uvicorn` — API service layer
- `python-dotenv` — environment config

### libscout-parser

- `tree-sitter` — Python bindings for the tree-sitter incremental parsing library
- `tree-sitter-language-pack` — pre-compiled tree-sitter grammars for 248 languages with language detection
