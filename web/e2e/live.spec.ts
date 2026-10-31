import { expect, test } from "@playwright/test";

// Spends real Crustdata credits (~80). Run with: LIVE=1 pnpm exec playwright test e2e/live.spec.ts
test.skip(!process.env.LIVE, "set LIVE=1 to run a real mission");

test("live mission through the web app (real Crustdata + LLM)", async ({ page }) => {
  test.setTimeout(420_000);
  await page.goto("/");
  await page.getByRole("button", { name: "Germany logistics" }).click();
  await page.getByText("Run options").click();
  await page.getByText("Simulate one API failure").click(); // also exercise retry handling live
  const t0 = Date.now();
  await page.getByTestId("run-btn").click();
  await expect(page).toHaveURL(/\/run$/);
  await expect(page.getByTestId("stepper")).toBeVisible();
  await page.waitForTimeout(8000);
  await page.screenshot({ path: "shots/live-1-running.png", fullPage: true });
  await page.waitForURL(/\/missions\/mission_[0-9a-f]{10}$/, { timeout: 360_000 });
  const secs = Math.round((Date.now() - t0) / 1000);
  console.log(`live mission finished in ${secs}s`);
  await expect(page.getByTestId("mission-title")).toContainText("Logistics in Germany");
  await expect(page.getByTestId("sizing-formula")).toContainText("€9,000");
  await page.screenshot({ path: "shots/live-2-results.png", fullPage: true });
  await page.getByTestId("tab-exports").click();
  await expect(page.getByTestId("exports")).toContainText("Market entry report (PDF)");
  await page.getByTestId("tab-buyers").click();
  const text = await page.getByTestId("buyers-table").innerText();
  expect(text).not.toMatch(/assistant/i);
  console.log(text.split("\n").slice(0, 12).join(" | "));
});
