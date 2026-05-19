import { defineConfig, devices } from "@playwright/test"

const apiURL = "http://127.0.0.1:8123"
const webURL = "http://127.0.0.1:5173"

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: webURL,
    trace: "on-first-retry",
  },
  webServer: [
    {
      command: "cd ../.. && .venv/bin/python apps/web/tests/fixtures/run_e2e_api.py",
      url: `${apiURL}/api/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port 5173`,
      env: {
        VITE_API_BASE_URL: apiURL,
      },
      url: webURL,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
})
