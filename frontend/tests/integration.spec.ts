import { expect, test, type APIRequestContext } from "@playwright/test";
import { introduceEmergency, revision, waitLoaded } from "./helpers";
import type { Proposal, Snapshot } from "../src/api/types";

const api = process.env.DISPATCHIQ_API ?? "http://127.0.0.1:8000";
const base = (s: Snapshot) => ({
  scenario_id: s.scenario_id,
  scenario_epoch: s.scenario_epoch,
  base_revision: s.revision,
});
const snapshot = async (request: APIRequestContext): Promise<Snapshot> =>
  (await request.get(`${api}/api/scenario`)).json();
test.beforeAll(async ({ request }) => {
  const response = await request.get(`${api}/api/health`);
  expect(
    response.ok(),
    "Real API must be running; integration tests cannot silently skip",
  ).toBeTruthy();
});
test.beforeEach(async ({ page, request }) => {
  const s = await snapshot(request);
  expect(
    (await request.post(`${api}/api/reset`, { data: base(s) })).ok(),
  ).toBeTruthy();
  await page.goto("/");
  await waitLoaded(page);
});

test("real preview, evidence, reject, repeat, approve and reset", async ({
  page,
  request,
}) => {
  const original = await snapshot(request);
  await expect(page.getByTestId("fixture-banner")).toHaveCount(0);
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/events/preview") &&
      r.request().method() === "POST",
  );
  await introduceEmergency(page, "No heat at a clinic");
  const p: Proposal = await (await response).json();
  expect(p.status).toBe("ready");
  expect(p.validation.valid).toBe(true);
  expect(
    p.changes.some(
      (c) => c.before && c.after && c.before.start_min !== c.after.start_min,
    ),
  ).toBe(true);
  expect(await snapshot(request)).toEqual(original);
  await expect(page.getByTestId("approve")).toBeEnabled();
  await expect(page.getByTestId("bar-E01")).toBeVisible();
  await page.getByText("Why this recommendation", { exact: true }).click();
  await expect(page.getByTestId("proposal-explanation")).toHaveText(
    p.explanation,
  );
  await page.getByText("Compare evaluated approaches", { exact: true }).click();
  for (const comparison of p.comparison)
    if (comparison.diff_metrics)
      await expect(page.getByTestId("comparison")).toContainText(
        `${comparison.diff_metrics.absolute_start_shift_min} min`,
      );
  await page.getByRole("tab", { name: "Approved", exact: true }).click();
  await expect(page.getByTestId("bar-E01")).toHaveCount(0);
  await page.getByTestId("reject").click();
  await expect(page.getByTestId("proposal-panel")).toHaveCount(0);
  expect(await snapshot(request)).toEqual(original);
  await introduceEmergency(page, "No heat at a clinic");
  await page.getByTestId("approve").click();
  await expect.poll(() => revision(page)).toBe(original.revision + 1);
  const approved = await snapshot(request);
  expect(approved.events).toHaveLength(1);
  expect(approved.validation.valid).toBe(true);
  expect(approved.schedule.assignments.some((a) => a.job_id === "E01")).toBe(
    true,
  );
  await expect(page.getByTestId("bar-E01")).toBeVisible();
  await page.getByTestId("reset").click();
  await expect.poll(() => revision(page)).toBe(original.revision + 2);
  expect((await snapshot(request)).schedule).toEqual(original.schedule);
});

test("job and technician selection links map, row and one contextual mode", async ({
  page,
}) => {
  await page.getByTestId("tech-T03").click();
  await expect(page.getByTestId("technician-inspector")).toContainText("Priya");
  await expect(
    page.getByTestId("row-T03").getByRole("button").first(),
  ).toHaveAttribute("aria-pressed", "true");
  await page.keyboard.press("Escape");
  await page.getByTestId("bar-J12").click();
  await expect(page.getByTestId("job-inspector")).toContainText("J12");
  await expect(page.locator(".map-job-marker.selected")).toHaveCount(1);
  await expect(page.getByTestId("technician-inspector")).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("inspector")).toHaveCount(0);
  await page.locator('[title="John start location"]').click();
  await expect(page.getByTestId("technician-inspector")).toContainText("John");
});

test("real no-plan and rejected invalid input preserve the approved schedule", async ({
  page,
  request,
}) => {
  const original = await snapshot(request);
  // A tight response deadline is a valid contract request with no feasible insertion.
  await page.getByTestId("introduce-emergency").click();
  await page.getByLabel("Respond within (min)").fill("1");
  await page.getByTestId("preview-emergency").click();
  await expect(page.getByTestId("proposal-panel")).toContainText(
    "No feasible plan",
  );
  await expect(page.getByTestId("approve")).toBeDisabled();
  expect(await snapshot(request)).toEqual(original);
  await page.getByTestId("reject").click();
  // Unknown but well-formed skills are accepted as input; no qualified technician is an honest no-plan.
  await introduceEmergency(page, "Elevator fault (no qualified tech)");
  await expect(page.getByTestId("proposal-panel")).toContainText(
    "No feasible plan",
  );
  await expect(page.getByTestId("approve")).toBeDisabled();
  expect(await snapshot(request)).toEqual(original);
  await page.getByTestId("reject").click();
  // The real validator rejects an overlong customer name and the client keeps the schedule.
  await page.getByTestId("introduce-emergency").click();
  await page.getByLabel("Customer", { exact: true }).fill("x".repeat(161));
  await page.getByTestId("preview-emergency").click();
  await expect(page.getByTestId("operation-error")).toBeVisible();
  expect(await snapshot(request)).toEqual(original);
});

