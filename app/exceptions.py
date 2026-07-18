class OllamaRouterError(Exception):
    pass


class QuotaExceeded(OllamaRouterError):
    pass


class AuthenticationFailed(OllamaRouterError):
    pass


class RateLimited(OllamaRouterError):
    pass


class NetworkFailure(OllamaRouterError):
    pass


class ServerError(OllamaRouterError):
    pass


class AccountDisabled(OllamaRouterError):
    pass


class UnknownError(OllamaRouterError):
    pass


class AllAccountsUnhealthy(OllamaRouterError):
    pass
