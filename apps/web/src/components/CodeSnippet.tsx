import { tokenizeCode } from "@/lib/syntax-highlight"

const TOKEN_CLASS: Record<ReturnType<typeof tokenizeCode>[number]["kind"], string> = {
  comment: "text-slate-500",
  keyword: "text-sky-300",
  literal: "text-amber-200",
  number: "text-emerald-200",
  operator: "text-slate-400",
  plain: "text-slate-100",
  string: "text-lime-200",
}

type CodeSnippetProps = {
  code: string
  language: string
}

export function CodeSnippet({ code, language }: CodeSnippetProps) {
  const tokens = tokenizeCode(code, language)

  return (
    <pre className="overflow-x-auto rounded-lg bg-slate-950 p-4 text-xs leading-6 text-slate-100">
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
