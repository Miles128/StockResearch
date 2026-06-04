"""Custom exception hierarchy for StockResearch."""


class StockResearchError(Exception):
    """Base exception for all StockResearch errors."""


class NotFoundError(StockResearchError):
    """Resource not found."""


class AuthenticationError(StockResearchError):
    """Authentication failed."""


class AuthorizationError(StockResearchError):
    """Authorization failed."""


class ValidationError(StockResearchError):
    """Input validation failed."""


class DataProviderError(StockResearchError):
    """External data source failure."""


class AgentError(StockResearchError):
    """Agent execution failure."""
