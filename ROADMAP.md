# Roadmap

## Goal

Make LibScout the best way to search how small, fast-moving libraries are actually used, with tree-sitter as the core retrieval primitive.

## Phase 1: Foundations

- Set up the uv workspace and Python package layout
- Add GitHub repo download support
- Establish parser package with tree-sitter language detection and CST parsing
- Put test, lint, and type-checking workflows in place

## Phase 2: Structural Indexing

- Introduce repository injection for local and GitHub repositories
- Extract syntax-aware CST chunks instead of naive line windows
- Capture structural metadata:
  - symbol names
  - identifiers
  - call targets
  - imports
  - node/scope types
  - CST ancestry paths
- Persist structural rows alongside vector records

## Phase 3: Search and Retrieval

- Add ChromaDB-backed storage
- Add search API endpoints
- Make structural retrieval primary:
  - exact symbol lookup
  - call/import matching
  - scope-aware ranking
- Keep vector search as a secondary support signal
- Add self-healing behavior around index rebuilds and Chroma instability

## Phase 4: UX and Integration

- Build a search-first React web interface with shadcn/ui
- Keep ingestion and config out of the main search experience
- Add Docker Compose for API + web deployment
- Add curated repo seeding without depending on the live scraper path

## Phase 5: Next Steps

- Implement the MCP server in `apps/mcp`
- Add explicit symbol/call/import filters in the UI
- Add language-specific tree-sitter query patterns
- Add snippet expansion to enclosing function/class/module context
- Add real LLM-backed best-practice summarization instead of placeholder synthesis

## Suggested 10-Week Breakdown

### Weeks 1-2

- workspace setup
- scraper and downloader
- parser bootstrap

### Weeks 3-4

- repository injection
- CST chunk extraction
- structural metadata capture

### Weeks 5-6

- Chroma integration
- structural search ranking
- backend API endpoints

### Weeks 7-8

- web UI
- dockerization
- curated seed flow

### Weeks 9-10

- MCP server
- search quality tuning
- polish and demo hardening
