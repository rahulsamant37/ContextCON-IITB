import { expect, test } from "@playwright/test";

const API = process.env.API_URL ?? "http://127.0.0.1:8000";
const PROMPT = "We sell AI-driven fleet-maintenance software to logistics companies. Evaluate entry into Germany, 100–1,000 employees, €9,000 ACV, buyers: Head of Fleet / VP Operations / CTO.";

test("replay mission end to end: new -> run -> results -> evidence -> exports -> CRM -> history", async ({ page, request }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && !/favicon|Failed to load resource/.test(m.text()) && errors.push(m.text()));

  // ---- new mission + brief review
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Market-entry research you can audit/ })).toBeVisible();
  await page.getByTestId("prompt-input").fill(PROMPT);
  await page.getByTestId("review-btn").click();
  const card = page.getByTestId("brief-card");
  await expect(card).toBeVisible();
  await expect(card.locator("input").first()).toHaveValue("Germany");
  await page.screenshot({ path: "shots/1-new-mission.png", fullPage: true });

  // offline replay (0 credits), LLM off because the recording was made without it
  await page.getByText("Run options").click();
  await page.getByTestId("option-replay").check();
  const llm = page.getByLabel(/Use AI for wording/);
  if (await llm.isEnabled()) await llm.uncheck();
  await page.getByTestId("run-btn").click();

  // ---- live run page
  await expect(page).toHaveURL(/\/missions\/mission_[0-9a-f]{10}\/run/);
  await expect(page.getByTestId("stepper")).toBeVisible();
  await page.screenshot({ path: "shots/2-run.png", fullPage: true });
  await page.waitForURL(/\/missions\/mission_[0-9a-f]{10}$/, { timeout: 60_000 });
  const mid = page.url().split("/").pop()!;

  // ---- results overview
  await expect(page.getByTestId("mission-title")).toContainText("Logistics in Germany");
  await expect(page.getByTestId("sizing-formula")).toContainText("413");
  await expect(page.getByTestId("sizing-formula")).toContainText("9,000");
  await expect(page.getByText("observed, coverage-limited")).toBeVisible();
  await expect(page.getByText("illustrative, not TAM").first()).toBeVisible();
  await page.screenshot({ path: "shots/3-overview.png", fullPage: true });

  // ---- accounts + drawer + evidence source
  await page.getByTestId("tab-accounts").click();
  const rows = page.getByTestId("account-row");
  await expect(rows).toHaveCount(20);
  await page.getByTestId("account-search").fill("heavy");
  await expect(rows).toHaveCount(1);
  await rows.first().click();
  await expect(page.getByTestId("account-detail")).toBeVisible();
  await expect(page.getByText("Why this score")).toBeVisible();
  await page.getByRole("button", { name: /Headcount \(total\)/ }).first().click();
  const viewer = page.getByTestId("source-viewer").first();
  await expect(viewer).toContainText("supported");
  await expect(viewer).toContainText("headcount.total");
  await page.screenshot({ path: "shots/4-account-drawer.png" });
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("drawer")).toHaveCount(0);

  // ---- buyers, competitors, assumptions
  await page.getByTestId("tab-buyers").click();
  await expect(page.getByTestId("buyers-table")).toContainText("verified");
  await page.getByTestId("tab-competitors").click();
  await expect(page.getByTestId("competitors")).toBeVisible();
  await page.getByTestId("tab-assumptions").click();
  await expect(page.getByText("annual_contract_value").first()).toBeVisible();

  // ---- evidence explorer
  await page.getByTestId("tab-evidence").click();
  await page.getByTestId("evidence-search").fill("Total funding");
  await expect(page.getByTestId("evidence-table").locator("tbody tr").first()).toBeVisible();
  await page.getByTestId("evidence-table").locator("tbody tr").first().click();
  await expect(page.getByTestId("source-viewer")).toBeVisible();
  await page.keyboard.press("Escape");

  // ---- exports (real files)
  await page.getByTestId("tab-exports").click();
  await expect(page.getByTestId("exports")).toContainText("Market entry report (PDF)");
  const pdf = await request.get(`${API}/api/missions/${mid}/artifacts/Market_Entry_Report.pdf`);
  expect(pdf.status()).toBe(200);
  expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
  expect((await request.get(`${API}/api/missions/${mid}/artifacts/marketentry.db`)).status()).toBe(404);
  await page.screenshot({ path: "shots/5-exports.png", fullPage: true });

  // ---- CRM board: stage change persists; drafts are editable and never "sent"
  await page.goto(`/missions/${mid}/crm`);
  await expect(page.getByTestId("board")).toBeVisible();
  const card0 = page.getByTestId("company-card").first();
  const name = await card0.locator("div").first().innerText();
  const sel = card0.getByRole("combobox");
  const target = (await sel.inputValue()) === "Contacted" ? "Meeting" : "Contacted";
  await sel.selectOption(target);
  await expect(page.getByTestId(`col-${target}`)).toContainText(name);
  await page.reload();
  await expect(page.getByTestId(`col-${target}`)).toContainText(name);
  const draft = page.getByTestId("draft-card").first();
  await expect(draft).toContainText("UNSENT");
  const ta = draft.getByRole("textbox");
  const marker = `Reviewed by a human ${Date.now()}`;
  await ta.fill(`${marker}\n\n[DRAFT — UNSENT. Stored locally only; not sent to any external party.]`);
  await draft.getByRole("button", { name: /Save edits/ }).click();
  await page.reload();
  await expect(page.getByTestId("draft-card").first().getByRole("textbox")).toHaveValue(new RegExp(marker));
  await expect(page.getByRole("button", { name: /^send/i })).toHaveCount(0);
  await page.screenshot({ path: "shots/6-crm.png", fullPage: true });

  // ---- history + settings
  await page.goto("/history");
  await expect(page.getByTestId("history-list")).toContainText("Logistics in Germany");
  await page.goto("/settings");
  await expect(page.getByText("Crustdata API")).toBeVisible();
  await expect(page.locator("body")).not.toContainText(process.env.CRUSTDATA_API_KEY ?? "no-key-in-env");
  expect(errors, errors.join("\n")).toEqual([]);
});

test("unrecognised request fails honestly without fabricating results", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("prompt-input").fill("Help me sell stuff somewhere nice.");
  await page.getByTestId("review-btn").click();
  await expect(page.getByText("I could not recognise the country or sector")).toBeVisible();
  await page.getByText("Run options").click();
  await page.getByTestId("option-replay").check();
  await page.getByTestId("run-btn").click();
  await page.waitForURL(/\/missions\/mission_[0-9a-f]{10}$/, { timeout: 60_000 });
  await expect(page.getByText("This mission could not complete")).toBeVisible();
  await expect(page.getByTestId("failure-reasons")).toContainText(/not recognised/);
  await page.screenshot({ path: "shots/7-failed.png" });
});
