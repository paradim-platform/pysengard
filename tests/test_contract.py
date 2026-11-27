"""The client against the OpenAPI document of Isengard (tests/openapi.json, see the README to refresh it).

Every operation of the document is called through the client, answered with a sample of its response schema (every field
filled): the client covers the whole API, its models read every response, and its bodies are those the API takes.
"""

import datetime as dt
import json
import re

import pytest

from pysengard import models
from tests.conftest import OPENAPI, sample, schema

# Each call of the client, by the operation it sends.
CALLS = {
    ('GET', '/api/v1/projects/'): lambda c: c.projects.list(),
    ('GET', '/api/v1/projects/{project_id}/'): lambda c: c.projects.get(1),
    ('POST', '/api/v1/projects/{project_id}/albums/'): lambda c: c.projects.create_album(
        1, 'Results', 'algorithm', description='d', keywords=['k'], license='CC-BY', reference='r', contact_email='a@b.c'
    ),
    ('GET', '/api/v1/albums/'): lambda c: c.albums.list(project=1, permissions=['can_upload'], keyword='k'),
    ('GET', '/api/v1/albums/{album_id}/'): lambda c: c.albums.get('abc'),
    ('PATCH', '/api/v1/albums/{album_id}/'): lambda c: c.albums.update('abc', name='New', keywords=['a', 'b']),
    ('GET', '/api/v1/albums/{album_id}/studies/'): lambda c: c.albums.studies(
        'abc', patient_name='doe', date_from=dt.date(2020, 1, 1), modalities=['CT', 'MR'], own=True
    ),
    ('GET', '/api/v1/albums/{album_id}/series/'): lambda c: c.albums.series('abc', modality='CT'),
    ('GET', '/api/v1/albums/{album_id}/studies/{study_uid}/series/'): lambda c: c.albums.study_series('abc', '1.2.3', own=True),
    ('POST', '/api/v1/albums/{album_id}/sub-albums/'): lambda c: c.albums.create_sub_album('abc', 'Run 1', 'algorithm'),
    ('POST', '/api/v1/albums/{album_id}/copy/'): lambda c: c.albums.copy_series('abc', 'def', ['1.2.3.4']),
    ('POST', '/api/v1/albums/{album_id}/duplicate/'): lambda c: c.albums.duplicate(
        'abc', 'Copy', mode='lineage', category='human', parent_names={'par': 'Parent copy'}
    ),
    ('GET', '/api/v1/albums/{album_id}/tokens/'): lambda c: c.album_tokens.list('abc', inactive=True),
    ('POST', '/api/v1/albums/{album_id}/tokens/'): lambda c: c.album_tokens.create('abc', 'job', dt.timedelta(days=7), can_write=True),
    ('DELETE', '/api/v1/albums/{album_id}/tokens/{token_id}/'): lambda c: c.album_tokens.revoke('abc', 4),
    ('GET', '/api/v1/albums/{album_id}/members/'): lambda c: c.members.list('abc'),
    ('POST', '/api/v1/albums/{album_id}/members/'): lambda c: c.members.add('abc', 'jdoe', ['can_download']),
    ('PATCH', '/api/v1/albums/{album_id}/members/{user_id}/'): lambda c: c.members.update(
        'abc', 7, grant=['can_upload'], revoke=[models.Permission.CAN_REMOVE]
    ),
    ('DELETE', '/api/v1/albums/{album_id}/members/{user_id}/'): lambda c: c.members.remove('abc', 7),
    ('DELETE', '/api/v1/album-tokens/self/'): lambda c: c.album_tokens.revoke_self('album-token'),
    ('GET', '/api/v1/studies/'): lambda c: c.studies.search('doe', modalities=['CT'], date_to=dt.date(2026, 1, 1)),
    ('GET', '/api/v1/me/'): lambda c: c.me(),
}

# The model of the client mirroring each response schema.
MODELS = {
    'ProjectAlbumOut': models.ProjectAlbum,
    'ProjectOut': models.Project,
    'AlbumOut': models.Album,
    'AlbumStudyOut': models.AlbumStudy,
    'SeriesOut': models.Series,
    'SeriesCopyOut': models.SeriesCopyResult,
    'AlbumDuplicateOut': models.AlbumDuplication,
    'ListedAlbumTokenOut': models.AlbumToken,
    'CreatedAlbumTokenOut': models.CreatedAlbumToken,
    'UserOut': models.User,
    'MemberOut': models.Member,
    'StudyAlbumOut': models.StudyAlbum,
    'StudyHitOut': models.StudyHit,
    'StudySearchOut': models.StudySearchResult,
    'TokenInfoOut': models.TokenInfo,
    'MeOut': models.Me,
}

ENUMS = {'AlbumCategory': models.AlbumCategory, 'DuplicationMode': models.DuplicationMode, 'Permission': models.Permission}

OPERATIONS = [(method.upper(), url) for url, operations in OPENAPI['paths'].items() for method in operations]


def test_every_operation_has_a_call():
    assert sorted(CALLS) == sorted(OPERATIONS)


def _success(operation):
    status, response = next((code, response) for code, response in operation['responses'].items() if code.startswith('2'))
    content = response.get('content', {}).get('application/json')
    return int(status), sample(content['schema']) if content else None


def _check_body(request_body, sent):
    node = request_body['content']['application/json']['schema']
    target = schema(node['$ref'].rsplit('/', 1)[-1])
    properties = target.get('properties', {})
    assert set(sent) <= set(properties), f'Unknown fields: {set(sent) - set(properties)}'
    assert set(target.get('required', [])) <= set(sent), 'Missing required fields'


@pytest.mark.parametrize(('method', 'url'), OPERATIONS, ids=[f'{m} {u}' for m, u in OPERATIONS])
def test_operation(client, api, method, url):
    operation = OPENAPI['paths'][url][method.lower()]
    status, payload = _success(operation)
    pattern = re.escape(url).replace(r'\{', '{').replace(r'\}', '}')
    pattern = re.sub(r'\{[^}]+\}', '[^/]+', pattern)
    route = api.route(method=method, url__regex=rf'^https://isengard\.test{pattern}(\?.*)?$')
    route.respond(status, json=payload) if payload is not None else route.respond(status)

    CALLS[(method, url)](client)

    assert route.call_count == 1
    request = route.calls.last.request
    known = {parameter['name'] for parameter in operation.get('parameters', []) if parameter['in'] == 'query'}
    assert set(request.url.params) <= known, f'Unknown query parameters: {set(request.url.params) - known}'
    if 'requestBody' in operation:
        _check_body(operation['requestBody'], json.loads(request.content))
    else:
        assert not request.content


@pytest.mark.parametrize('name', sorted(MODELS))
def test_models_have_the_fields_of_the_schemas(name):
    target = schema(name)
    fields = MODELS[name].model_fields
    assert set(fields) == set(target['properties'])
    required = {field for field, info in fields.items() if info.is_required()}
    assert required <= set(target.get('required', []))


@pytest.mark.parametrize('name', sorted(ENUMS))
def test_enums_have_the_values_of_the_schemas(name):
    assert sorted(item.value for item in ENUMS[name]) == sorted(schema(name)['enum'])
