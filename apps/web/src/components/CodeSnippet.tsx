import { tokenizeCode } from "@/lib/syntax-highlight"

const TOKEN_CLASS: Record<ReturnType<typeof tokenizeCode>[number]["kind"], string> = {
  comment: "text-slate-500",
  keyword: "text-blue-700",
  literal: "text-amber-700",
  number: "text-emerald-700",
  operator: "text-slate-600",
  plain: "text-slate-950",
  string: "text-green-700",
}

type CodeSnippetProps = {
  code: string
  language: string
}

export function CodeSnippet({ code, language }: CodeSnippetProps) {
  const tokens = tokenizeCode(code, language)

  return (
    <pre className="min-w-0 self-start overflow-x-auto rounded-sm border bg-background p-4 text-xs leading-6 text-foreground">
      <code>
        {tokens.map((token, index) => (
          <span key={`${index}-${token.kind}`} className={TOKEN_CLASS[token.kind]}>
            {token.text}
          </span>
        ))}
      </code>
    </pre>
  )
}
