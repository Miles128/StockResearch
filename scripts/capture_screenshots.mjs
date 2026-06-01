import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = path.join(ROOT, "docs", "screenshots");
const BASE = "http://127.0.0.1:5174";

const TABS = [
  ["chat", "AI 对话"],
  ["market", "市场行情"],
  ["news", "快讯"],
  ["portfolio", "持仓"],
  ["research", "投研"],
  ["risk", "风控"],
];

await mkdir(OUT, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(BASE, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);

for (const [id, label] of TABS) {
  await page.getByRole("button", { name: new RegExp(label) }).click();
  await page.waitForTimeout(1200);
  await page.screenshot({ path: path.join(OUT, `${id}.png`), fullPage: true });
}

await browser.close();
console.log("screenshots saved to docs/screenshots/");
