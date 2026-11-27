"""Encoding of the paths, query parameters and JSON bodies of the requests."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from enum import Enum
from typing import Any
from urllib.parse import quote

API_PREFIX = '/api/v1'


def api_root(base_url: str) -> str:
    """``https://isengard.example`` (or ``…/api/v1``) → ``https://isengard.example/api/v1/``."""
    root = base_url.rstrip('/')
    if not root.endswith(API_PREFIX):
        root += API_PREFIX
    return root + '/'


def path(*segments: Any) -> str:
    """The relative path of an endpoint, its segments quoted, with the trailing slash the API expects."""
    return '/'.join(quote(str(segment), safe='') for segment in segments) + '/'


def jsonable(value: Any) -> Any:
    """Enums by their value, dates in ISO 8601, recursively."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dt.datetime):
        # A naive datetime is a local time: send its offset, so that the server does not read it in its own time zone.
        return (value if value.tzinfo else value.astimezone()).isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(item) for item in value]
    return value


def body(**fields: Any) -> dict[str, Any]:
    """A JSON body without the fields left to ``None`` (not sent: the API keeps or defaults them)."""
    return {key: jsonable(value) for key, value in fields.items() if value is not None}


def _query_value(value: Any) -> Any:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return jsonable(value)


def query(params: Mapping[str, Any]) -> list[tuple[str, Any]]:
    """Query parameters without the ``None`` ones, lists repeated (``?modality=CT&modality=MR``)."""
    pairs: list[tuple[str, Any]] = []
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set, frozenset)):
            pairs.extend((key, _query_value(item)) for item in value)
        else:
            pairs.append((key, _query_value(value)))
    return pairs
