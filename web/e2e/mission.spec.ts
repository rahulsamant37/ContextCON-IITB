import { expect, test } from "@playwright/test";

const API = process.env.API_URL ?? "http://127.0.0.1:8000";

test("guided research end to end in demo mode: form -> progress -> results -> sources -> downloads -> pipeline", async ({ page, request }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && !/favicon|Failed to load resource/.test(m.text()) && errors.push(m.text()));

  // ---- new research (example prefilled, demo mode = recorded data, 0 credits)
  await page.goto("/new?example=germany");
  await expect(page.getByRole("heading", { name: "New research" })).toBeVisible();
  await expect(page.getByTestId("f-country")).toHaveValue("Germany");
  await expect(page.getByTestId("brief-summary")).toContainText("Logistics");
  await expect(page.getByTestId("brief-summary")).toContainText("Germany");
  await expect(page.getByText("Free (demo)")).toBeVisible();
  await page.screenshot({ path: "shots/1-new.png", fullPage: true });
  await page.getByTestId("run-btn").click();

  // ---- progress
  await expect(page).toHaveURL(/\/missions\/mission_[0-9a-f]{10}\/run/);
  await expect(page.getByTestId("stepper")).toBeVisible();
  await page.screenshot({ path: "shots/2-run.png", fullPage: true });
  await page.waitForURL(/\/missions\/mission_[0-9a-f]{10}$/, { timeout: 60_000 });
  const mid = page.url().split("/").pop()!;

  // ---- overview
  await expect(page.getByTestId("mission-title")).toContainText("Logistics in Germany");
  await expect(page.getByTestId("recommendation")).toBeVisible();
  await expect(page.getByText("Estimated market value")).toBeVisible();
  await expect(page.getByText("€3.7M")).toBeVisible();
  await page.screenshot({ path: "shots/3-overview.png", fullPage: true });

  // ---- companies + panel + a source
  await page.getByTestId("tab-companies").click();
  const rows = page.getByTestId("account-row");
  await expect(rows).toHaveCount(20);
  await page.getByTestId("account-search").fill("heavy");
  await expect(rows).toHaveCount(1);
  await page.screenshot({ path: "shots/4-companies.png", fullPage: true });
  await rows.first().click();
  await expect(page.getByTestId("account-detail")).toBeVisible();
  await expect(page.getByText("Why it's a match")).toBeVisible();
  await page.getByRole("button", { name: /^Headcount: / }).first().click();
  const viewer = page.getByTestId("source-viewer").first();
  await expect(viewer).toContainText("Confirmed");
  await expect(viewer).toContainText("headcount.total");
  await page.screenshot({ path: "shots/5-company-panel.png" });
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("drawer")).toHaveCount(0);

  // ---- other tabs
  await page.getByTestId("tab-people").click();
  await expect(page.getByTestId("buyers-table")).toContainText("Confirmed");
  await page.getByTestId("tab-competitors").click();
  await expect(page.getByTestId("competitors")).toBeVisible();
  await page.getByTestId("tab-sources").click();
  await page.getByTestId("evidence-search").fill("Total funding");
  await page.getByTestId("evidence-table").locator("tbody tr").first().click();
  await expect(page.getByTestId("source-viewer")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByTestId("tab-brief").click();
  await expect(page.getByText("How we interpreted it")).toBeVisible();
  await page.getByTestId("tab-downloads").click();
  await expect(page.getByTestId("exports")).toContainText("Market entry report");
  const pdf = await request.get(`${API}/api/missions/${mid}/artifacts/Market_Entry_Report.pdf`);
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");

  // ---- pipeline: stage change persists, draft edit persists, no send
  await page.goto(`/missions/${mid}/crm`);
  await expect(page.getByTestId("board")).toBeVisible();
  const crm = await (await request.get(`${API}/api/missions/${mid}/crm`)).json();
  const draft = crm.tasks.find((t: { task_type: string }) => t.task_type === "outreach_draft");
  const company = crm.companies.find((c: { id: number }) => c.id === draft.company_id);
  await page.getByTestId("company-card").filter({ hasText: company.name }).click();
  const target = company.stage === "Contacted" ? "Meeting" : "Contacted";
  await page.getByTestId("stage-select").selectOption(target);
  await expect(page.getByText(`Moved to ${target}`)).toBeVisible();
  const marker = `Reviewed by a person ${Date.now()}`;
  await page.getByTestId("draft-card").first().getByRole("textbox").fill(`${marker}\n\n[DRAFT — UNSENT.]`);
  await page.getByTestId("draft-card").first().getByRole("button", { name: "Save edits" }).click();
  await expect(page.getByText("Draft saved")).toBeVisible();
  await page.screenshot({ path: "shots/6-pipeline-panel.png" });
  await page.keyboard.press("Escape");
  await page.reload();
  await expect(page.getByTestId(`col-${target}`)).toContainText(company.name);
  await page.getByTestId("company-card").filter({ hasText: company.name }).click();
  await expect(page.getByTestId("draft-card").first().getByRole("textbox")).toHaveValue(new RegExp(marker));
  await expect(page.getByRole("button", { name: /^send/i })).toHaveCount(0);
  await page.keyboard.press("Escape");
  await page.screenshot({ path: "shots/7-pipeline.png", fullPage: true });

  // ---- research list + settings
  await page.goto("/");
  await expect(page.getByTestId("history-list")).toContainText("Logistics in Germany");
  await page.screenshot({ path: "shots/8-list.png", fullPage: true });
  await page.goto("/settings");
  await expect(page.getByText("Company and people data")).toBeVisible();
  expect(errors, errors.join("\n")).toEqual([]);
});

test("guided form validates before starting", async ({ page }) => {
  await page.goto("/new");
  await page.getByTestId("run-btn").click();
  await expect(page.getByText("Please complete the highlighted fields.")).toBeVisible();
  await expect(page.getByText("Describe your product in a few words.")).toBeVisible();
  await expect(page.getByText("Choose a country.")).toBeVisible();
  await expect(page).toHaveURL(/\/new$/);
});

test("unrecognised free-text request fails honestly without fabricating results", async ({ page }) => {
  await page.goto("/new");
  await page.getByRole("radio", { name: "Describe in your own words" }).click();
  await page.getByTestId("prompt-input").fill("Help me sell stuff somewhere nice.");
  await page.getByTestId("review-btn").click();
  await expect(page.getByText("We couldn't recognise the country or industry")).toBeVisible();
  await page.getByText("Options").click();
  await page.getByTestId("option-replay").check();
  await page.getByTestId("run-btn").click();
  await page.waitForURL(/\/missions\/mission_[0-9a-f]{10}$/, { timeout: 60_000 });
  await expect(page.getByText("This research couldn't be completed")).toBeVisible();
  await expect(page.getByTestId("failure-reasons")).toContainText(/not recognised/);
});
