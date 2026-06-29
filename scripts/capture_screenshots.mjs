import { chromium } from "playwright";
import { mkdir, unlink } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = path.join(ROOT, "docs", "screenshots");
const BASE = process.env.SCREENSHOT_BASE_URL ?? "http://127.0.0.1:5174";

// 模拟一个可用的 LLM 配置，避免 Onboarding 拦截首屏
const LLM_SETTINGS = {
  apiKey: "screenshot-demo",
  baseUrl: "https://api.deepseek.com/v1",
  model: "deepseek-chat",
  temperature: 0.3,
  useMock: true,
};

// 三 Tab 主内容区（中文 locale）
const CENTER_TABS = [
  ["focus", "今日关注"],
  ["risk", "风控"],
  ["news", "新闻"],
];

// 历史遗留文件，删除避免陈旧截图
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
await context.addInitScript((settings) => {
  localStorage.setItem("stockresearch.llm.settings", JSON.stringify(settings));
  localStorage.setItem("stockresearch.locale", "zh");
}, LLM_SETTINGS);

const page = await context.newPage();
await page.goto(BASE, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);

async function dismissOverlays() {
  for (const label of ["跳过", "Skip", "稍后", "Later"]) {
    const btn = page.getByRole("button", { name: label }).first();
    if (await btn.isVisible().catch(() => false)) {
      await btn.click().catch(() => {});
    }
  }
}

await dismissOverlays();
await page.waitForTimeout(500);

for (const [id, label] of CENTER_TABS) {
  await page.getByRole("button", { name: label }).first().click();
  await page.waitForTimeout(1800);
  await page.screenshot({ path: path.join(OUT, `${id}.png`), fullPage: false });
  console.log(`saved ${id}.png`);
}

const copilotBtn = page.getByRole("button", { name: "AI 对话" }).first();
if (await copilotBtn.isVisible().catch(() => false)) {
  await copilotBtn.click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(OUT, "copilot.png"), fullPage: false });
  console.log("saved copilot.png");
  await copilotBtn.click().catch(() => {});
  await page.waitForTimeout(500);
}

const settingsBtn = page.getByRole("button", { name: "设置" }).first();
if (await settingsBtn.isVisible().catch(() => false)) {
  await settingsBtn.click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(OUT, "settings.png"), fullPage: false });
  console.log("saved settings.png");
}

await browser.close();
console.log(`screenshots saved to ${OUT}/`);
