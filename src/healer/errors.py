"""Public exceptions with messages suitable for CLI users."""


class HealerError(Exception):
    """Base error for the SDK."""


class ConfigurationError(HealerError):
    """Required configuration is absent or invalid."""


class AuthenticationError(HealerError):
    """A credential is invalid, expired, revoked, or for another host."""


class PermissionDeniedError(HealerError):
    """The credential lacks a required scope, binding, role, or entitlement."""


class RateLimitError(HealerError):
    """The service is still rate limiting after bounded retries."""


class UnsafePatchError(HealerError):
    """A proposed patch violates the caller's file boundary."""


class ExternalToolError(HealerError):
    """A subprocess or optional integration failed."""
