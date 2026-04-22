import { Search, Sparkles } from "lucide-react"
import { startTransition, useEffect, useMemo, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import { askRag, fetchRepositories, search } from "@/lib/api"
import type { RagResponse, Repository, SearchHit } from "@/types"

const DEFAULT_QUERY = "How do I parse a file, detect its language, and extract CST-backed chunks?"

export default function App() {
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [selectedRepoIds, setSelectedRepoIds] = useState<string[]>([])
  const [query, setQuery] = useState(DEFAULT_QUERY)
  const [libraryFilter, setLibraryFilter] = useState("")
  const [results, setResults] = useState<SearchHit[]>([])
  const [rag, setRag] = useState<RagResponse | null>(null)
  const [busy, setBusy] = useState<null | "search" | "rag">(null)
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

  async function handleSearch() {
    setBusy("search")
    setError(null)
    try {
      const response = await search({
        query,
        limit: 10,
        repo_ids: effectiveRepoIds,
      })
      startTransition(() => {
        setResults(response.hits)
        setRag(null)
      })
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : "Search failed.")
    } finally {
      setBusy(null)
    }
  }

  async function handleRag() {
    setBusy("rag")
    setError(null)
    try {
      const response = await askRag({
        query,
        limit: 6,
        repo_ids: effectiveRepoIds,
      })
      startTransition(() => {
        setRag(response)
        setResults(response.hits)
      })
    } catch (ragError) {
      setError(ragError instanceof Error ? ragError.message : "RAG request failed.")
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

  return (
    <main className="container py-8">
      <section className="mx-auto max-w-5xl">
        <div className="mb-8 flex flex-col items-center gap-4 text-center">
          <Badge variant="secondary">LibScout</Badge>
          <div className="space-y-3">
            <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
              Search how libraries are actually used.
            </h1>
            <p className="mx-auto max-w-2xl text-base leading-7 text-muted-foreground">
              Semantic search over real usage snippets from public repositories, with surrounding code context and
              retrieval-backed summaries.
            </p>
          </div>
        </div>

        <Card className="bg-white">
          <CardContent className="p-6 sm:p-8">
            <div className="space-y-4">
              <Textarea
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="min-h-[160px] text-base"
                placeholder="How do I handle auth with this library? How is parsing configured? How are errors surfaced?"
              />
              <div className="flex flex-col gap-3 sm:flex-row">
                <Button onClick={handleSearch} disabled={busy !== null} className="sm:flex-1">
                  <Search className="mr-2 h-4 w-4" />
                  {busy === "search" ? "Searching…" : "Search Usage"}
                </Button>
                <Button variant="secondary" onClick={handleRag} disabled={busy !== null} className="sm:flex-1">
                  <Sparkles className="mr-2 h-4 w-4" />
                  {busy === "rag" ? "Summarizing…" : "Summarize Best Practices"}
                </Button>
              </div>
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
            </div>
          </CardContent>
        </Card>

        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <span>Searching</span>
          <Badge variant="outline">{effectiveRepoIds.length || repositories.length} repositories</Badge>
          <Badge variant="outline">{indexedFiles} files</Badge>
          <Badge variant="outline">{indexedChunks} snippets</Badge>
        </div>

        {rag ? (
          <Card className="mt-6 bg-slate-950 text-slate-50">
            <CardHeader>
              <CardTitle className="text-xl">Best Practices Brief</CardTitle>
              <CardDescription className="text-slate-300">
                Retrieval-backed synthesis over the current search scope.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="whitespace-pre-wrap text-sm leading-6 text-slate-100">{rag.answer}</pre>
            </CardContent>
          </Card>
        ) : null}

        <Card className="mt-6 bg-white">
          <CardHeader>
            <CardTitle className="text-xl">Results</CardTitle>
            <CardDescription>
              {results.length
                ? `${results.length} semantic matches with surrounding code context.`
                : "Run a query to inspect indexed usage snippets."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {results.map((hit) => (
                <article key={`${hit.repo_id}-${hit.path}-${hit.start_line}`} className="rounded-xl border bg-background/80 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge>{hit.repo_name}</Badge>
                    <Badge variant="secondary">{hit.language}</Badge>
                    <Badge variant="outline">{hit.node_type}</Badge>
                    <span className="text-xs text-muted-foreground">
                      {hit.path}:{hit.start_line}-{hit.end_line}
                    </span>
                    <span className="ml-auto text-xs font-semibold text-foreground">{hit.score.toFixed(3)}</span>
                  </div>
                  <p className="mt-3 text-sm font-medium">{hit.symbol ?? "Context snippet"}</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted-foreground">{hit.cst_path}</p>
                  <Separator className="my-4" />
                  <pre className="overflow-x-auto rounded-lg bg-slate-950 p-4 text-xs leading-6 text-slate-100">
                    {hit.excerpt}
                  </pre>
                </article>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="mt-8 border-dashed bg-background/40">
          <CardHeader className="pb-4">
            <CardTitle className="text-base">Search Configuration</CardTitle>
            <CardDescription>
              Optional scope controls. Leave everything unselected to search across the full indexed set.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              placeholder="Filter libraries by owner/name"
              value={libraryFilter}
              onChange={(event) => setLibraryFilter(event.target.value)}
            />
            <ScrollArea className="h-[240px]">
              <div className="space-y-2 pr-4">
                {visibleRepositories.map((repository) => {
                  const selected = selectedRepoIds.includes(repository.id)
                  return (
                    <button
                      key={repository.id}
                      type="button"
                      onClick={() =>
                        setSelectedRepoIds((current) =>
                          selected ? current.filter((repoId) => repoId !== repository.id) : [...current, repository.id],
                        )
                      }
                      className={`w-full rounded-lg border px-4 py-3 text-left transition ${
                        selected ? "border-foreground/20 bg-muted" : "border-border bg-background hover:bg-accent"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium">{repository.full_name}</p>
                          <p className="text-xs text-muted-foreground">
                            {repository.indexed_chunk_count} snippets · {repository.indexed_file_count} files
                          </p>
                        </div>
                        <Badge variant={repository.source === "github" ? "outline" : "secondary"}>{repository.source}</Badge>
                      </div>
                    </button>
                  )
                })}
              </div>
            </ScrollArea>
            <Button variant="outline" onClick={() => setSelectedRepoIds([])}>
              Clear Explicit Selection
            </Button>
          </CardContent>
        </Card>
      </section>
    </main>
  )
}
