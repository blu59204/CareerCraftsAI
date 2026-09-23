"""Safe domain errors for the integrations boundary."""


class IntegrationError(Exception):
    """Base integration error safe to translate to an API response."""


class IntegrationDisabledError(IntegrationError):
    pass


class ConnectionNotFoundError(IntegrationError):
    pass


class ConnectionOwnershipError(IntegrationError):
    pass


class ProviderUnavailableError(IntegrationError):
    pass


class InvalidWebhookError(IntegrationError):
    pass


class IntegrationActionError(IntegrationError):
    pass
