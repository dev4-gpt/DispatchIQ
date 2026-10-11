/**
 * Full workflow against Developer 1's real FastAPI service (127.0.0.1:8000 via the Vite proxy).
 * Skipped automatically when the API is not running, so a green fixture run is never mistaken
 * for integration. Start the backend first, then run: npx playwright test --project=integration
 */
import { expect, test } from "@playwright/test";
import { introduceEmergency, revision, waitLoaded } from "./helpers";

test.beforeAll(async ({ request }) => {
  const ok = await request.get("http://127.0.0.1:8000/api/health").then((r) => r.ok()).catch(() => false);
  test.skip(!ok, "Backend API not running on 127.0.0.1:8000");
});

test("real API: baseline, preview, approve, reset", async ({ page }) => {
  await page.goto("/");
  await waitLoaded(page);
  await expect(page.getByTestId("fixture-banner")).toHaveCount(0);
  const rev0 = await revision(page);
  await introduceEmergency(page, "No heat at a clinic");
  await expect(page.getByTestId("proposal-panel")).toBeVisible();
  expect(await revision(page)).toBe(rev0);
  const ready = await page.getByTestId("approve").isEnabled();
  if (ready) {
    await page.getByTestId("approve").click();
    await expect.poll(() => revision(page)).toBe(rev0 + 1);
  }
  await page.getByTestId("reset").click();
  await expect.poll(() => revision(page)).toBeGreaterThan(rev0);
});
