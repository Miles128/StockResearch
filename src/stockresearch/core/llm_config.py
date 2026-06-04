"""Per-request LLM overrides from client settings."""

from dataclasses import dataclass

from stockresearch.core.config import get_settings


@dataclass(frozen=True)
class LlmOverrides:
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    temperature: float | None = None
    use_mock: bool | None = None

    def effective_api_key(self) -> str:
        if self.api_key and self.api_key.strip():
            return self.api_key.strip()
        return get_settings().llm_api_key

    def effective_base_url(self) -> str:
        if self.base_url and self.base_url.strip():
            return self.base_url.strip().rstrip("/")
        return get_settings().llm_base_url.rstrip("/")

    def effective_model(self) -> str:
        if self.model and self.model.strip():
            return self.model.strip()
        return get_settings().llm_model

    def effective_temperature(self) -> float:
        if self.temperature is not None:
            return max(0.0, min(2.0, self.temperature))
        return 0.3

    def effective_use_mock(self) -> bool:
        if self.use_mock is not None:
            return self.use_mock
        return get_settings().use_mock_llm

    def uses_live_llm(self) -> bool:
        return not self.effective_use_mock() and bool(self.effective_api_key())