test("stale approval is refused, review can close and reopen, refresh restores real state", async ({
  page,
  request,
}) => {
  await introduceEmergency(page, "No heat at a clinic");
  await expect(page.getByTestId("approve")).toBeEnabled();
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("inspector")).toHaveCount(0);
  await page.getByTestId("review-proposal").click();
  await expect(page.getByTestId("approve")).toBeVisible();
  const original = await snapshot(request);
  await request.post(`${api}/api/reset`, { data: base(original) });
  await page.getByTestId("approve").click();
  await expect(page.getByTestId("proposal-panel")).toContainText("Outdated");
  await expect(page.getByTestId("approve")).toBeDisabled();
  await page
    .getByRole("button", { name: "Refresh committed schedule" })
    .click();
  await expect.poll(() => revision(page)).toBe(original.revision + 1);
  await expect(page.locator('[data-testid^="bar-J"]')).toHaveCount(25);
});

test("data-backed navigation, searches, filters and empty states", async ({
  page,
}) => {
  const nav = page.getByRole("navigation", { name: "Main navigation" });
  await nav.getByRole("button", { name: "Overview", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Up next" })).toBeVisible();
  await nav.getByRole("button", { name: /Jobs/ }).click();
  await page.getByRole("textbox", { name: "Search jobs" }).fill("Customer 3");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.getByRole("button", { name: /Customer 3/ }).click();
  await expect(page.getByTestId("job-inspector")).toContainText("J03");
  await page.keyboard.press("Escape");
  await page
    .getByRole("textbox", { name: "Search jobs" })
    .fill("unknown customer");
  await expect(page.getByText("No matching appointments")).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.locator("tbody tr")).toHaveCount(25);
  await nav.getByRole("button", { name: "Technicians", exact: true }).click();
  await page.getByRole("textbox", { name: "Search technicians" }).fill("Priya");
  await expect(page.locator(".technician-card")).toHaveCount(1);
  await nav.getByRole("button", { name: "Activity", exact: true }).click();
  await expect(
    page.getByText("No disruption events have been applied to this schedule."),
  ).toBeVisible();
});

test("keyboard navigation, focus return, map expansion and client expiry protection", async ({
  page,
}) => {
  await page.getByTestId("introduce-emergency").focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("dialog", { name: "New emergency" }),
  ).toBeVisible();
  await page.keyboard.press("Tab");
  expect(
    await page.evaluate(
      () => !!document.activeElement?.closest('[role="dialog"]'),
    ),
  ).toBe(true);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("introduce-emergency")).toBeFocused();
  await page.getByRole("button", { name: "Expand map", exact: true }).click();
  await expect(page.locator(".service-map")).toHaveClass(/expanded/);
  await page.getByRole("button", { name: "Compact map", exact: true }).click();
  await page.clock.install();
  await introduceEmergency(page, "No heat at a clinic");
  await expect(page.getByTestId("approve")).toBeEnabled();
  await page.clock.fastForward(16 * 60 * 1000);
  await expect(page.getByTestId("approve")).toBeDisabled();
  await expect(page.getByTestId("proposal-panel")).toContainText("expired");
});

test("server error after load keeps the approved board; retry does not create fixture data", async ({
  page,
  request,
}) => {
  const original = await snapshot(request);
  await page.route("**/api/events/preview", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "OPTIMIZER_FAILED", message: "Optimizer unavailable" },
      }),
    }),
  );
  await introduceEmergency(page, "No heat at a clinic");
  await expect(page.getByTestId("operation-error")).toContainText(
    "committed schedule was not changed",
  );
  expect(await snapshot(request)).toEqual(original);
  await expect(page.locator('[data-testid^="bar-J"]')).toHaveCount(25);
  await expect(page.getByTestId("fixture-banner")).toHaveCount(0);
});

for (const [width, height] of [
  [1440, 900],
  [1280, 800],
  [1024, 768],
  [390, 844],
])
  test(`API workflow and screenshots at ${width}×${height}`, async ({
    page,
    request,
  }) => {
    await page.setViewportSize({ width, height });
    await page.reload();
    await waitLoaded(page);
    await expect(page.getByTestId("introduce-emergency")).toBeVisible();
    const dimensions = await page.evaluate(() => ({
      width: document.documentElement.scrollWidth,
      height: document.documentElement.scrollHeight,
    }));
    expect(dimensions.width).toBe(width);
    expect(dimensions.height).toBe(height);
    await page.screenshot({ path: `evidence/after/${width}x${height}.png` });
    const original = await snapshot(request);
    await introduceEmergency(page, "No heat at a clinic");
    await expect(page.getByTestId("approve")).toBeEnabled();
    if (width < 1360) await expect(page.getByRole("dialog")).toBeVisible();
    await page.screenshot({
      path: `evidence/after/${width}x${height}-proposal.png`,
    });
    await page.getByTestId("approve").click();
    await expect.poll(() => revision(page)).toBe(original.revision + 1);
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("bar-E01")).toBeVisible();
    if (width === 390) {
      await page.getByRole("tab", { name: "Map", exact: true }).click();
      await expect(page.getByTestId("route-map")).toBeVisible();
      await page.locator(".job-E01").click();
      await expect(page.getByTestId("job-inspector")).toContainText("E01");
    }
  });
