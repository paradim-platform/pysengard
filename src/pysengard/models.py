"""The resources the Isengard REST API answers, as pydantic models.

They follow the schemas of the OpenAPI document (``/api/v1/openapi.json``); the name of the schema each model mirrors is given in
its docstring. Unknown fields are kept (``extra='allow'``), so a newer Isengard does not break an older client.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict


class AlbumCategory(str, Enum):
    """The category of an album to create (``AlbumCategory``)."""

    ACQUISITION = 'acquisition'
    ALGORITHM = 'algorithm'
    HUMAN = 'human'


class DuplicationMode(str, Enum):
    """What the copy of an album holds (``DuplicationMode``).

    - ``ALBUM``: its own series (all of a root album; a sub-album's own data, without what it inherits);
    - ``MERGED``: a sub-album's series and those it inherits from its parent albums, in one root album;
    - ``LINEAGE``: the same tree, a copy of each parent album then the copy of the sub-album under them.
    """

    ALBUM = 'album'
    MERGED = 'merged'
    LINEAGE = 'lineage'


class Permission(str, Enum):
    """A permission on an album (``Permission``); all but ``IS_ADMIN`` can be granted to a member (``GrantablePermission``)."""

    IS_ADMIN = 'is_admin'
    CAN_UPLOAD = 'can_upload'
    CAN_DOWNLOAD = 'can_download'
    CAN_EXPORT = 'can_export'
    CAN_REMOVE = 'can_remove'
    CAN_MANAGE_MEMBERS = 'can_manage_members'
    CAN_CREATE_TOKEN = 'can_create_token'  # noqa: S105  # a permission, not a password
    CAN_CREATE_SUBALBUM = 'can_create_subalbum'
    CAN_COPY_DATA = 'can_copy_data'


class _Model(BaseModel):
    model_config = ConfigDict(extra='allow')


# ── Projects ───────────────────────────────────────────────────────────────────


class ProjectAlbum(_Model):
    """An album of a project, as listed with it (``ProjectAlbumOut``)."""

    album_id: str
    name: str
    public: bool
    category: str
    parent_album_id: str | None = None


class Project(_Model):
    """A project (``ProjectOut``), with the albums of it the caller sees."""

    id: int
    name: str
    description: str
    public: bool
    ethics_number: str
    created_at: dt.datetime
    updated_at: dt.datetime
    last_activity_at: dt.datetime | None = None
    albums: list[ProjectAlbum]


# ── Albums ─────────────────────────────────────────────────────────────────────


class Album(_Model):
    """An album (``AlbumOut``). ``album_id`` is the identifier the other calls take."""

    id: int
    album_id: str
    name: str
    description: str
    public: bool
    # acquisition, algorithm, human, or the category of a frozen album.
    category: str
    project_id: int
    project_name: str
    parent_album_id: str | None = None
    study_count: int
    series_count: int
    keywords: list[str]
    license: str
    reference: str
    contact_email: str
    frozen_at: dt.datetime | None = None
    created_at: dt.datetime
    updated_at: dt.datetime
    last_ingestion_at: dt.datetime | None = None


class AlbumStudy(_Model):
    """A study an album shows (``AlbumStudyOut``), with the modalities and the number of its series the album shows."""

    orthanc_id: str
    uid: str
    patient_id: str
    patient_name: str
    date: dt.date | None = None
    description: str
    accession_number: str
    modalities: list[str]
    series_count: int


class Series(_Model):
    """A series an album shows (``SeriesOut``). ``inherited`` is true for a series shown from a parent album."""

    id: int
    orthanc_id: str
    uid: str
    description: str
    modality: str
    study_id: int
    study_uid: str
    study_date: dt.date | None = None
    inherited: bool
    # None until the series has been checked against Orthanc.
    instance_count: int | None = None
    size_bytes: int | None = None
    counters_synced_at: dt.datetime | None = None
    created_at: dt.datetime
    updated_at: dt.datetime


class SeriesCopyResult(_Model):
    """What a copy did with each requested series, by SeriesInstanceUID (``SeriesCopyOut``)."""

    source: str
    destination: str
    # Linked to the destination by this call.
    copied: list[str]
    # Held by the destination already: nothing to do.
    already_held: list[str]
    # Held by a parent album of the destination, which therefore already shows them.
    already_shown: list[str]
    # Inherited by the source from a parent album on which the caller does not hold ``can_copy_data``: not copied.
    not_permitted: list[str]


class AlbumDuplication(_Model):
    """The albums a duplication created (``AlbumDuplicateOut``)."""

    album: Album
    # ``lineage``: the copies of its parent albums, root first. Else empty.
    parents: list[Album]
    # The links created between the copies and the series, all copies together.
    series_count: int


# ── Album (DICOMweb) tokens ────────────────────────────────────────────────────


class AlbumToken(_Model):
    """A DICOMweb token of an album, as listed (``ListedAlbumTokenOut``): never its value, which is not stored."""

    id: int
    description: str
    can_read: bool
    can_write: bool
    expiration_date: dt.datetime
    created_at: dt.datetime
    # ACTIVE, EXPIRED or REVOKED.
    state: str
    last_used: dt.datetime | None = None
    created_by: str
    # The application, or the personal token, that created it through the REST API; '' from the web pages.
    issued_via: str
    # The study the token is limited to; None for the whole album.
    study_uid: str | None = None


class CreatedAlbumToken(_Model):
    """A DICOMweb token just created (``CreatedAlbumTokenOut``), with its raw value, answered this once only."""

    id: int
    description: str
    can_read: bool
    can_write: bool
    expiration_date: dt.datetime
    created_at: dt.datetime
    # Use it as ``Authorization: Bearer <token>`` on DICOMweb.
    token: str


# ── Members ────────────────────────────────────────────────────────────────────


class User(_Model):
    """A user (``UserOut``)."""

    id: int
    username: str
    email: str
    full_name: str


class Member(_Model):
    """A row of the access table of an album (``MemberOut``): a steward, a member, or a group membership."""

    user: User | None = None
    group: str | None = None
    steward: bool
    permissions: list[str]


# ── Studies ────────────────────────────────────────────────────────────────────


class StudyAlbum(_Model):
    """An album holding a study found by a search (``StudyAlbumOut``)."""

    album_id: str
    name: str
    project_id: int
    project_name: str


class StudyHit(_Model):
    """A study found by a search (``StudyHitOut``), with the albums the caller sees that hold one of its series."""

    orthanc_id: str
    uid: str
    patient_id: str
    patient_name: str
    date: dt.date | None = None
    description: str
    accession_number: str
    modalities: list[str]
    albums: list[StudyAlbum]


class StudySearchResult(_Model):
    """The result of a study search (``StudySearchOut``). ``has_more``: more studies match, refine the query."""

    items: list[StudyHit]
    has_more: bool


# ── Me ─────────────────────────────────────────────────────────────────────────


class TokenInfo(_Model):
    """The token of the call (``TokenInfoOut``): a personal token, or an application's access token with its scopes."""

    kind: str
    name: str
    scopes: list[str] | None = None
    expires_at: dt.datetime


class Me(_Model):
    """The user the token acts for (``MeOut``)."""

    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    is_superuser: bool
    token: TokenInfo


# ── Pagination ─────────────────────────────────────────────────────────────────

T = TypeVar('T')


class Page(BaseModel, Generic[T]):
    """A page of a paginated list: ``items``, and ``count`` the total number of matching items."""

    items: list[T]
    count: int
    limit: int
    offset: int

    @property
    def has_next(self) -> bool:
        return self.offset + len(self.items) < self.count

    def __iter__(self):  # type: ignore[override]  # iterate over the items, not the fields
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)
