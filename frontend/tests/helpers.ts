import { expect, type Page } from "@playwright/test";

export async function introduceEmergency(
  page: Page,
  preset: string,
  strategy?: "stable_insertion" | "first_feasible",
) {
  await page.getByTestId("introduce-emergency").click();
  await page.getByRole("button", { name: preset }).click();
  if (strategy) await page.getByTestId("strategy").selectOption(strategy);
  await page.getByTestId("preview-emergency").click();
}

export async function revision(page: Page) {
  const t = await page
    .getByText(/^rev \d+$/)
    .first()
    .textContent();
  return Number(t!.replace("rev ", ""));
}

export async function waitLoaded(page: Page) {
  await expect(page.getByTestId("row-T00")).toBeVisible();
  if ((page.viewportSize()?.width ?? 1440) >= 768)
    await expect(page.locator(".map-base-marker")).toHaveCount(10);
}
