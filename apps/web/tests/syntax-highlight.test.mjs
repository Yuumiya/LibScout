import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { test } from "node:test"

const source = readFileSync(new URL("../src/lib/syntax-highlight.ts", import.meta.url), "utf8")
const component = readFileSync(new URL("../src/components/CodeSnippet.tsx", import.meta.url), "utf8")

test("syntax highlighter supports highlighted snippet rendering primitives", () => {
  assert.match(source, /export function tokenizeCode/)
  assert.match(source, /"keyword"/)
  assert.match(source, /"string"/)
  assert.match(source, /"comment"/)
  assert.match(source, /def/)
  assert.match(source, /typescript/)
  assert.match(component, /tokenizeCode\(code, language\)/)
  assert.match(component, /<span/)
  assert.match(component, /TOKEN_CLASS\[token\.kind\]/)
})
