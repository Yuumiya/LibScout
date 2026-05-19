export type SyntaxToken = {
  text: string
  kind: "comment" | "keyword" | "literal" | "number" | "operator" | "plain" | "string"
}

const LANGUAGE_KEYWORDS: Record<string, Set<string>> = {
  python: new Set([
    "as",
    "async",
    "await",
    "class",
    "def",
    "except",
    "finally",
    "for",
    "from",
    "if",
    "import",
    "in",
    "is",
    "lambda",
    "return",
    "try",
    "with",
    "yield",
  ]),
  typescript: new Set([
    "async",
    "await",
    "class",
    "const",
    "export",
    "from",
    "function",
    "import",
    "interface",
    "let",
    "new",
    "return",
    "type",
  ]),
}

const SHARED_LITERALS = new Set(["false", "none", "null", "true", "undefined"])
const TOKEN_RE = /(#.*|\/\/.*|\/\*[\s\S]*?\*\/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|\b\d+(?:\.\d+)?\b|\b[A-Za-z_][A-Za-z0-9_]*\b|[{}()[\].,;:+\-*/%=<>!&|?]+|\s+|.)/g

export function tokenizeCode(source: string, language: string): SyntaxToken[] {
  const keywords = LANGUAGE_KEYWORDS[language.toLowerCase()] ?? LANGUAGE_KEYWORDS.typescript
  return Array.from(source.matchAll(TOKEN_RE), ([text]) => ({
    text,
    kind: classifyToken(text, keywords),
  }))
}

function classifyToken(text: string, keywords: Set<string>): SyntaxToken["kind"] {
  const lower = text.toLowerCase()
  if (text.startsWith("#") || text.startsWith("//") || text.startsWith("/*")) {
    return "comment"
  }
  if (text.startsWith("\"") || text.startsWith("'") || text.startsWith("`")) {
    return "string"
  }
  if (/^\d/.test(text)) {
    return "number"
  }
  if (keywords.has(lower)) {
    return "keyword"
  }
  if (SHARED_LITERALS.has(lower)) {
    return "literal"
  }
  if (/^[{}()[\].,;:+\-*/%=<>!&|?]+$/.test(text)) {
    return "operator"
  }
  return "plain"
}
