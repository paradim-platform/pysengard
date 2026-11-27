"""The Isengard REST API client."""

from __future__ import annotations

import os
import time
from collections.abc import Mapping
from typing import Any

import httpx

from ._utils import api_root, query
from ._version import __version__
from .exceptions import IsengardConnectionError, error_from_response
from .models import Me
from .resources.album_tokens import AlbumTokens
from .resources.albums import Albums
from .resources.members import Members
from .resources.projects import Projects
from .resources.studies import Studies

URL_ENV = 'ISENGARD_URL'
TOKEN_ENV = 'ISENGARD_TOKEN'  # noqa: S105  # the name of the variable, not a token


class Isengard:
    """A client of the Isengard REST API v1.

    >>> from pysengard import Isengard
    >>> with Isengard('https://isengard.example', token='…') as isengard:
    ...     for album in isengard.albums.iter(permissions=['can_create_token']):
    ...         print(album.album_id, album.name)

    ``base_url`` and ``token`` default to the ``ISENGARD_URL`` and ``ISENGARD_TOKEN`` environment variables. The token is a
    personal token (created on the profile page of Isengard), or the access token of an application that signs its users in
    with Isengard (OpenID Connect).

    A request answered 429 (rate limited) is retried up to ``max_retries`` times, after the delay of its ``Retry-After``.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        *,
        timeout: float | httpx.Timeout = 30.0,
        verify: bool | str = True,
        max_retries: int = 3,
        headers: Mapping[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        base_url = base_url or os.environ.get(URL_ENV)
        if not base_url:
            raise ValueError(f'No Isengard URL: pass base_url or set {URL_ENV}.')
        token = token if token is not None else os.environ.get(TOKEN_ENV)
        self.base_url = api_root(base_url)
        self.max_retries = max_retries
        all_headers = {'Accept': 'application/json', 'User-Agent': f'pysengard/{__version__}'}
        if token:
            all_headers['Authorization'] = f'Bearer {token}'
        all_headers.update(headers or {})
        self._http = httpx.Client(base_url=self.base_url, headers=all_headers, timeout=timeout, verify=verify, transport=transport)

        self.projects = Projects(self)
        self.albums = Albums(self)
        self.album_tokens = AlbumTokens(self)
        self.members = Members(self)
        self.studies = Studies(self)

    @classmethod
    def from_env(cls, **kwargs: Any) -> Isengard:
        """A client configured by ``ISENGARD_URL`` and ``ISENGARD_TOKEN``."""
        return cls(**kwargs)

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self.base_url!r})'

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Isengard:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # ── Calls ──────────────────────────────────────────────────────────────────

    def me(self) -> Me:
        """The user the token acts for, and the token (``GET /me/``)."""
        return Me.model_validate(self.request('GET', 'me/'))

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Send a request to the API (``url`` relative to ``/api/v1/``) and return its decoded JSON, ``None`` for a 204.

        Raises an :class:`~pysengard.exceptions.APIError` subclass for an error status.
        """
        attempt = 0
        while True:
            try:
                response = self._http.request(method, url, params=query(params or {}), json=json, headers=headers)
            except httpx.TransportError as exc:
                raise IsengardConnectionError(f'{method} {self.base_url}{url}: {exc}') from exc
            if response.status_code == 429 and attempt < self.max_retries:
                attempt += 1
                time.sleep(_retry_delay(response, attempt))
                continue
            if response.is_error:
                raise error_from_response(response)
            if response.status_code == 204 or not response.content:
                return None
            return response.json()


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get('Retry-After')
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    return min(0.5 * 2 ** (attempt - 1), 8.0)
