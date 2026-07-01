import { chromium } from "playwright";
import { mkdir, unlink } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = path.join(ROOT, "docs", "screenshots");
const BASE = process.env.SCREENSHOT_BASE_URL ?? "http://127.0.0.1:5174";
const API = process.env.SCREENSHOT_API_URL ?? "http://127.0.0.1:8000";

const LLM_SETTINGS = {
  apiKey: "screenshot-demo",
  baseUrl: "https://api.deepseek.com/v1",
  model: "deepseek-chat",
  temperature: 0.3,
  useMock: true,
};

const MODE_SETTINGS = {
  mode: "advisor",
  riskTolerance: "moderate",
  readingMode: "friendly",
  enableDebate: false,
  enableGlossary: true,
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

const CENTER_TABS = [
  ["focus", "今日关注"],
  ["risk", "风控"],
  ["news", "新闻"],
];

const LEGACY = [
  "portfolio.png",
  "market.png",
  "research.png",
  "chat.png",
  "daily_scan.png",
];

await mkdir(OUT, { recursive: true });
for (const file of LEGACY) {
  try {
    await unlink(path.join(OUT, file));
  } catch {
    /* ignore */
  }
}

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

async function dismissOverlays() {
  for (const label of ["跳过", "Skip", "稍后", "Later"]) {
    const btn = page.getByRole("button", { name: label }).first();
    if (await btn.isVisible().catch(() => false)) {
      await btn.click().catch(() => {});
      await page.waitForTimeout(400);
    }
  }
}

async function loadDemoPortfolio() {
  const res = await page.request.post(`${API}/portfolio/demo`);
  if (!res.ok()) {
    console.warn("demo portfolio load failed:", res.status());
  }
}

await page.goto(BASE, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
await dismissOverlays();
await loadDemoPortfolio();
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(2500);
await dismissOverlays();

// 选中第一只持仓，让「今日关注」有 K 线内容
const firstHolding = page.locator(".lists-holding-select").first();
if (await firstHolding.isVisible().catch(() => false)) {
  await firstHolding.click();
  await page.waitForTimeout(2000);
}

for (const [id, label] of CENTER_TABS) {
  await page.getByRole("button", { name: label, exact: true }).first().click();
  await page.waitForTimeout(1800);
  await page.screenshot({ path: path.join(OUT, `${id}.png`), fullPage: false });
  console.log(`saved ${id}.png`);
}

const copilotColumn = page.locator(".copilot-column");
if (await copilotColumn.isVisible().catch(() => false)) {
  await page.screenshot({ path: path.join(OUT, "copilot.png"), fullPage: false });
  console.log("saved copilot.png");
} else {
  const copilotBtn = page.getByRole("button", { name: "展开 AI 面板" }).first();
  if (await copilotBtn.isVisible().catch(() => false)) {
    await copilotBtn.click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(OUT, "copilot.png"), fullPage: false });
    console.log("saved copilot.png");
  }
}

const settingsBtn = page.getByRole("button", { name: "大模型 API Key / 模型 / 温度" }).first();
if (await settingsBtn.isVisible().catch(() => false)) {
  await settingsBtn.click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(OUT, "settings.png"), fullPage: false });
  console.log("saved settings.png");
}

await browser.close();
console.log(`screenshots saved to ${OUT}/`);
