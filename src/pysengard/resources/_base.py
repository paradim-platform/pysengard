from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel

from ..models import Page

if TYPE_CHECKING:
    from ..client import Isengard

M = TypeVar('M', bound=BaseModel)

# The API's default and maximum ``limit`` of a paginated list.
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000


class Resource:
    def __init__(self, client: Isengard):
        self._client = client

    def _get(self, url: str, **params: Any) -> Any:
        return self._client.request('GET', url, params=params)

    def _page(self, model: type[M], url: str, limit: int, offset: int, **params: Any) -> Page[M]:
        data = self._get(url, limit=limit, offset=offset, **params)
        return Page[model](items=data['items'], count=data['count'], limit=limit, offset=offset)


def iterate(fetch: Callable[[int, int], Page[M]], page_size: int) -> Iterator[M]:
    """Every item of a paginated list, fetching it ``page_size`` items at a time."""
    offset = 0
    while True:
        page = fetch(page_size, offset)
        yield from page.items
        offset += len(page.items)
        if not page.items or offset >= page.count:
            return
