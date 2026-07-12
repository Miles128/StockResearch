import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = path.join(ROOT, "docs", "screenshots");
const BASE = process.env.SCREENSHOT_BASE_URL ?? "http://127.0.0.1:5174";
const API = process.env.SCREENSHOT_API_URL ?? "http://127.0.0.1:8000/api/v1";
const QUERY = "对贵州茅台做深度分析";

const LLM_SETTINGS = {
  apiKey: "screenshot-demo",
  baseUrl: "https://api.deepseek.com/v1",
  model: "deepseek-chat",
  temperature: 0.3,
  useMock: true,
};

const MODE_SETTINGS = {
  mode: "research",
  riskTolerance: "moderate",
  readingMode: "standard",
  enableDebate: false,
  enableGlossary: false,
  maxSignals: 5,
  onboarded: true,
  enableMasterCommentary: false,
  selectedMasters: ["buffett", "munger", "burry"],
  customMasters: [],
  customGlossary: [],
  holdingsView: "table",
  quoteRefreshMinutes: 10,
  briefingAutoEnabled: true,
  uiPollingEnabled: false,
};

await mkdir(OUT, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  locale: "zh-CN",
});
await context.addInitScript(
  ({ llm, mode }) => {
    localStorage.setItem("stockresearch.llm.settings", JSON.stringify(llm));
    localStorage.setItem("stockresearch.locale", "zh");
    localStorage.setItem("stockresearch.mode.settings", JSON.stringify(mode));
  },
  { llm: LLM_SETTINGS, mode: MODE_SETTINGS },
);

const page = await context.newPage();
page.setDefaultTimeout(15_000);

async function dismissOverlays() {
  for (const label of ["跳过", "Skip", "稍后", "Later"]) {
    const btn = page.getByRole("button", { name: label }).first();
    if (await btn.isVisible().catch(() => false)) {
      await btn.click().catch(() => {});
      await page.waitForTimeout(300);
    }
  }
}

await page.goto(BASE, { waitUntil: "load" });
await page.waitForTimeout(1200);
await dismissOverlays();

const demo = await page.request.post(`${API}/portfolio/demo`);
if (!demo.ok()) console.warn("demo portfolio load failed:", demo.status());
await page.reload({ waitUntil: "load" });
await page.waitForTimeout(1800);
await dismissOverlays();

// Open 茅台 focus via header search
const search = page.locator(".chrome-search-input");
await search.fill("600519");
await page.waitForTimeout(800);
const candidate = page.getByRole("button", { name: /贵州茅台|600519/ }).first();
if (await candidate.isVisible().catch(() => false)) {
  await candidate.click();
} else {
  await search.press("Enter");
}
await page.waitForTimeout(2000);

const copilotBtn = page.getByRole("button", { name: "展开 AI 面板" }).first();
if (await copilotBtn.isVisible().catch(() => false)) {
  await copilotBtn.click();
  await page.waitForTimeout(500);
}

const input = page.locator(".chat-input-textarea");
await input.click();
await input.fill(QUERY);
await input.press("Enter");

// Confirm stock / route if asked
for (const label of ["贵州茅台", "600519", "推荐流程", "专业投研", "Preset", "preset"]) {
  const pick = page.getByRole("button", { name: new RegExp(label) }).first();
  if (await pick.isVisible({ timeout: 1500 }).catch(() => false)) {
    await pick.click().catch(() => {});
    await page.waitForTimeout(400);
  }
}

const result = page.locator(
  ".light-research-card, .dimension-card-fold, .dimension-cards-grid, .stream-section-title",
);
try {
  await result.first().waitFor({ state: "visible", timeout: 180_000 });
  // Let streaming settle / scores appear
  await page
    .locator(".dimension-card-fold .stat-pill, .light-research-card .stat-pill")
    .first()
    .waitFor({ state: "visible", timeout: 120_000 })
    .catch(() => {});
  await page.waitForTimeout(2500);
} catch (e) {
  console.warn("timed out waiting for research UI:", String(e));
}

const folds = page.locator(".dimension-card-fold");
const count = await folds.count();
for (let i = 0; i < Math.min(count, 2); i++) {
  const fold = folds.nth(i);
  if ((await fold.getAttribute("open")) == null) {
    await fold.locator("summary").click().catch(() => {});
  }
}
await page.waitForTimeout(600);

const outPath = path.join(OUT, "moutai-analysis.png");
await page.screenshot({ path: outPath, fullPage: false });
console.log(`saved ${outPath}`);

await browser.close();
