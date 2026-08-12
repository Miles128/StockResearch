"""Application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 默认与 .env 的 DATABASE_URL（sqlite:///./main.db）保持一致，避免误建第二个库。
    database_url: str = "sqlite:///./main.db"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_http_proxy: str = ""
    # 默认关闭 mock：漏配 .env 时显式报 LLM 未配置错误，而不是静默输出假研报。
    use_mock_llm: bool = False
    use_mock_market_data: bool = False
    # 博查 AI 联网搜索 API Key（https://open.bochaai.com）。用于新闻兜底搜索。
    bocha_api_key: str = ""
    research_cache_ttl_seconds: int = 86400
    agent_timeout_seconds: int = 45
    # LLM 单次请求超时。必须 < agent_timeout_seconds，否则 agent 已超时但 LLM 仍在跑。
    llm_timeout_seconds: int = 30
    # comma-separated；空 = 回退到本机开发常用源（见 api/app.py），非通配允许全部。
    cors_allowed_origins: str = ""
    # 提示词目录。留空使用项目根目录 prompts/；不存在时回退到内置 prompts。
    prompts_dir: str = ""
    # 是否在 API 进程内启动定时调度（简报/价格告警）。P1 默认 false，应独立运行 worker。
    run_schedulers_in_api: bool = False

    # Kimi Datasource(经本地 kimi CLI 调用,按次消耗 Kimi Code 会员配额)
    kimi_cli_enabled: bool = False
    kimi_cli_path: str = "kimi"
    kimi_cli_timeout_seconds: int = 120
    kimi_live_max_calls_per_day: int = 20

    @property
    def prompts_path(self) -> Path | None:
        if self.prompts_dir:
            path = Path(self.prompts_dir).expanduser().resolve()
            return path if path.is_dir() else None
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
