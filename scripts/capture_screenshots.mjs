import { chromium } from "playwright";
import { mkdir, unlink } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = path.join(ROOT, "docs", "screenshots");
const BASE = process.env.SCREENSHOT_BASE_URL ?? "http://127.0.0.1:5174";

const LLM_SETTINGS = {
  apiKey: "screenshot-demo",
  baseUrl: "https://api.deepseek.com/v1",
  model: "deepseek-chat",
  temperature: 0.3,
  useMock: true,
};

const TABS = [
  ["chat", "对话"],
  ["news", "新闻"],
  ["portfolio", "持仓"],
  ["risk", "风控"],
  ["settings", "设置"],
];

const LEGACY = ["market.png", "research.png"];

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
await page.waitForTimeout(2000);

for (const [id, label] of TABS) {
  await page.getByRole("button", { name: label }).first().click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(OUT, `${id}.png`), fullPage: false });
  console.log(`saved ${id}.png`);
}

await browser.close();
console.log(`screenshots saved to ${OUT}/`);
