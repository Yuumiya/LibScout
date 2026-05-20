import { expect, test } from "@playwright/test"

const apiURL = "http://127.0.0.1:8123"

test.describe("LibScout search interface", () => {
  test("renders the full search shell and indexed repository scope", async ({ page }) => {
    await page.goto("/")

    await expect(page.getByRole("heading", { name: "search real library usage" })).toBeVisible()
    await expect(page.getByTestId("search-query")).toHaveValue("")
    await expect(page.getByTestId("search-query")).toHaveAttribute(
      "placeholder",
      "How does FastAPI raise errors? import:fastapi call:HTTPException scope:function",
    )
    await expect(page.getByTestId("search-button")).toHaveText(/search/)
    await expect(page.getByTestId("search-examples")).toContainText("Pydantic fields")
    await expect(page.getByTestId("search-examples")).toContainText("import:pydantic call:Field scope:class")
    await expect(page.getByTestId("search-scope")).toContainText("2 repositories")
    await expect(page.getByTestId("search-scope")).toContainText("5 files")
    await expect(page.getByTestId("empty-state")).toContainText("No snippets to show yet.")

    await page.getByTestId("repo-filter").fill("fixture-py")
    await expect(page.getByTestId("repo-option")).toHaveCount(1)
    await expect(page.getByTestId("repo-option")).toContainText("tests/fixture-py")
    await page.getByTestId("clear-selection").click()
  })

  test("search usage mode renders ranked structural results with syntax metadata and highlighting", async ({ page }) => {
    await page.goto("/")
    await runSearch(page, "call:httpx.get")

    const firstCard = page.getByTestId("result-card").first()
    await expect(firstCard.getByTestId("result-symbol")).toHaveText("fetch_user")
    await expect(firstCard).toContainText("tests/fixture-py")
    await expect(firstCard).toContainText("python")
    await expect(firstCard).toContainText("function")
    await expect(firstCard).toContainText("client.py:")
    await expect(firstCard.getByTestId("result-metadata")).toContainText("calls httpx.get")
    await expect(firstCard.getByTestId("result-metadata")).toContainText("imports httpx")
    await expect(firstCard.locator("code span").filter({ hasText: "def" }).first()).toBeVisible()
    await expect(firstCard.locator("code span").filter({ hasText: "return" }).first()).toBeVisible()
  })

  test("example queries run searches with useful results", async ({ page }) => {
    await page.goto("/")

    const examples = [
      {
        label: "Pydantic fields",
        query: "import:pydantic call:Field scope:class",
        symbol: "Item",
      },
      {
        label: "Typer options",
        query: "call:typer.Option scope:function",
        symbol: "delete",
      },
      {
        label: "FastAPI exceptions",
        query: "How does FastAPI raise authentication errors? import:fastapi call:HTTPException scope:function",
        symbol: "make_not_authenticated_error",
      },
      {
        label: "Rich console output",
        query: "How does Rich print formatted console output? import:rich call:console.print scope:function",
        symbol: "report",
      },
    ]

    for (const example of examples) {
      const responsePromise = page.waitForResponse(`${apiURL}/api/search`)
      await page.getByTestId("search-example").filter({ hasText: example.label }).click()
      await responsePromise
      await expect(page.getByTestId("search-query")).toHaveValue(example.query)
      await expect(page.getByTestId("result-card").first().getByTestId("result-symbol")).toHaveText(example.symbol)
    }
  })

  test("repository scoping and language search modes change the result set", async ({ page }) => {
    await page.goto("/")

    await page.getByTestId("repo-filter").fill("fixture-py")
    await page.getByTestId("repo-option").click()
    await expect(page.getByTestId("search-scope")).toContainText("1 repositories")
    await runSearch(page, "import:request language:typescript")
    await expect(page.getByTestId("empty-state")).toContainText("No snippets to show yet.")

    await page.getByTestId("clear-selection").click()
    await page.getByTestId("repo-filter").fill("")
    await runSearch(page, "import:request language:typescript")

    const firstCard = page.getByTestId("result-card").first()
    await expect(firstCard.getByTestId("result-symbol")).toHaveText("loadUser")
    await expect(firstCard).toContainText("tests/fixture-ts")
    await expect(firstCard).toContainText("typescript")
    await expect(firstCard.getByTestId("result-metadata")).toContainText("calls request")
  })

  test("empty, loading, and error states are visible", async ({ page }) => {
    await page.goto("/")

    let forceSearchFailure = false
    await page.route(`${apiURL}/api/search`, async (route) => {
      if (forceSearchFailure) {
        await route.fulfill({ status: 500, body: "forced search failure" })
        return
      }
      await new Promise((resolve) => setTimeout(resolve, 300))
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ hits: [] }),
      })
    })

    await page.getByTestId("search-query").fill("symbol:does_not_exist")
    await page.getByTestId("search-button").click()
    await expect(page.getByTestId("loading-state")).toContainText("searching symbols")
    await expect(page.getByTestId("empty-state")).toContainText("No snippets to show yet.")

    forceSearchFailure = true
    await page.getByTestId("search-query").fill("call:httpx.get")
    await page.getByTestId("search-button").click()
    await expect(page.getByTestId("error-state")).toContainText("forced search failure")
  })
})

test.describe("LibScout search API through Playwright", () => {
  test("ranks exact call-site function chunks above enclosing class context", async ({ request }) => {
    const response = await request.post(`${apiURL}/api/search`, {
      data: { query: "call:httpx.get", limit: 5 },
    })
    expect(response.ok()).toBeTruthy()

    const payload = await response.json()
    expect(payload.hits.length).toBeGreaterThan(0)
    expect(payload.hits[0].symbol).toBe("fetch_user")
    expect(payload.hits[0].scope_type).toBe("function")
    expect(payload.hits[0].calls).toContain("httpx.get")

    const classHit = payload.hits.find((hit: { symbol: string }) => hit.symbol === "ApiClient")
    if (classHit) {
      expect(classHit.score).toBeLessThan(payload.hits[0].score)
    }
  })

  test("supports symbol, import, language, and MCP sampling search modes", async ({ request }) => {
    const symbolResponse = await request.post(`${apiURL}/api/search`, {
      data: { query: "symbol:fetch_user scope:function", limit: 3 },
    })
    expect(symbolResponse.ok()).toBeTruthy()
    const symbolPayload = await symbolResponse.json()
    expect(symbolPayload.hits[0].symbol).toBe("fetch_user")
    expect(symbolPayload.hits[0].scope_type).toBe("function")

    const importResponse = await request.post(`${apiURL}/api/search`, {
      data: { query: "import:request language:typescript", limit: 3 },
    })
    expect(importResponse.ok()).toBeTruthy()
    const importPayload = await importResponse.json()
    expect(importPayload.hits[0].symbol).toBe("loadUser")
    expect(importPayload.hits[0].language).toBe("typescript")

    const mcpResponse = await request.post(`${apiURL}/mcp/search_usage`, {
      data: { query: "call:httpx.get", limit: 3, enable_sampling: true },
    })
    expect(mcpResponse.ok()).toBeTruthy()
    const mcpPayload = await mcpResponse.json()
    expect(mcpPayload.hits[0].symbol).toBe("fetch_user")
    expect(mcpPayload.answer).toContain("Best-practices brief")
    expect(mcpPayload.sampling_request.method).toBe("sampling/createMessage")
  })
})

async function runSearch(page: import("@playwright/test").Page, query: string) {
  await page.getByTestId("search-query").fill(query)
  const responsePromise = page.waitForResponse(`${apiURL}/api/search`)
  await page.getByTestId("search-button").click()
  await responsePromise
}
