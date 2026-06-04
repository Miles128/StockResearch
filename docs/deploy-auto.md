# StockResearch — Pages + Fly 香港自动部署

两端都可以在 **push 到 `main`** 后自动发布，无需每次手动 `wrangler` / `fly deploy`。

```text
git push main
  ├─ Cloudflare Pages（连 GitHub）→ 构建 web/dist
  └─ GitHub Actions deploy-fly.yml → fly deploy → hkg
```

---

## 一、Cloudflare Pages（前端，推荐连 Git）

在 [Cloudflare Dashboard](https://dash.cloudflare.com) → **Workers & Pages** → **Create** → **Pages** → **Connect to Git**，选本仓库。

| 配置项 | 值 |
|--------|-----|
| Production branch | `main` |
| 构建命令 | `cd web && npm ci && npm run build` |
| 构建输出目录 | `web/dist` |
| 根目录 | `/`（仓库根） |

**环境变量（Production）：**

| 变量 | 示例 |
|------|------|
| `BACKEND_URL` | `https://stockresearch-api.fly.dev`（与 Fly 应用名一致，**不要**末尾 `/`） |

保存后：每次合并到 `main` 会自动构建并发布；预览分支可选 PR 预览。

> 也可用 GitHub Actions + `wrangler pages deploy`，但 **连 Git 更简单**，一般不必再写 workflow。

---

## 二、Fly.io 香港（后端，GitHub Actions）

### 1. 一次性初始化（本地）

```bash
# 安装 https://fly.io/docs/hands-on/install-flyctl/
fly auth login

# 应用名与 fly.toml 中 app 一致，可改成你的
fly apps create stockresearch-api

# 持久化 SQLite（香港）
fly volumes create stockresearch_data --region hkg --size 1 --app stockresearch-api

# 密钥（生产必改）
fly secrets set SECRET_KEY="$(openssl rand -hex 32)" --app stockresearch-api
```

首次也可直接推送 `main`，由 Actions 执行 `fly deploy`（需已创建 app 与 volume）。

### 2. GitHub Secret

仓库 **Settings → Secrets and variables → Actions** → **New repository secret**：

| Name | 值 |
|------|-----|
| `FLY_API_TOKEN` | [Fly 控制台](https://fly.io/user/personal_access_tokens) 生成的 Personal Access Token |

### 3. 自动触发

工作流：`.github/workflows/deploy-fly.yml`

- **触发**：`main` 分支 push，且改动 `src/`、`Dockerfile`、`pyproject.toml`、`fly.toml` 等
- **动作**：`flyctl deploy --remote-only` 到 **hkg**

手动触发：Actions 页 → **Deploy API (Fly.io hkg)** → **Run workflow**。

### 4. 验证

```bash
curl https://stockresearch-api.fly.dev/health
```

Cloudflare 里 `BACKEND_URL` 指向同一地址后，前端 `/api/v1/*` 经 Functions 转发到 Fly。

---

## 三、推荐顺序（首次上线）

1. Fly 创建 app + volume + `SECRET_KEY`
2. 配置 `FLY_API_TOKEN`，push `main` 部署 API
3. Cloudflare Pages 连 Git，设 `BACKEND_URL`
4. push 前端改动 → Pages 自动构建

之后日常只需 **git push**，两端各自更新。

---

## 四、费用与注意

- Fly 免费档政策会变，见 [fly.io/docs/about/pricing](https://fly.io/docs/about/pricing)；`min_machines_running = 0` 可在空闲时停机省资源，首请求可能冷启动。
- **不要**在 Fly / Cloudflare 配置 `LLM_API_KEY`（用户浏览器填写）。
- 改 `fly.toml` 里 `app` 名称时，同步改 Cloudflare 的 `BACKEND_URL`。
