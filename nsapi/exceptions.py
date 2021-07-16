"""Exceptions defined and used by this package."""


class APIError(Exception):
    """Error interacting with NationStates API."""


class AuthError(APIError):
    """Error with authentication for NS API."""


class ResourceError(APIError, ValueError):
    """Error with retrieving a resource from NS API."""
