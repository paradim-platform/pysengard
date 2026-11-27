import json
from pathlib import Path

import pytest
import respx

from pysengard import Isengard

BASE_URL = 'https://isengard.test'
API = f'{BASE_URL}/api/v1'
OPENAPI = json.loads((Path(__file__).parent / 'openapi.json').read_text())


@pytest.fixture
def client():
    with Isengard(BASE_URL, token='personal-token') as isengard:
        yield isengard


@pytest.fixture
def api():
    with respx.mock(base_url=API, assert_all_called=False) as router:
        yield router


def schema(name):
    return OPENAPI['components']['schemas'][name]


def sample(node):
    """A value valid for an OpenAPI schema node, every field filled (the nullable ones too)."""
    if '$ref' in node:
        return sample(schema(node['$ref'].rsplit('/', 1)[-1]))
    for key in ('allOf', 'anyOf'):
        if key in node:
            options = [option for option in node[key] if option.get('type') != 'null']
            return sample(options[0])
    if 'enum' in node:
        return node['enum'][0]
    kind = node.get('type')
    if kind == 'object':
        return {name: sample(prop) for name, prop in node.get('properties', {}).items()}
    if kind == 'array':
        return [sample(node['items'])]
    if kind == 'string':
        return {'date-time': '2026-11-11T12:00:00Z', 'date': '2026-11-11'}.get(node.get('format'), 'text')
    if kind == 'integer':
        return 1
    if kind == 'boolean':
        return True
    raise AssertionError(f'Unknown schema node: {node}')
