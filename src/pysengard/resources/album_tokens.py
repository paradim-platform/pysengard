from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

from .._utils import body, path
from ..models import AlbumToken, CreatedAlbumToken, Page
from ._base import DEFAULT_LIMIT, Resource, iterate


class AlbumTokens(Resource):
    """The DICOMweb tokens of an album (``/albums/{album_id}/tokens/``).

    Requires ``can_create_token`` on the album (an access token: the ``album-tokens:write`` scope).
    """

    def list(self, album_id: str, *, inactive: bool | None = None, limit: int = DEFAULT_LIMIT, offset: int = 0) -> Page[AlbumToken]:
        """A page of the tokens of the album, latest first: the active ones, and with ``inactive`` the expired and revoked ones."""
        return self._page(AlbumToken, path('albums', album_id, 'tokens'), limit, offset, inactive=inactive)

    def iter(self, album_id: str, *, inactive: bool | None = None, page_size: int = DEFAULT_LIMIT) -> Iterator[AlbumToken]:
        """Every token of the album, fetched ``page_size`` at a time."""
        return iterate(lambda limit, offset: self.list(album_id, inactive=inactive, limit=limit, offset=offset), page_size)

    def create(
        self,
        album_id: str,
        description: str,
        expiration: dt.datetime | dt.timedelta,
        *,
        can_read: bool = False,
        can_write: bool = False,
    ) -> CreatedAlbumToken:
        """Create a DICOMweb token of the album; its raw value (``.token``) is answered this once only.

        ``expiration`` is the expiration date, or the lifetime of the token from now; the server caps it. At least one of
        ``can_read`` and ``can_write`` is required. A naive datetime is read as a local time.
        """
        if isinstance(expiration, dt.timedelta):
            expiration = dt.datetime.now(dt.timezone.utc) + expiration
        payload = body(description=description, can_read=can_read, can_write=can_write, expiration_date=expiration)
        return CreatedAlbumToken.model_validate(self._client.request('POST', path('albums', album_id, 'tokens'), json=payload))

    def revoke(self, album_id: str, token_id: int) -> None:
        """Revoke a token of the album: it stops authenticating at once. Revoking it again changes nothing."""
        self._client.request('DELETE', path('albums', album_id, 'tokens', token_id))

    def revoke_self(self, album_token: str) -> None:
        """Revoke the album token ``album_token`` itself, authenticated by it (not by the client's token).

        For an application giving up the album token it was given, once done with it. An already revoked or expired token is
        fine; an unknown one raises :class:`~pysengard.AuthenticationError`.
        """
        self._client.request('DELETE', path('album-tokens', 'self'), headers={'Authorization': f'Bearer {album_token}'})
