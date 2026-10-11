/**
 * UI workflow tests against the in-browser DEVELOPMENT FIXTURE (npm run dev:fixture).
 * They verify the frontend's behaviour and contract handling. They do NOT certify backend
 * integration; see integration.spec.ts for that.
 */
import { expect, test } from "@playwright/test";
import { introduceEmergency, revision, waitLoaded } from "./helpers";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await waitLoaded(page);
});

test("loads baseline with fixture clearly labelled", async ({ page }) => {
  await expect(page.getByTestId("fixture-banner")).toContainText("Development fixture");
  await expect(page.locator('[data-testid^="row-T"]')).toHaveCount(10);
  await expect(page.locator('[data-testid^="bar-J"]')).toHaveCount(25);
  await expect(page.getByTestId("backend-status")).toContainText("Dev fixture");
  expect(await revision(page)).toBe(0);
});

test("technician, map and timeline selection open one inspector", async ({ page }) => {
  await page.getByTestId("tech-T03").click();
  await expect(page.getByTestId("tech-T03")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("row-T03").getByRole("button").first()).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("bar-J10").click();
  await expect(page.getByTestId("job-inspector")).toContainText("J10");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("job-inspector")).toHaveCount(0);
  await page.locator(".job-J12").click();
  await expect(page.getByTestId("job-inspector")).toContainText("J12");
});

test("emergency preview leaves committed schedule unchanged until approval", async ({ page }) => {
  await introduceEmergency(page, "No heat at a clinic");
  await expect(page.getByTestId("proposal-panel")).toContainText("Ready to review");
  await expect(page.getByTestId("proposal-explanation")).toContainText("E01");
  await expect(page.getByTestId("change-E01")).toContainText("Added");
  expect(await revision(page)).toBe(0);
  // Proposed view shows E01; committed view does not.
  await expect(page.getByTestId("bar-E01")).toBeVisible();
  await page.getByRole("tab", { name: "Committed" }).click();
  await expect(page.getByTestId("bar-E01")).toHaveCount(0);
  await page.getByTestId("approve").click();
  await expect(page.getByTestId("announce")).toContainText("revision 1");
  expect(await revision(page)).toBe(1);
  await expect(page.getByTestId("bar-E01")).toBeVisible();
  await expect(page.getByTestId("proposal-panel")).toHaveCount(0);
});

test("first-feasible strategy shows real owner/time changes with before and after", async ({ page }) => {
  await introduceEmergency(page, "Power loss at a bakery", "first_feasible");
  const shifted = page.locator('[data-testid^="change-J"]');
  await expect(shifted.first()).toBeVisible();
  await expect(shifted.first()).toContainText(/Time shifted|Reassigned/);
  const changed = page.locator('[data-change="shifted"], [data-change="reassigned"]');
  await expect(changed.first()).toBeVisible();
  await expect(page.getByTestId("comparison")).toContainText("First feasible (proposed)");
});

test("reject preserves committed state", async ({ page }) => {
  await introduceEmergency(page, "Burst pipe");
  await expect(page.getByTestId("approve")).toBeEnabled();
  await page.getByTestId("reject").click();
  await expect(page.getByTestId("announce")).toContainText("rejected");
  expect(await revision(page)).toBe(0);
  await expect(page.getByTestId("bar-E01")).toHaveCount(0);
});

test("impossible event shows an honest no-plan result that cannot be approved", async ({ page }) => {
  await introduceEmergency(page, "Elevator fault (no qualified tech)");
  await expect(page.getByTestId("proposal-panel")).toContainText("No feasible plan");
  await expect(page.getByTestId("proposal-explanation")).toContainText("No technician has the required skill");
  await expect(page.getByTestId("approve")).toBeDisabled();
  await page.getByTestId("reject").click();
  expect(await revision(page)).toBe(0);
});

test("reset invalidates an open proposal and replay is deterministic twice", async ({ page }) => {
  const runOnce = async () => {
    await introduceEmergency(page, "No heat at a clinic");
    await page.getByTestId("approve").click();
    await expect(page.getByTestId("bar-E01")).toBeVisible();
    return page.getByTestId("bar-E01").getAttribute("aria-label");
  };
  const first = await runOnce();
  await page.getByTestId("reset").click();
  await expect(page.getByTestId("bar-E01")).toHaveCount(0);
  const second = await runOnce();
  expect(second).toBe(first);
  // An open proposal does not survive a reset.
  await page.getByTestId("reset").click();
  await introduceEmergency(page, "Burst pipe");
  await expect(page.getByTestId("approve")).toBeEnabled();
  await page.getByTestId("reset").click();
  await expect(page.getByTestId("proposal-panel")).toHaveCount(0);
});

test("stale approval is refused and the committed board is kept", async ({ page }) => {
  await introduceEmergency(page, "Burst pipe");
  await expect(page.getByTestId("approve")).toBeEnabled();
  // Another dispatcher commits first (fixture-only hook), so this proposal's base revision is stale.
  await page.evaluate(() => (window as unknown as { __dispatchiqFixture: { simulateExternalCommit(): void } }).__dispatchiqFixture.simulateExternalCommit());
  await page.getByTestId("approve").click();
  await expect(page.getByTestId("proposal-panel")).toContainText("Outdated");
  await expect(page.getByTestId("approve")).toBeDisabled();
  await page.getByRole("tab", { name: "Committed" }).click();
  await expect(page.locator('[data-testid^="bar-J"]')).toHaveCount(25);
  await expect(page.getByTestId("bar-E01")).toHaveCount(0);
  await page.getByRole("button", { name: /Refresh committed schedule/ }).click();
  await expect(page.getByTestId("announce")).toContainText("revision 1");
});

test.describe("responsive", () => {
  test("1024 uses a drawer inspector; 390 uses tabs and keeps controls usable", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await introduceEmergency(page, "No heat at a clinic");
    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(page.getByTestId("approve")).toBeVisible();
    await page.keyboard.press("Escape");
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByRole("tab", { name: /Timeline/ })).toBeVisible();
    await page.getByRole("tab", { name: /Details/ }).click();
    await expect(page.getByTestId("approve")).toBeVisible();
    await page.getByTestId("approve").click();
    await expect(page.getByTestId("announce")).toContainText("revision 1");
  });
});

test("screenshots for visual review", async ({ page }) => {
  const dir = "test-results/screenshots";
  await page.screenshot({ path: `${dir}/desktop-1440-baseline.png` });
  await introduceEmergency(page, "Power loss at a bakery", "first_feasible");
  await expect(page.getByTestId("proposal-panel")).toBeVisible();
  await page.screenshot({ path: `${dir}/desktop-1440-proposal.png` });
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${dir}/tablet-1024-proposal.png` });
  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${dir}/mobile-390.png`, fullPage: true });
});
