"""Custom exception hierarchy for InvesBao."""


class InvesBaoError(Exception):
    """Base exception for all InvesBao errors."""


class NotFoundError(InvesBaoError):
    """Resource not found."""


class AuthenticationError(InvesBaoError):
    """Authentication failed."""


class AuthorizationError(InvesBaoError):
    """Authorization failed."""


class ValidationError(InvesBaoError):
    """Input validation failed."""


class DataProviderError(InvesBaoError):
    """External data source failure."""


class AgentError(InvesBaoError):
    """Agent execution failure."""
