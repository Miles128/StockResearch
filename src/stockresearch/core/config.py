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
    use_mock_market_data: bool = False
    research_cache_ttl_seconds: int = 86400
    agent_timeout_seconds: int = 45


@lru_cache
def get_settings() -> Settings:
    return Settings()
