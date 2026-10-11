/** Real API mode with nothing listening behind the proxy: the UI must say so, never show mock data. */
import { expect, test } from "@playwright/test";

test("no backend: honest error, retry, and no fixture fallback", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByTestId("load-error")).toBeVisible();
  await expect(page.getByTestId("backend-status")).toContainText(
    "Connection unavailable",
  );
  await expect(page.getByTestId("fixture-banner")).toHaveCount(0);
  await expect(page.locator('[data-testid^="row-T"]')).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});
