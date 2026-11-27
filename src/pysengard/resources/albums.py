from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Iterator, Mapping

from .._utils import body, path
from ..models import (
    Album,
    AlbumCategory,
    AlbumDuplication,
    AlbumStudy,
    DuplicationMode,
    Page,
    Permission,
    Series,
    SeriesCopyResult,
)
from ._base import DEFAULT_LIMIT, Resource, iterate


def _list(values: Iterable | None) -> list | None:
    if values is None:
        return None
    if isinstance(values, str):
        # A single modality or permission, not its letters.
        return [values]
    return list(values)


class Albums(Resource):
    """The albums visible to the caller (``/albums/``), their studies and series, and the albums created from them.

    The album tokens and the members of an album are in :attr:`Isengard.album_tokens` and :attr:`Isengard.members`.
    """

    # ── Albums ─────────────────────────────────────────────────────────────────

    def list(
        self,
        *,
        project: int | None = None,
        permissions: Iterable[Permission | str] | None = None,
        keyword: str | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> Page[Album]:
        """A page of the visible albums, ordered by name.

        ``project`` keeps the albums of that project; ``permissions`` those where the caller holds every permission given (e.g.
        ``['can_upload']`` lists the possible destinations of a copy); ``keyword`` those with that keyword, whatever its case.
        """
        return self._page(Album, 'albums/', limit, offset, project=project, permission=_list(permissions), keyword=keyword)

    def iter(
        self,
        *,
        project: int | None = None,
        permissions: Iterable[Permission | str] | None = None,
        keyword: str | None = None,
        page_size: int = DEFAULT_LIMIT,
    ) -> Iterator[Album]:
        """Every visible album matching the filters of :meth:`list`, fetched ``page_size`` at a time."""
        return iterate(
            lambda limit, offset: self.list(project=project, permissions=permissions, keyword=keyword, limit=limit, offset=offset),
            page_size,
        )

    def get(self, album_id: str) -> Album:
        """A visible album, by its ``album_id`` (else :class:`~pysengard.NotFoundError`)."""
        return Album.model_validate(self._get(path('albums', album_id)))

    def update(
        self,
        album_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        category: AlbumCategory | str | None = None,
        keywords: Iterable[str] | None = None,
        license: str | None = None,
        reference: str | None = None,
        contact_email: str | None = None,
    ) -> Album:
        """Change the details given (those left to ``None`` are kept). ``keywords`` replaces all the keywords.

        Requires to administer the album. A name already used in the project raises :class:`~pysengard.ConflictError`.
        """
        payload = body(
            name=name,
            description=description,
            category=category,
            keywords=_list(keywords),
            license=license,
            reference=reference,
            contact_email=contact_email,
        )
        return Album.model_validate(self._client.request('PATCH', path('albums', album_id), json=payload))

    # ── Studies and series ─────────────────────────────────────────────────────

    def studies(
        self,
        album_id: str,
        *,
        patient_id: str | None = None,
        patient_name: str | None = None,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
        description: str | None = None,
        modalities: Iterable[str] | None = None,
        own: bool | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
    ) -> Page[AlbumStudy]:
        """A page of the studies the album shows, with the filters of its page, ordered by patient ID, latest first.

        ``patient_id`` and ``description`` match a part of the field; every word of ``patient_name`` must appear (``john doe``
        matches ``DOE^JOHN``); ``date_from`` and ``date_to`` bound the study date; ``modalities`` keeps the studies with a
        series of one of them; ``own`` keeps a sub-album's own series, without those of its parent albums.
        """
        return self._page(
            AlbumStudy,
            path('albums', album_id, 'studies'),
            limit,
            offset,
            patient_id=patient_id,
            patient_name=patient_name,
            date_from=date_from,
            date_to=date_to,
            description=description,
            modality=_list(modalities),
            own=own,
        )

    def iter_studies(self, album_id: str, *, page_size: int = DEFAULT_LIMIT, **filters) -> Iterator[AlbumStudy]:
        """Every study the album shows matching the filters of :meth:`studies`, fetched ``page_size`` at a time."""
        return iterate(lambda limit, offset: self.studies(album_id, limit=limit, offset=offset, **filters), page_size)

    def series(self, album_id: str, *, modality: str | None = None, limit: int = DEFAULT_LIMIT, offset: int = 0) -> Page[Series]:
        """A page of the series the album shows, ordered by UID: its own and, for a sub-album, those of its parent albums."""
        return self._page(Series, path('albums', album_id, 'series'), limit, offset, modality=modality)

    def iter_series(self, album_id: str, *, modality: str | None = None, page_size: int = DEFAULT_LIMIT) -> Iterator[Series]:
        """Every series the album shows, fetched ``page_size`` at a time."""
        return iterate(lambda limit, offset: self.series(album_id, modality=modality, limit=limit, offset=offset), page_size)

    def study_series(self, album_id: str, study_uid: str, *, own: bool | None = None) -> list[Series]:
        """The series of a study (by its StudyInstanceUID) that the album shows, ordered by modality, description and UID.

        Raises :class:`~pysengard.NotFoundError` if the album shows no series of the study.
        """
        data = self._get(path('albums', album_id, 'studies', study_uid, 'series'), own=own)
        return [Series.model_validate(item) for item in data]

    # ── Albums created from an album ───────────────────────────────────────────

    def create_sub_album(self, album_id: str, name: str, category: AlbumCategory | str, *, description: str = '') -> Album:
        """Create a sub-album of the album, e.g. to receive the results of an algorithm run on its series.

        Requires ``can_create_subalbum`` on the album; the caller becomes the steward of the sub-album. A name already used in
        the project raises :class:`~pysengard.ConflictError`. Then create a token of the sub-album
        (:meth:`AlbumTokens.create`) to store the results through DICOMweb STOW-RS.
        """
        payload = body(name=name, category=category, description=description)
        return Album.model_validate(self._client.request('POST', path('albums', album_id, 'sub-albums'), json=payload))

    def copy_series(self, album_id: str, destination: str, series: Iterable[str]) -> SeriesCopyResult:
        """Copy series the album shows (by SeriesInstanceUID, 1000 at most) into ``destination``, another album of the project.

        Requires ``can_copy_data`` on the album and ``can_upload`` on the destination. A series the album does not show raises
        :class:`~pysengard.NotFoundError`, and nothing is copied. Copying again is harmless.
        """
        payload = body(destination=destination, series=_list(series))
        return SeriesCopyResult.model_validate(self._client.request('POST', path('albums', album_id, 'copy'), json=payload))

    def duplicate(
        self,
        album_id: str,
        name: str,
        *,
        mode: DuplicationMode | str = DuplicationMode.ALBUM,
        category: AlbumCategory | str | None = None,
        parent_names: Mapping[str, str] | None = None,
    ) -> AlbumDuplication:
        """Duplicate the album into a new album of its project, named ``name``.

        ``mode`` says what the copy holds (see :class:`~pysengard.DuplicationMode`). ``category`` changes the copy's (required
        for a frozen album). ``parent_names``, for ``lineage`` only, maps the ``album_id`` of a parent album to the name of its
        copy. Requires to administer the project.
        """
        payload = body(name=name, mode=mode, category=category, parent_names=dict(parent_names) if parent_names else None)
        return AlbumDuplication.model_validate(self._client.request('POST', path('albums', album_id, 'duplicate'), json=payload))
