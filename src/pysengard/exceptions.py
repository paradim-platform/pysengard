"""Errors raised by the client.

Every error of the API is an :class:`APIError`, with the HTTP status and the ``detail`` the API answered. The subclasses match
the statuses the Isengard REST API documents, so a caller can catch, e.g., :class:`ConflictError` to reuse an album whose name
is already taken in the project.
"""

from __future__ import annotations

from typing import Any

import httpx


class IsengardError(Exception):
    """Base class of every error raised by pysengard."""


class IsengardConnectionError(IsengardError):
    """The server could not be reached, or did not answer in time."""


class APIError(IsengardError):
    """The API answered with an error status."""

    status_code: int

    def __init__(self, message: str, *, status_code: int, detail: Any = None, response: httpx.Response | None = None):
        super().__init__(message)
        self.status_code = status_code
        # A string for the errors of Isengard, a list of pydantic errors for a request the API could not validate.
        self.detail = detail
        self.response = response


class BadRequestError(APIError):
    """400: a malformed request."""


class AuthenticationError(APIError):
    """401: no token, or an unknown, expired or revoked one."""


class PermissionDeniedError(APIError):
    """403: the album is visible, but the caller lacks the permission (or the access token the scope)."""


class NotFoundError(APIError):
    """404: the resource does not exist, or is not visible to the caller."""


class ConflictError(APIError):
    """409: e.g. a name already used in the project, or a user already a member of the album."""


class UnprocessableEntityError(APIError):
    """422: the request is well-formed but refused (validation error, frozen album, ...)."""


class RateLimitError(APIError):
    """429: too many requests (Isengard's nginx limits ``/api/v1/`` per client IP)."""


class ServerError(APIError):
    """5xx: an error of the server."""


_BY_STATUS: dict[int, type[APIError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    422: UnprocessableEntityError,
    429: RateLimitError,
}


def _format_detail(detail: Any) -> str:
    if isinstance(detail, list):
        # django-ninja's validation errors: [{"type": ..., "loc": [...], "msg": ...}, ...]
        parts = []
        for error in detail:
            if isinstance(error, dict):
                loc = '.'.join(str(part) for part in error.get('loc', ()))
                parts.append(f'{loc}: {error.get("msg", error)}' if loc else str(error.get('msg', error)))
            else:
                parts.append(str(error))
        return '; '.join(parts)
    return str(detail)


def error_from_response(response: httpx.Response) -> APIError:
    """Build the :class:`APIError` matching an error response."""
    try:
        body = response.json()
    except ValueError:
        body = None
    detail = body.get('detail', body) if isinstance(body, dict) else body
    if detail is None:
        detail = response.text or response.reason_phrase
    status = response.status_code
    cls = _BY_STATUS.get(status) or (ServerError if status >= 500 else APIError)
    message = f'{status} {response.reason_phrase} on {response.request.method} {response.request.url.path}: {_format_detail(detail)}'
    return cls(message, status_code=status, detail=detail, response=response)
