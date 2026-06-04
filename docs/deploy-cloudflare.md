# 部署到 Cloudflare Pages

StockResearch **前端**部署在 Cloudflare Pages；**Python 后端**需单独部署（Railway / Fly.io / VPS 等），通过 `BACKEND_URL` 代理，**不要把大模型 API Key 写在 Cloudflare 或后端环境变量里**（由用户在浏览器设置里填写）。

## 架构

```text
用户浏览器
  ├─ localStorage：API Key / Base URL / 模型（仅本机）
  └─ HTTPS → Cloudflare Pages（静态 + Functions）
         └─ /api/*  → BACKEND_URL（你的 FastAPI 服务）
```

## 1. 部署后端 API

```bash
# 生产环境 .env 示例（勿填 LLM_API_KEY）
USE_MOCK_LLM=false
USE_MOCK_MARKET_DATA=false
LLM_API_KEY=
SECRET_KEY=<随机长字符串>
```

启动后确保可访问：`https://<你的-api>/health`

## 2. 构建前端

```bash
cd web
npm ci
npm run build
```

可选：若 API 与 Pages **不同域**且不用 Functions 代理，构建时设置：

```bash
VITE_API_BASE_URL=https://api.example.com npm run build
```

默认同域走 `/api/v1` + Pages Function 转发。

## 3. 部署 Pages

**自动部署（推荐）**：Cloudflare **Connect Git**，push `main` 即构建发布。与 Fly 香港联动见 [deploy-auto.md](deploy-auto.md)。

手动部署：

```bash
cd web
npx wrangler pages deploy dist --project-name stockresearch
```

或在 Cloudflare Dashboard：**Workers & Pages → Create → Pages → Connect Git**

| 设置项 | 值 |
|--------|-----|
| 构建命令 | `cd web && npm ci && npm run build` |
| 输出目录 | `web/dist` |
| Root directory | 仓库根目录 |

## 4. 环境变量（Cloudflare Dashboard）

| 变量 | 必填 | 说明 |
|------|------|------|
| `BACKEND_URL` | 是 | 后端根地址，如 `https://api.stockresearch.example.com` |
| `LLM_API_KEY` | **不要配置** | 密钥仅存在用户浏览器 |

## 5. 新用户首次打开

未配置大模型时，会自动弹出设置向导；测试通过并保存后才能使用。Key 不会进入构建产物或 Git。

## 6. 本地预览 Pages 构建

```bash
cd web
npm run build
npx wrangler pages dev dist --env BACKEND_URL=http://127.0.0.1:8000
```
