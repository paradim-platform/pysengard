from __future__ import annotations

from collections.abc import Iterable

from .._utils import body, path
from ..models import Member, Permission
from ._base import Resource


def _permissions(permissions: Iterable[Permission | str] | None) -> list | None:
    if permissions is None:
        return None
    return [permissions] if isinstance(permissions, str) else list(permissions)


class Members(Resource):
    """The members of an album (``/albums/{album_id}/members/``).

    Requires ``can_manage_members`` on the album (an access token: the ``album-members:write`` scope to change them). Whoever
    does not administer the album only grants or revokes the permissions they hold. The stewards are changed on the web pages.
    """

    def list(self, album_id: str) -> list[Member]:
        """The access table of the album: its stewards, then its members with their permissions, then group memberships."""
        return [Member.model_validate(item) for item in self._get(path('albums', album_id, 'members'))]

    def add(self, album_id: str, user: str, permissions: Iterable[Permission | str] = ()) -> Member:
        """Make a user (by username or email address) a member of the album, with ``permissions``.

        The user must already be a member of the project, or of the parent album for a sub-album. A steward or a member already
        raises :class:`~pysengard.ConflictError`: change a member's permissions with :meth:`update`.
        """
        payload = body(user=user, permissions=_permissions(permissions))
        return Member.model_validate(self._client.request('POST', path('albums', album_id, 'members'), json=payload))

    def update(
        self,
        album_id: str,
        user_id: int,
        *,
        grant: Iterable[Permission | str] = (),
        revoke: Iterable[Permission | str] = (),
    ) -> Member:
        """Grant the permissions of ``grant`` and revoke those of ``revoke`` to a member (by user id); the others are kept."""
        payload = body(grant=_permissions(grant), revoke=_permissions(revoke))
        return Member.model_validate(self._client.request('PATCH', path('albums', album_id, 'members', user_id), json=payload))

    def remove(self, album_id: str, user_id: int) -> None:
        """Remove a member (by user id) from the album and from its sub-albums."""
        self._client.request('DELETE', path('albums', album_id, 'members', user_id))
