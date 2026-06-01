# 投小宝 InvesBao

面向 A 股个人投资者的 Multi-Agent AI 投研助手（Phase 1 MVP）。

## 功能

- **对话 Agent**：意图路由 → 新闻 / 投研 / 风控 / 闲聊
- **新闻分析**：快讯抓取、NER、情感标签、一句话解读、持仓关联
- **投研分析**：基本面 / 技术面 / 情绪面 / 筹码面四维并行 + 投票聚合
- **智能风控**：规则引擎（止损、集中度、黑天鹅）+ 人话翻译
- **用户系统**：注册登录、持仓、自选股

## 快速开始

### 后端

```bash
cd "/Users/sihai/Documents/My Projects/InvesBao"
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn invesbao.api.app:app --reload --app-dir src
```

API 文档：http://localhost:8000/docs

**UI 请访问 http://localhost:5174（不是 8000）**。直接打开 `http://localhost:8000/` 只会看到 API 提示，不是界面。

### 前端

```bash
cd web
npm install
npm run dev
```

访问：http://localhost:5174

### Docker

```bash
docker compose up --build
```

### 测试

```bash
pytest
ruff check src tests
mypy src/invesbao --strict
```

## 环境变量

见 `.env.example`。MVP 默认 `USE_MOCK_LLM=true` 和 `USE_MOCK_MARKET_DATA=true`，无需外部 API 即可运行。

## 免责声明

本产品所有 AI 输出仅供学习参考，不构成投资建议。
