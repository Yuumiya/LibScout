import { Search } from "lucide-react"
import { startTransition, useEffect, useMemo, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CodeSnippet } from "@/components/CodeSnippet"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import { fetchRepositories, search } from "@/lib/api"
import type { Repository, SearchHit } from "@/types"

const SEARCH_EXAMPLES = [
  {
    label: "Pydantic fields",
    query: "import:pydantic call:Field scope:class",
    description: "models that configure fields on class definitions",
  },
  {
    label: "Typer options",
    query: "call:typer.Option scope:function",
    description: "CLI callbacks that declare options",
  },
  {
    label: "FastAPI exceptions",
    query: "How does FastAPI raise authentication errors? import:fastapi call:HTTPException scope:function",
    description: "handlers and dependencies that raise FastAPI exceptions",
  },
  {
    label: "Rich console output",
    query: "How does Rich print formatted console output? import:rich call:console.print scope:function",
    description: "functions that print formatted terminal output",
  },
]

export default function App() {
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [selectedRepoIds, setSelectedRepoIds] = useState<string[]>([])
  const [query, setQuery] = useState("")
  const [libraryFilter, setLibraryFilter] = useState("")
  const [results, setResults] = useState<SearchHit[]>([])
  const [busy, setBusy] = useState<null | "search">(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void loadRepositories()
  }, [])

  async function loadRepositories() {
    try {
      const repos = await fetchRepositories()
      startTransition(() => {
        setRepositories(repos)
      })
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load indexed repositories.")
    }
  }

  async function handleSearch(searchQuery = query) {
    const normalizedQuery = searchQuery.trim()
    if (!normalizedQuery) {
      return
    }
    setBusy("search")
    setError(null)
    try {
      const response = await search({
        query: normalizedQuery,
        limit: 10,
        repo_ids: effectiveRepoIds,
      })
      startTransition(() => {
        setResults(response.hits)
      })
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : "Search failed.")
    } finally {
      setBusy(null)
    }
  }

  const visibleRepositories = useMemo(() => {
    const filter = libraryFilter.trim().toLowerCase()
    if (!filter) {
      return repositories
    }
    return repositories.filter((repository) => repository.full_name.toLowerCase().includes(filter))
  }, [libraryFilter, repositories])

  const effectiveRepoIds = useMemo(() => {
    if (selectedRepoIds.length > 0) {
      return selectedRepoIds
    }
    return visibleRepositories.map((repository) => repository.id)
  }, [selectedRepoIds, visibleRepositories])

  const indexedChunks = useMemo(
    () => repositories.reduce((sum, repository) => sum + repository.indexed_chunk_count, 0),
    [repositories],
  )

  const indexedFiles = useMemo(
    () => repositories.reduce((sum, repository) => sum + repository.indexed_file_count, 0),
    [repositories],
  )

  const canSubmit = busy === null && query.trim().length > 0

  return (
    <main className="min-h-screen bg-background px-4 py-8 font-mono text-foreground sm:px-6">
      <section className="mx-auto max-w-6xl">
        <header className="mx-auto mb-6 max-w-4xl text-center">
          <div className="text-xs uppercase text-muted-foreground">LibScout</div>
          <h1 className="mt-3 text-2xl font-semibold sm:text-3xl">search real library usage</h1>
          <p className="mx-auto mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
            tree-sitter indexed snippets, ranked by symbols, calls, imports, scope, and language.
          </p>
        </header>

        <section className="mx-auto max-w-5xl border bg-white">
          <div className="border-b bg-muted/40 px-4 py-2 text-xs text-muted-foreground">
            query / structural search
          </div>
          <div className="space-y-3 p-4">
            <Textarea
              data-testid="search-query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="min-h-28 resize-none rounded-sm border-0 bg-background p-4 text-base shadow-none ring-1 ring-border focus-visible:ring-1 focus-visible:ring-foreground"
              placeholder="How does FastAPI raise errors? import:fastapi call:HTTPException scope:function"
            />

            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0 flex-1">
                <div data-testid="search-examples" className="flex flex-wrap gap-2">
                  {SEARCH_EXAMPLES.map((example) => (
                    <button
                      key={example.query}
                      type="button"
                      data-testid="search-example"
                      onClick={() => {
                        setQuery(example.query)
                        void handleSearch(example.query)
                      }}
                      disabled={busy !== null}
                      className="max-w-full rounded-sm border bg-background px-2.5 py-1.5 text-left text-xs transition hover:border-foreground disabled:cursor-not-allowed disabled:opacity-60"
                      title={example.description}
                    >
                      <span className="font-semibold">{example.label}</span>
                      <span className="ml-2 break-all text-muted-foreground">{example.query}</span>
                    </button>
                  ))}
                </div>
              </div>
              <Button
                data-testid="search-button"
                size="sm"
                variant="outline"
                onClick={() => void handleSearch()}
                disabled={!canSubmit}
                className="h-8 shrink-0 rounded-sm px-3 text-xs"
              >
                <Search className="mr-2 h-3.5 w-3.5" />
                {busy === "search" ? "searching" : "search"}
              </Button>
            </div>

            {error ? (
              <p data-testid="error-state" className="text-xs text-destructive">
                error: {error}
              </p>
            ) : null}
            {busy ? (
              <p data-testid="loading-state" className="text-xs text-muted-foreground">
                searching symbols, calls, imports, and semantic matches.
              </p>
            ) : null}
          </div>

          <div className="grid border-t md:grid-cols-[1fr_320px]">
            <div data-testid="search-scope" className="flex flex-wrap items-center gap-2 border-b px-4 py-3 text-xs md:border-b-0 md:border-r">
              <span className="text-muted-foreground">scope</span>
              <Badge variant="outline" className="rounded-sm">
                {effectiveRepoIds.length || repositories.length} repositories
              </Badge>
              <Badge variant="outline" className="rounded-sm">
                {indexedFiles} files
              </Badge>
              <Badge variant="outline" className="rounded-sm">
                {indexedChunks} snippets
              </Badge>
            </div>
            <div className="space-y-2 p-3">
              <Input
                data-testid="repo-filter"
                placeholder="filter owner/name"
                value={libraryFilter}
                onChange={(event) => setLibraryFilter(event.target.value)}
                className="h-8 rounded-sm text-xs"
              />
              <ScrollArea className="h-32">
                <div className="space-y-1 pr-3">
                  {visibleRepositories.map((repository) => {
                    const selected = selectedRepoIds.includes(repository.id)
                    return (
                      <button
                        key={repository.id}
                        data-testid="repo-option"
                        type="button"
                        onClick={() =>
                          setSelectedRepoIds((current) =>
                            selected ? current.filter((repoId) => repoId !== repository.id) : [...current, repository.id],
                          )
                        }
                        className={`w-full rounded-sm border px-2 py-1.5 text-left text-xs transition ${
                          selected ? "border-foreground bg-muted" : "border-transparent bg-background hover:border-border"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate font-medium">{repository.full_name}</span>
                          <span className="text-muted-foreground">{repository.source}</span>
                        </div>
                        <div className="mt-1 text-muted-foreground">
                          {repository.indexed_chunk_count} snippets / {repository.indexed_file_count} files
                        </div>
                      </button>
                    )
                  })}
                </div>
              </ScrollArea>
              <Button
                data-testid="clear-selection"
                variant="outline"
                size="sm"
                onClick={() => setSelectedRepoIds([])}
                className="h-7 rounded-sm px-2 text-xs"
              >
                clear selection
              </Button>
            </div>
          </div>
        </section>

        <section className="mx-auto mt-5 max-w-5xl">
          <div className="mb-2 flex items-center justify-between border-b pb-2 text-xs">
            <h2 className="font-semibold">results</h2>
            <span className="text-muted-foreground">
              {busy === "search"
                ? "structural lookup in progress"
                : results.length
                  ? `${results.length} matches`
                  : "waiting for query"}
            </span>
          </div>

          <div data-testid="results-list" className="space-y-3">
            {!busy && results.length === 0 ? (
              <div data-testid="empty-state" className="border border-dashed bg-white px-4 py-8 text-center text-sm">
                <p className="font-medium">No snippets to show yet.</p>
                <p className="mt-2 text-xs text-muted-foreground">
                  try symbol:parse_file, call:client.get, import:fastapi, scope:function, or language:python.
                </p>
              </div>
            ) : null}

            {results.map((hit) => (
              <article
                key={`${hit.repo_id}-${hit.path}-${hit.start_line}`}
                data-testid="result-card"
                className="min-w-0 border bg-white p-3"
              >
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <Badge className="rounded-sm">{hit.repo_name}</Badge>
                  <Badge variant="secondary" className="rounded-sm">
                    {hit.language}
                  </Badge>
                  <Badge variant="outline" className="rounded-sm">
                    {hit.scope_type ?? hit.node_type}
                  </Badge>
                  <span className="min-w-0 truncate text-muted-foreground">
                    {hit.path}:{hit.start_line}-{hit.end_line}
                  </span>
                  <span className="ml-auto font-semibold">{hit.score.toFixed(3)}</span>
                </div>

                <div className="mt-3 grid min-w-0 items-start gap-3 lg:grid-cols-[minmax(0,250px)_minmax(0,1fr)]">
                  <aside className="min-w-0 space-y-2 text-xs">
                    <p data-testid="result-symbol" className="break-all font-semibold">
                      {hit.symbol ?? "Context snippet"}
                    </p>
                    <div data-testid="result-metadata" className="min-w-0 space-y-1 text-muted-foreground">
                      <p className="break-all">{hit.node_type}</p>
                      {hit.calls.slice(0, 4).map((call) => (
                        <p key={`call-${call}`} className="break-all">
                          calls {call}
                        </p>
                      ))}
                      {hit.imports.slice(0, 4).map((importName) => (
                        <p key={`import-${importName}`} className="break-all">
                          imports {importName}
                        </p>
                      ))}
                    </div>
                    <Separator />
                    <p className="break-words text-[11px] leading-5 text-muted-foreground">{hit.cst_path}</p>
                  </aside>
                  <CodeSnippet code={hit.excerpt} language={hit.language} />
                </div>
              </article>
            ))}
          </div>
        </section>
      </section>
    </main>
  )
}
