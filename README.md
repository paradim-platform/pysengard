# pysengard

Python client for the **Isengard REST API v1** (`/api/v1/`): projects, albums and sub-albums, studies and series, album
copy and duplication, album DICOMweb tokens and album members.

The DICOMweb API (`/api/dicomweb/`: QIDO-RS, WADO-RS, STOW-RS) is not covered: use a DICOMweb client (for example
[dicomweb-client](https://github.com/ImagingDataCommons/dicomweb-client)) with an album token created by `pysengard`.

## Installation

Python 3.10 or newer.

```bash
pip install pysengard
# or, in a uv project
uv add pysengard
```

## Authentication

Every call requires a **personal token**, created on Isengard's *Profile → Tokens* page (or the access token of an
application that signs its users in with Isengard via OpenID Connect, limited by its scopes).

```python
from pysengard import Isengard

isengard = Isengard('https://isengard.example.org', token='…')
```

Without arguments, the client reads the `ISENGARD_URL` and `ISENGARD_TOKEN` environment variables:

```python
isengard = Isengard()  # or Isengard.from_env()
print(isengard.me().username)
```

The URL can be either the site's or the API's (`…/api/v1`). Options: `timeout`, `verify` (TLS certificate), `max_retries`
(retries of a request rejected with 429 by the rate limit), `headers`, `transport` (httpx).

## Usage

```python
import datetime as dt

from pysengard import AlbumCategory, ConflictError, Isengard, Permission

with Isengard() as isengard:
    # Visible projects and albums: list() returns one page, iter() walks through all pages.
    page = isengard.projects.list(limit=20)
    print(page.count, [project.name for project in page])

    for album in isengard.albums.iter(permissions=[Permission.CAN_CREATE_TOKEN]):
        print(album.album_id, album.name, album.series_count)

    album = isengard.albums.get('6DgJD3F7')

    # Studies and series of an album, with the filters of its page.
    for study in isengard.albums.iter_studies(album.album_id, patient_name='john doe', modalities=['CT', 'MR']):
        for series in isengard.albums.study_series(album.album_id, study.uid):
            print(study.patient_id, series.modality, series.uid)

    # Search across all visible albums (not paginated: has_more suggests narrowing the query).
    result = isengard.studies.search('doe', date_from=dt.date(2024, 1, 1))

    # A sub-album for an algorithm's results, and a DICOMweb write token to upload into it (STOW-RS).
    try:
        results = isengard.albums.create_sub_album(album.album_id, 'Segmentations v2', AlbumCategory.ALGORITHM)
    except ConflictError:
        results = next(a for a in isengard.albums.iter(project=album.project_id) if a.name == 'Segmentations v2')
    token = isengard.album_tokens.create(results.album_id, 'pipeline', dt.timedelta(days=7), can_write=True)
    print(token.token)  # the raw value is only returned once

    # … once the work is done, the application revokes its album token:
    isengard.album_tokens.revoke_self(token.token)
```

### Reference

| Method | Call |
|---|---|
| `isengard.me()` | `GET /me/` |
| `projects.list(limit, offset)` / `projects.iter(page_size)` | `GET /projects/` |
| `projects.get(project_id)` | `GET /projects/{project_id}/` |
| `projects.create_album(project_id, name, category, …)` | `POST /projects/{project_id}/albums/` |
| `albums.list(project, permissions, keyword, …)` / `albums.iter(…)` | `GET /albums/` |
| `albums.get(album_id)` | `GET /albums/{album_id}/` |
| `albums.update(album_id, name=…, keywords=…, …)` | `PATCH /albums/{album_id}/` |
| `albums.studies(album_id, …)` / `albums.iter_studies(…)` | `GET /albums/{album_id}/studies/` |
| `albums.series(album_id, modality)` / `albums.iter_series(…)` | `GET /albums/{album_id}/series/` |
| `albums.study_series(album_id, study_uid, own)` | `GET /albums/{album_id}/studies/{study_uid}/series/` |
| `albums.create_sub_album(album_id, name, category)` | `POST /albums/{album_id}/sub-albums/` |
| `albums.copy_series(album_id, destination, series)` | `POST /albums/{album_id}/copy/` |
| `albums.duplicate(album_id, name, mode, category, parent_names)` | `POST /albums/{album_id}/duplicate/` |
| `album_tokens.list(album_id, inactive)` / `album_tokens.iter(…)` | `GET /albums/{album_id}/tokens/` |
| `album_tokens.create(album_id, description, expiration, can_read, can_write)` | `POST /albums/{album_id}/tokens/` |
| `album_tokens.revoke(album_id, token_id)` | `DELETE /albums/{album_id}/tokens/{token_id}/` |
| `album_tokens.revoke_self(album_token)` | `DELETE /album-tokens/self/` |
| `members.list(album_id)` | `GET /albums/{album_id}/members/` |
| `members.add(album_id, user, permissions)` | `POST /albums/{album_id}/members/` |
| `members.update(album_id, user_id, grant, revoke)` | `PATCH /albums/{album_id}/members/{user_id}/` |
| `members.remove(album_id, user_id)` | `DELETE /albums/{album_id}/members/{user_id}/` |

Responses are pydantic models (`Album`, `Series`, `AlbumStudy`, …); unknown fields from a newer Isengard version are
preserved. The documentation of each call (required permissions, error cases) is in the docstrings, and in Isengard's
OpenAPI (`/api/v1/docs/`).

### Errors

An API error raises a subclass of `pysengard.APIError`, with `status_code` and `detail`:

| Status | Exception |
|---|---|
| 401 | `AuthenticationError` (token missing, unknown, expired or revoked) |
| 403 | `PermissionDeniedError` (album visible, but permission or scope missing) |
| 404 | `NotFoundError` (nonexistent or not visible) |
| 409 | `ConflictError` (name already taken in the project, member already present, …) |
| 422 | `UnprocessableEntityError` (request rejected or invalid) |
| 429 | `RateLimitError` (after `max_retries` retries) |
| 5xx | `ServerError` |

An unreachable server raises `IsengardConnectionError`. All of them inherit from `IsengardError`.

## License

[MIT](LICENSE)
