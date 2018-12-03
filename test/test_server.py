import os
import tempfile
import json
import pytest
from pprint import pprint
from .util import test_config
from uuid import uuid4
import feeds.config
from .mongo_controller import MongoController
import test.util as test_util

cfg = test_config()


@pytest.mark.parametrize('path', (
    '/api/V1/notifications',
    '/api/V1/notifications?',
    '/api/V1/notification/some_note_id'
))
def test_server_get_paths_noauth(client, path):
    response = client.get(path)
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'].get('http_code') == 401
    assert data['error'].get('http_status') == 'Unauthorized'
    assert 'Authentication token required' in data['error'].get('message')


@pytest.mark.parametrize('path', (
    '/api/V1/notification',
    '/api/V1/notification/global',
    '/api/V1/notifications/see',
    '/api/V1/notifications/unsee'
))
def test_server_post_paths_noauth(client, path):
    response = client.post(path)
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'].get('http_code') == 401
    assert data['error'].get('http_status') == 'Unauthorized'
    assert 'Authentication token required' in data['error'].get('message')


def test_root(client):
    response = client.get('/')
    data = json.loads(response.data)
    assert 'servertime' in data
    assert 'service' in data and data['service'] == 'Notification Feeds Service'
    assert 'version' in data


def test_permissions_noauth(client, requests_mock):
    response = client.get('/permissions')
    data = json.loads(response.data)
    assert 'token' in data
    assert data['token'] == {'service': None, 'user': None, 'admin': False}
    assert 'permissions' in data
    assert data['permissions'] == {'GET': ['/api/V1/notifications/global'], 'POST': []}


def test_permissions_user(client, requests_mock, mock_valid_user_token):
    user_id = 'a_user'
    user_name = 'A User'
    mock_valid_user_token(user_id, user_name)
    response = client.get('/permissions', headers={'Authorization': 'test_token'+str(uuid4())})
    data = json.loads(response.data)
    assert 'token' in data
    assert data['token'] == {'service': None, 'user': user_id, 'admin': False}
    assert 'permissions' in data
    assert 'GET' in data['permissions']
    valid_gets = set(['/api/V1/notifications/global', '/api/V1/notifications', '/api/V1/notification/<note_id>'])
    assert valid_gets == set(data['permissions']['GET'])
    valid_posts = set(['/api/V1/notifications/see', '/api/V1/notifications/unsee'])
    assert valid_posts == set(data['permissions']['POST'])


def test_permissions_service(client, requests_mock, mock_valid_service_token):
    service_name = 'fake_service'
    user_id = 'service_admin'
    user_name = 'Service User'
    mock_valid_service_token(user_id, user_name, service_name)
    response = client.get('/permissions', headers={'Authorization': 'serv_token-'+str(uuid4())})
    data = json.loads(response.data)
    assert 'token' in data
    assert data['token'] == {'service': service_name, 'user': user_id, 'admin': False}
    assert 'permissions' in data
    assert 'GET' in data['permissions']
    valid_gets = set(['/api/V1/notifications/global', '/api/V1/notifications', '/api/V1/notification/<note_id>'])
    assert valid_gets == set(data['permissions']['GET'])
    valid_posts = set(['/api/V1/notifications/see', '/api/V1/notifications/unsee', '/api/V1/notification'])
    assert valid_posts == set(data['permissions']['POST'])


def test_permissions_admin(client, requests_mock, mock_valid_admin_token):
    user_id = 'service_user'
    user_name = 'Service User'
    mock_valid_admin_token(user_id, user_name)
    response = client.get('/permissions', headers={'Authorization': 'admin_token-'+str(uuid4())})
    data = json.loads(response.data)
    assert 'token' in data
    assert data['token'] == {'service': None, 'user': user_id, 'admin': True}
    assert 'permissions' in data
    assert 'GET' in data['permissions']
    valid_gets = set(['/api/V1/notifications/global', '/api/V1/notifications', '/api/V1/notification/<note_id>'])
    assert valid_gets == set(data['permissions']['GET'])
    valid_posts = set(['/api/V1/notifications/see', '/api/V1/notifications/unsee', '/api/V1/notification/global'])
    assert valid_posts == set(data['permissions']['POST'])


def test_permissions_bad_token(client, mock_invalid_user_token):
    user_id = 'bad_user'
    mock_invalid_user_token(user_id)
    response = client.get('/permissions', headers={'Authorization': 'bad_token-'+str(uuid4())})
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error']['http_code'] == 403
    assert data['error']['message'] == 'Invalid token'


def test_server_illegal_param(client, mock_valid_service_token):
    mock_valid_service_token('service_admin', 'serv_pw', 'SomeService')
    response = client.post('/api/V1/notification', headers={'Authorization': 'token-'+str(uuid4())}, json=['bad', 'format'])
    data = json.loads(response.data)
    _validate_error(data, {'http_code': 400, 'http_status': 'Bad Request', 'message': 'Expected a JSON object as an input.'})


def test_server_invalid_token(client, mock_invalid_user_token):
    user_id = 'a_user'
    mock_invalid_user_token(user_id)
    response = client.get('/api/V1/notifications', headers={'Authorization': 'token-'+str(uuid4())})
    data = json.loads(response.data)
    _validate_error(data, {'http_code': 403, 'http_status': 'Forbidden', 'message': 'Invalid token'})


def test_server_note_not_found(client, mongo, mock_valid_user_token):
    user_id = 'a_user'
    user_name = 'A User'
    mock_valid_user_token(user_id, user_name)
    response = client.get('/api/V1/notification/fake_note', headers={'Authorization': 'token-'+str(uuid4())})
    data = json.loads(response.data)
    _validate_error(data, {'http_code': 404, 'http_status': 'Not Found', 'message': 'Cannot find notification with id fake_note.'})


def test_server_404(client):
    path = '/not/a/real/path'
    response = client.get(path)
    data = json.loads(response.data)
    _validate_error(data, {'http_code': 404, 'http_status': 'Not Found', 'message': 'Path {} not found.'.format(path)})


def test_server_missing_params(client, mock_valid_service_token):
    """
    Calls the API, but here we're just checking that the proper error gets raised from the server.
    The API tests will make sure the error content is correct.
    """
    mock_valid_service_token('service_admin', 'serv_pw', 'SomeService')
    response = client.post('/api/V1/notification', headers={'Authorization': 'token-'+str(uuid4())}, json={'actor': 'nope'})
    data = json.loads(response.data)
    _validate_error(data, {
        'http_code': 422,
        'http_status': 'Unprocessable Entity',
        'message': 'Missing parameters - verb, object, level, target'
    })


def test_server_405(client):
    response = client.get('/api/V1/notification')
    data = json.loads(response.data)
    _validate_error(data, {'http_code': 405, 'http_status': 'Method Not Allowed', 'message': 'Method not allowed'})


def test_server_auth_error(client, mock_auth_error):
    response = client.get('/api/V1/notifications', headers={'Authorization': 'token-'+str(uuid4())})
    data = json.loads(response.data)
    _validate_error(data, {
        "http_code": 500,
        "http_status": "Internal Server Error",
        "message": "Unable to fetch authentication information"
    })


def test_server_500(client, mock_valid_user_token):
    pass


def _validate_error(data, std_error):
    """
    Validates an error returned by the service.
    :param data: dict - should have a single key "error"
    :param std_error: dict - the standard to compare against. The keys and values here are expected to
        all be in data['error']
    """
    assert 'error' in data
    for k in std_error:
        assert k in data['error']
        assert data['error'][k] == std_error[k]