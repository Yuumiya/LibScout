# LibScout

Bridging the “Knowledge Gap” for niche and next-gen libraries.

LibScout indexes real repositories with tree-sitter, stores syntax-aware chunks, and searches library usage by structure first:

- symbols, for example `symbol:parse_file`
- call sites, for example `call:httpx.get`
- imports, for example `import:fastapi`
- scopes, for example `scope:function`, `scope:class`, or `scope:module`
- languages, for example `language:python` or `language:typescript`

## Workflow

1. Start the API:

```bash
uv run python scripts/run_api.py
```

2. Inject and index a local repository:

```bash
curl -X POST http://localhost:8000/api/repositories/inject \
  -H 'Content-Type: application/json' \
  -d '{"source":"local","path":"/path/to/repo","owner":"local","name":"demo","index_now":true}'
```

3. Search usage from the web UI or API:

```bash
curl -X POST http://localhost:8000/api/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"import:httpx call:httpx.get scope:function","limit":5}'
```

4. Use the MCP-compatible usage endpoint from agents:

```bash
curl -X POST http://localhost:8000/mcp/search_usage \
  -H 'Content-Type: application/json' \
  -d '{"query":"symbol:fetch_user call:httpx.get","limit":5,"enable_sampling":true}'
```

The MCP endpoint returns search hits, a deterministic fallback best-practices brief, and a `sampling_request` using `sampling/createMessage` when retrieved snippets are available. MCP clients that support sampling can submit that prompt to their model and replace the fallback answer with the sampled summary.

## Testing

Run the Python suite:

```bash
source .venv/bin/activate
python -m pytest
```

Run the Playwright integration suite:

```bash
npm install
cd apps/web
npx playwright install chromium
npm run test:e2e
```

The Playwright config starts a deterministic fixture API on port `8123` and the Vite UI on port `5173`. It covers interface rendering, repository scoping, search modes, ranking assertions, RAG summaries, MCP sampling output, syntax metadata, highlighted snippets, and empty/error/loading states.

## Current Limitations

- Python and TypeScript have the most tuned structural extraction; other tree-sitter languages use generic node traversal.
- Vector search is a fallback/support signal. Exact structural filters intentionally dominate ranking.
- MCP sampling is exposed as a request payload because this HTTP endpoint cannot force a host client to run sampling.
- Snippet highlighting is lightweight and dependency-free; it is not a full grammar highlighter.
