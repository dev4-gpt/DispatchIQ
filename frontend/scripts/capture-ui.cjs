const { chromium } = require("@playwright/test");
const fs = require("node:fs");
const path = require("node:path");
const stage = process.argv[2] || "before";
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {}),
  });
  const report = [];
  const out = path.resolve("evidence", stage);
  fs.mkdirSync(out, { recursive: true });
  for (const [width, height] of [
    [1440, 900],
    [1280, 800],
    [1024, 768],
    [390, 844],
  ]) {
    const page = await browser.newPage({ viewport: { width, height } });
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(process.env.DISPATCHIQ_UI || "http://127.0.0.1:5173");
    await page.getByTestId("row-T00").waitFor();
    await page.screenshot({
      path: path.join(out, `${width}x${height}.png`),
      fullPage: true,
    });
    report.push({
      width,
      height,
      errors,
      layout: await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        scrollHeight: document.documentElement.scrollHeight,
        viewport: innerWidth,
      })),
      text: await page.locator("body").innerText(),
    });
    await page.close();
  }
  fs.writeFileSync(
    path.join(out, "inspection.json"),
    JSON.stringify(report, null, 2),
  );
  console.log(
    JSON.stringify(
      report.map(({ text, ...r }) => r),
      null,
      2,
    ),
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
