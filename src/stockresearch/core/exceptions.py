"""Custom exception hierarchy for StockResearch."""


class StockResearchError(Exception):
    """Base exception for all StockResearch errors."""


class NotFoundError(StockResearchError):
    """Resource not found."""


class ValidationError(StockResearchError):
    """Input validation failed."""


class DataProviderError(StockResearchError):
    """External data source failure."""


class AgentError(StockResearchError):
    """Agent execution failure."""


class LLMConfigError(StockResearchError):
    """LLM is misconfigured (e.g. API key missing while real LLM requested)."""
