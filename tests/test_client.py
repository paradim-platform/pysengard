import datetime as dt
import json

import httpx
import pytest

from pysengard import (
    AuthenticationError,
    ConflictError,
    Isengard,
    IsengardConnectionError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
    UnprocessableEntityError,
)
from tests.conftest import sample, schema


def album(album_id='abc', **fields):
    return {**sample(schema('AlbumOut')), 'album_id': album_id, **fields}


class TestConfiguration:
    @pytest.mark.parametrize('base_url', ['https://isengard.test', 'https://isengard.test/', 'https://isengard.test/api/v1/'])
    def test_api_root(self, base_url):
        assert Isengard(base_url, token='t').base_url == 'https://isengard.test/api/v1/'

    def test_from_env(self, monkeypatch, api):
        monkeypatch.setenv('ISENGARD_URL', 'https://isengard.test')
        monkeypatch.setenv('ISENGARD_TOKEN', 'env-token')
        route = api.get('/me/').respond(json=sample(schema('MeOut')))
        Isengard.from_env().me()
        assert route.calls.last.request.headers['Authorization'] == 'Bearer env-token'

    def test_no_url(self, monkeypatch):
        monkeypatch.delenv('ISENGARD_URL', raising=False)
        with pytest.raises(ValueError, match='ISENGARD_URL'):
            Isengard(token='t')

    def test_headers(self, client, api):
        route = api.get('/me/').respond(json=sample(schema('MeOut')))
        client.me()
        headers = route.calls.last.request.headers
        assert headers['Authorization'] == 'Bearer personal-token'
        assert headers['User-Agent'].startswith('pysengard/')


class TestErrors:
    @pytest.mark.parametrize(
        ('status', 'error'),
        [(401, AuthenticationError), (403, PermissionDeniedError), (404, NotFoundError), (409, ConflictError), (500, ServerError)],
    )
    def test_status(self, client, api, status, error):
        api.get('/albums/abc/').respond(status, json={'detail': 'Nope'})
        with pytest.raises(error) as raised:
            client.albums.get('abc')
        assert raised.value.status_code == status
        assert raised.value.detail == 'Nope'
        assert 'Nope' in str(raised.value)

    def test_validation_errors(self, client, api):
        detail = [{'type': 'missing', 'loc': ['body', 'payload', 'name'], 'msg': 'Field required'}]
        api.post('/albums/abc/sub-albums/').respond(422, json={'detail': detail})
        with pytest.raises(UnprocessableEntityError, match='body.payload.name: Field required') as raised:
            client.albums.create_sub_album('abc', '', 'human')
        assert raised.value.detail == detail

    def test_not_json(self, client, api):
        api.get('/me/').respond(502, text='Bad gateway')
        with pytest.raises(ServerError, match='Bad gateway'):
            client.me()

    def test_connection_error(self, client, api):
        api.get('/me/').mock(side_effect=httpx.ConnectError('refused'))
        with pytest.raises(IsengardConnectionError):
            client.me()

    def test_retries_rate_limited_requests(self, client, api):
        route = api.get('/me/')
        route.side_effect = [httpx.Response(429, headers={'Retry-After': '0'}), httpx.Response(200, json=sample(schema('MeOut')))]
        assert client.me().username == 'text'
        assert route.call_count == 2

    def test_gives_up_after_max_retries(self, api):
        route = api.get('/me/').respond(429, headers={'Retry-After': '0'}, json={'detail': 'Slow down'})
        with Isengard('https://isengard.test', token='t', max_retries=1) as client, pytest.raises(RateLimitError):
            client.me()
        assert route.call_count == 2


class TestPagination:
    def test_page(self, client, api):
        route = api.get('/albums/').respond(json={'items': [album('a'), album('b')], 'count': 5})
        page = client.albums.list(limit=2, offset=2)
        assert [item.album_id for item in page] == ['a', 'b']
        assert (page.count, page.limit, page.offset, page.has_next, len(page)) == (5, 2, 2, True, 2)
        assert route.calls.last.request.url.params == httpx.QueryParams({'limit': '2', 'offset': '2'})

    def test_iter_fetches_every_page(self, client, api):
        def respond(request):
            offset = int(request.url.params['offset'])
            items = [album(str(i)) for i in range(offset, min(offset + 2, 5))]
            return httpx.Response(200, json={'items': items, 'count': 5})

        route = api.get('/albums/', params={'project': '3'}).mock(side_effect=respond)
        assert [item.album_id for item in client.albums.iter(project=3, page_size=2)] == ['0', '1', '2', '3', '4']
        assert route.call_count == 3

    def test_iter_stops_on_an_empty_page(self, client, api):
        route = api.get('/albums/').respond(json={'items': [], 'count': 10})
        assert list(client.albums.iter()) == []
        assert route.call_count == 1


class TestEncoding:
    def test_repeated_query_parameters(self, client, api):
        route = api.get('/albums/abc/studies/').respond(json={'items': [], 'count': 0})
        client.albums.studies('abc', modalities=['CT', 'MR'], date_from=dt.date(2024, 2, 1), own=False)
        params = route.calls.last.request.url.params
        assert params.get_list('modality') == ['CT', 'MR']
        assert params['date_from'] == '2024-02-01'
        assert params['own'] == 'false'
        assert 'patient_id' not in params

    def test_a_single_string_is_one_value(self, client, api):
        route = api.get('/albums/').respond(json={'items': [], 'count': 0})
        client.albums.list(permissions='can_upload')
        assert route.calls.last.request.url.params.get_list('permission') == ['can_upload']

    def test_path_segments_are_quoted(self, client, api):
        route = api.get('/albums/a%2Fb/').respond(json=album())
        client.albums.get('a/b')
        assert route.called

    def test_update_sends_only_the_given_fields(self, client, api):
        route = api.patch('/albums/abc/').respond(json=album())
        client.albums.update('abc', description='', keywords=[])
        assert json.loads(route.calls.last.request.content) == {'description': '', 'keywords': []}

    def test_token_expiration_from_a_lifetime(self, client, api):
        route = api.post('/albums/abc/tokens/').respond(201, json=sample(schema('CreatedAlbumTokenOut')))
        before = dt.datetime.now(dt.timezone.utc)
        client.album_tokens.create('abc', 'job', dt.timedelta(days=1), can_read=True)
        sent = json.loads(route.calls.last.request.content)
        expiration = dt.datetime.fromisoformat(sent['expiration_date'])
        assert dt.timedelta(hours=23) < expiration - before <= dt.timedelta(days=1, seconds=5)
        assert sent['can_read'] is True and sent['can_write'] is False

    def test_naive_expiration_is_sent_with_its_offset(self, client, api):
        route = api.post('/albums/abc/tokens/').respond(201, json=sample(schema('CreatedAlbumTokenOut')))
        client.album_tokens.create('abc', 'job', dt.datetime(2030, 1, 1, 12), can_read=True)
        sent = dt.datetime.fromisoformat(json.loads(route.calls.last.request.content)['expiration_date'])
        assert sent.tzinfo is not None

    def test_revoke_self_authenticates_with_the_album_token(self, client, api):
        route = api.delete('/album-tokens/self/').respond(204)
        assert client.album_tokens.revoke_self('album-token') is None
        assert route.calls.last.request.headers['Authorization'] == 'Bearer album-token'

    def test_unknown_fields_are_kept(self, client, api):
        api.get('/albums/abc/').respond(json=album(new_field=42))
        assert client.albums.get('abc').new_field == 42
