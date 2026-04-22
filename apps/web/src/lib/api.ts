import type {
  InjectRepositoryPayload,
  RagResponse,
  Repository,
  SearchResponse,
} from "@/types"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ""

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Request failed with ${response.status}`)
  }

  return response.json() as Promise<T>
}

export async function fetchRepositories(): Promise<Repository[]> {
  const data = await request<{ repositories: Repository[] }>("/api/repositories")
  return data.repositories
}

export async function injectRepository(payload: InjectRepositoryPayload) {
  return request<{
    repository: Repository
    index_report?: {
      repository: Repository
      indexed_files: number
      indexed_chunks: number
      skipped_files: number
    }
  }>("/api/repositories/inject", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function seedRepositories(payload?: { github_token?: string; index_now?: boolean }) {
  return request<{
    count: number
    repositories: Array<{
      repository: Repository
      indexed_files?: number
      indexed_chunks?: number
      skipped_files?: number
    }>
  }>("/api/repositories/seed", {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  })
}

export async function search(payload: { query: string; limit: number; repo_ids: string[] }) {
  return request<SearchResponse>("/api/search", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function askRag(payload: { query: string; limit: number; repo_ids: string[] }) {
  return request<RagResponse>("/api/rag", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}
