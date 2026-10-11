import { defineConfig, devices } from "@playwright/test";

// CHROMIUM_PATH lets CI/sandboxes reuse a preinstalled Chromium; otherwise run `npx playwright install chromium`.
const launchOptions = process.env.CHROMIUM_PATH
  ? { executablePath: process.env.CHROMIUM_PATH }
  : {};
const integrationUrl = process.env.DISPATCHIQ_UI ?? "http://127.0.0.1:5173";
const integrationPort = new URL(integrationUrl).port || "5173";

export default defineConfig({
  testDir: "./tests",
  outputDir: "./test-results/artifacts",
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    viewport: { width: 1440, height: 900 },
    launchOptions,
    trace: "retain-on-failure",
  },
  projects: [
    {
      // UI workflow against the labeled in-browser development fixture. NOT backend integration.
      name: "fixture-ui",
      testMatch: /fixture-ui\.spec\.ts/,
      use: { baseURL: "http://127.0.0.1:5174" },
    },
    {
      // Real API mode with no backend running: proves there is no silent mock fallback.
      name: "api-unavailable",
      testMatch: /api-unavailable\.spec\.ts/,
      use: { baseURL: "http://127.0.0.1:5175" },
    },
    {
      // Full integration against Developer 1's FastAPI on 127.0.0.1:8000. Skips itself if the API is down.
      name: "integration",
      testMatch: /integration\.spec\.ts/,
      use: { baseURL: integrationUrl },
    },
  ],
  webServer: [
    {
      command: "npx vite --mode fixture --port 5174 --strictPort",
      url: "http://127.0.0.1:5174",
      reuseExistingServer: false,
    },
    {
      command: "npx vite --port 5175 --strictPort",
      url: "http://127.0.0.1:5175",
      reuseExistingServer: false,
      env: { DISPATCHIQ_API: "http://127.0.0.1:9" },
    },
    {
      command: `npx vite --port ${integrationPort} --strictPort`,
      url: integrationUrl,
      reuseExistingServer: true,
    },
  ],
});
