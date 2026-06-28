"""Application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./stockresearch.db"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_http_proxy: str = ""
    use_mock_llm: bool = True
    # 博查 AI 联网搜索 API Key（https://open.bochaai.com）。用于新闻兜底搜索。
    bocha_api_key: str = ""
    research_cache_ttl_seconds: int = 86400
    agent_timeout_seconds: int = 45
    # LLM 单次请求超时。必须 < agent_timeout_seconds，否则 agent 已超时但 LLM 仍在跑。
    llm_timeout_seconds: int = 30
    cors_allowed_origins: str = ""  # comma-separated, empty = allow all


@lru_cache
def get_settings() -> Settings:
    return Settings()
