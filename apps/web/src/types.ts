export type Repository = {
  id: string
  source: "github" | "local"
  owner: string
  name: string
  full_name: string
  local_dir: string
  default_branch: string
  ref: string | null
  indexed_file_count: number
  indexed_chunk_count: number
  last_indexed_at: string | null
}

export type SearchHit = {
  repo_id: string
  repo_name: string
  path: string
  language: string
  node_type: string
  symbol: string | null
  start_line: number
  end_line: number
  score: number
  excerpt: string
  cst_path: string
}

export type SearchResponse = {
  hits: SearchHit[]
}

export type RagResponse = {
  query: string
  answer: string
  hits: SearchHit[]
}

export type InjectRepositoryPayload =
  | {
      source: "github"
      owner: string
      name: string
      ref?: string
      github_token?: string
      index_now: boolean
    }
  | {
      source: "local"
      path: string
      owner?: string
      name?: string
      index_now: boolean
    }
