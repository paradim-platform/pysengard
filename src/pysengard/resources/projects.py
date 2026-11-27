from __future__ import annotations

from collections.abc import Iterable, Iterator

from .._utils import body, path
from ..models import Album, AlbumCategory, Page, Project
from ._base import DEFAULT_LIMIT, Resource, iterate


class Projects(Resource):
    """The projects visible to the caller (``/projects/``)."""

    def list(self, *, limit: int = DEFAULT_LIMIT, offset: int = 0) -> Page[Project]:
        """A page of the visible projects, ordered by name, each with the albums of it the caller sees."""
        return self._page(Project, 'projects/', limit, offset)

    def iter(self, *, page_size: int = DEFAULT_LIMIT) -> Iterator[Project]:
        """Every visible project, fetched ``page_size`` at a time."""
        return iterate(lambda limit, offset: self.list(limit=limit, offset=offset), page_size)

    def get(self, project_id: int) -> Project:
        """A visible project (else :class:`~pysengard.NotFoundError`)."""
        return Project.model_validate(self._get(path('projects', project_id)))

    def create_album(
        self,
        project_id: int,
        name: str,
        category: AlbumCategory | str,
        *,
        description: str = '',
        keywords: Iterable[str] | None = None,
        license: str = '',
        reference: str = '',
        contact_email: str = '',
    ) -> Album:
        """Create a root album in the project; the caller becomes its steward.

        Requires to administer the project (a steward of it, or a superuser). A name already used in the project raises
        :class:`~pysengard.ConflictError`. To create a sub-album, see :meth:`Albums.create_sub_album`.
        """
        payload = body(
            name=name,
            category=category,
            description=description,
            keywords=list(keywords) if keywords is not None else None,
            license=license,
            reference=reference,
            contact_email=contact_email,
        )
        return Album.model_validate(self._client.request('POST', path('projects', project_id, 'albums'), json=payload))
