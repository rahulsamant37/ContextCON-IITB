import { expect, test, type Page } from "@playwright/test";

function collectErrors(page: Page) {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && !/favicon|Failed to load resource/.test(m.text()) && errors.push(m.text()));
  return errors;
}

for (const theme of ["light", "dark"] as const) {
  test(`landing page (${theme}) presents the product and goes straight into the app`, async ({ page }) => {
    const errors = collectErrors(page);
    if (theme === "dark") await page.addInitScript(() => localStorage.setItem("theme", "dark"));
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Size up a new market");
    await expect(page.getByText("Top companies to approach")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Every number comes with a receipt" })).toBeVisible();
    await expect(page.getByText(/sign in|sign up|log in/i)).toHaveCount(0);
    await page.screenshot({ path: `shots/0-landing-${theme}.png`, fullPage: true });
    await page.getByTestId("hero-cta").first().click();
    await expect(page).toHaveURL(/\/research\/new$/);
    await expect(page.getByTestId("user-name")).toHaveText("Guest");
    await page.screenshot({ path: `shots/0-new-${theme}.png`, fullPage: true });
    expect(errors, errors.join("\n")).toEqual([]);
  });
}

test("guest runs the demo end to end: results, sources, downloads, pipeline", async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto("/research");
  await expect(page.getByText("Welcome! Let's research your first market")).toBeVisible();
  await expect(page.getByTestId("guest-badge")).toContainText("saved in this browser");
  await page.screenshot({ path: "shots/1-welcome.png", fullPage: true });
  await page.getByTestId("welcome-demo").click();

  await expect(page.getByTestId("f-country")).toHaveValue("Germany");
  await expect(page.getByText("Free (demo)")).toBeVisible();
  await page.getByTestId("run-btn").click();
  await expect(page).toHaveURL(/\/research\/mission_[0-9a-f]{10}\/run/);
  await expect(page.getByTestId("stepper")).toBeVisible();
  await page.screenshot({ path: "shots/2-run.png", fullPage: true });
  await page.waitForURL(/\/research\/mission_[0-9a-f]{10}$/, { timeout: 60_000 });
  const mid = page.url().split("/").pop()!;

  await expect(page.getByTestId("mission-title")).toContainText("Logistics in Germany");
  await expect(page.getByTestId("recommendation")).toBeVisible();
  await expect(page.getByText("€3.7M")).toBeVisible();
  await page.screenshot({ path: "shots/3-overview.png", fullPage: true });

  await page.getByTestId("tab-companies").click();
  await expect(page.getByTestId("account-row")).toHaveCount(20);
  await page.getByTestId("account-search").fill("heavy");
  await expect(page.getByTestId("account-row")).toHaveCount(1);
  await page.screenshot({ path: "shots/4-companies.png" });
  await page.getByTestId("account-row").first().click();
  await expect(page.getByTestId("account-detail")).toBeVisible();
  await page.getByRole("button", { name: /^Headcount: / }).first().click();
  await expect(page.getByTestId("source-viewer").first()).toContainText("Confirmed");
  await page.keyboard.press("Escape");

  await page.getByTestId("tab-people").click();
  await expect(page.getByTestId("buyers-table")).toContainText("Confirmed");
  await page.getByTestId("tab-sources").click();
  await page.getByTestId("evidence-search").fill("Total funding");
  await page.getByTestId("evidence-table").locator("tbody tr").first().click();
  await expect(page.getByTestId("source-viewer")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByTestId("tab-downloads").click();
  await expect(page.getByTestId("exports")).toContainText("Market entry report");
  const pdf = await page.request.get(`/api/missions/${mid}/artifacts/Market_Entry_Report.pdf`);
  expect(pdf.status()).toBe(200);
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
  const sse = await page.request.get(`/api/missions/${mid}/events`);
  expect(sse.status()).toBe(200);
  expect(await sse.text()).toContain('"type": "end"');

  await page.goto(`/research/${mid}/pipeline`);
  await expect(page.getByTestId("board")).toBeVisible();
  const crm = await (await page.request.get(`/api/missions/${mid}/crm`)).json();
  const draft = crm.tasks.find((t: { task_type: string }) => t.task_type === "outreach_draft");
  const company = crm.companies.find((c: { id: number }) => c.id === draft.company_id);
  await page.getByTestId("company-card").filter({ hasText: company.name }).click();
  await page.getByTestId("stage-select").selectOption("Contacted");
  await expect(page.getByText("Moved to Contacted")).toBeVisible();
  const marker = `Reviewed by a person ${Date.now()}`;
  await page.getByTestId("draft-card").first().getByRole("textbox").fill(`${marker}\n\n[DRAFT — UNSENT.]`);
  await page.getByTestId("draft-card").first().getByRole("button", { name: "Save edits" }).click();
  await expect(page.getByText("Draft saved")).toBeVisible();
  await page.screenshot({ path: "shots/6-pipeline-panel.png" });
  await page.keyboard.press("Escape");
  await page.reload();
  await expect(page.getByTestId("col-Contacted")).toContainText(company.name);
  await page.screenshot({ path: "shots/7-pipeline.png", fullPage: true });

  await page.goto("/research");
  await expect(page.getByTestId("history-list")).toContainText("Logistics in Germany");
  await page.screenshot({ path: "shots/8-list.png", fullPage: true });
  expect(errors, errors.join("\n")).toEqual([]);
});

test("dark mode: app screens render with readable text", async ({ page }) => {
  const errors = collectErrors(page);
  await page.addInitScript(() => localStorage.setItem("theme", "dark"));
  await page.goto("/research/new?example=germany");
  await page.getByTestId("run-btn").click();
  await page.waitForURL(/\/research\/mission_[0-9a-f]{10}$/, { timeout: 60_000 });
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.screenshot({ path: "shots/d-overview.png", fullPage: true });
  await page.getByTestId("tab-companies").click();
  await page.screenshot({ path: "shots/d-companies.png" });
  expect(errors, errors.join("\n")).toEqual([]);
});

test("each browser gets its own private guest workspace", async ({ browser }) => {
  const a = await (await browser.newContext()).newPage();
  await a.goto("/research/new?example=germany");
  await a.getByTestId("run-btn").click();
  await a.waitForURL(/\/research\/mission_[0-9a-f]{10}$/, { timeout: 60_000 });
  const mid = a.url().split("/").pop()!;
  await a.goto("/research");
  await expect(a.getByTestId("history-list")).toContainText("Logistics in Germany");  // persists for the same browser
  const b = await (await browser.newContext()).newPage();
  await b.goto("/research");
  await expect(b.getByText("Welcome! Let's research your first market")).toBeVisible();
  await b.goto(`/research/${mid}`);
  await expect(b.getByText("Couldn't load this research")).toBeVisible();
  expect((await b.request.get(`/api/missions/${mid}`)).status()).toBe(404);
});

test("guided form validates before starting", async ({ page }) => {
  await page.goto("/research/new");
  await page.getByTestId("run-btn").click();
  await expect(page.getByText("Please complete the highlighted fields.")).toBeVisible();
  await expect(page.getByText("Choose a country.")).toBeVisible();
  await expect(page).toHaveURL(/\/research\/new$/);
});

test("unrecognised free-text request fails honestly without fabricating results", async ({ page }) => {
  await page.goto("/research/new");
  await page.getByRole("radio", { name: "Describe in your own words" }).click();
  await page.getByTestId("prompt-input").fill("Help me sell stuff somewhere nice.");
  await page.getByTestId("review-btn").click();
  await expect(page.getByText("We couldn't recognise the country or industry")).toBeVisible();
  await page.getByText("Options").click();
  await page.getByTestId("option-replay").check();
  await page.getByTestId("run-btn").click();
  await page.waitForURL(/\/research\/mission_[0-9a-f]{10}$/, { timeout: 60_000 });
  await expect(page.getByText("This research couldn't be completed")).toBeVisible();
});
