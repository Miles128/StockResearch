# StockResearch Desktop (Tauri 2)

macOS / Windows 桌面壳：启动本机 FastAPI（托管 `web/dist`），窗口打开 `http://127.0.0.1:8000`。

## 前置

- Rust（`rustup`）+ 平台 WebView（macOS 自带；Windows 需 WebView2）
- 本机已安装 [`uv`](https://github.com/astral-sh/uv)
- 仓库根已 `uv sync`
- 前端已构建：`cd web && npm run build`

## 开发运行

```bash
cd desktop
npm install
npm run dev
```

可选环境变量：

| 变量 | 说明 |
|------|------|
| `STOCKRESEARCH_ROOT` | 仓库根路径（默认从 `desktop/src-tauri` 上推两级） |
| `STOCKRESEARCH_UV` | `uv` 可执行文件路径 |
| `STOCKRESEARCH_DESKTOP_PORT` | API 端口（默认 `8000`；被占用时可设 `18000`） |
| `STOCKRESEARCH_DESKTOP_WORKER=1` | 同时拉起 `stockresearch worker`（默认关） |

若 `127.0.0.1:8000` 已有健康服务，壳会复用、退出时不杀。

## 打包

```bash
cd web && npm run build
cd ../desktop && npm run build
```

产物在 `desktop/src-tauri/target/release/bundle/`（`.dmg` / `.msi` 等）。
MVP **不**捆绑 Python：目标机器仍需可访问同一仓库 + `uv`。

## 应用图标

源图：`branding/app-icon.png`（金融研究终端：K 线 + 研究取景，海军蓝/青绿底 + 琥珀高点）。
重新生成各尺寸：

```bash
cd desktop && npx tauri icon branding/app-icon.png
```

## 非目标

移动端；Electron；把数据源/模型打进安装包。
