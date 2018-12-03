import pytest
import requests
import json
import os
import uuid
from feeds.auth import (
    validate_user_token,
    validate_service_token,
    get_auth_token,
    is_feeds_admin
)
from .util import test_config
from feeds.exceptions import InvalidTokenError

cfg = test_config()


def test_validate_service_token_ok(requests_mock):

    # test service token
    token = 'fake_token' + str(uuid.uuid4())
    test_name = 'fake_service'
    user = 'service_admin'
    requests_mock.get('{}/api/V2/token'.format(cfg.get('feeds', 'auth-url')),
                      text=json.dumps({'type': 'Service', 'user': user}))
    requests_mock.get('{}/api/V2/me'.format(cfg.get('feeds', 'auth-url')),
                      text=json.dumps({}))
    assert (validate_service_token(token) == test_name)


def test_validate_service_token_fail(requests_mock):

    token = 'fake_token' + str(uuid.uuid4())
    test_user = 'test_user'
    requests_mock.get('{}/api/V2/token'.format(cfg.get('feeds', 'auth-url')),
                      text=json.dumps({'user': test_user}))
    requests_mock.get('{}/api/V2/me'.format(cfg.get('feeds', 'auth-url')),
                      text=json.dumps({'customroles': []}))

    with pytest.raises(InvalidTokenError) as e:
        validate_service_token(token)
    assert "Authentication token must be a Service token." in str(e.value)


def test_is_feeds_admin_ok(requests_mock):
    # test service token - should fail
    token = 'fake_token' + str(uuid.uuid4())
    test_name = 'test_name'
    requests_mock.get('{}/api/V2/token'.format(cfg.get('feeds', 'auth-url')),
                      text=json.dumps({'type': 'Service', 'name': test_name}))
    requests_mock.get('{}/api/V2/me'.format(cfg.get('feeds', 'auth-url')),
                      text=json.dumps({}))
    assert is_feeds_admin(token) == False

    # test feeds admin user token
    token = 'fake_token' + str(uuid.uuid4())
    test_user = 'test_user'
    requests_mock.get('{}/api/V2/token'.format(cfg.get('feeds', 'auth-url')),
                      text=json.dumps({'user': test_user}))
    requests_mock.get('{}/api/V2/me'.format(cfg.get('feeds', 'auth-url')),
                      text=json.dumps({'customroles': ['FEEDS_ADMIN']}))
    assert is_feeds_admin(token)

    # test common user token
    token = 'fake_token' + str(uuid.uuid4())
    test_user = 'test_user'
    requests_mock.get('{}/api/V2/token'.format(cfg.get('feeds', 'auth-url')),
                      text=json.dumps({'user': test_user}))
    requests_mock.get('{}/api/V2/me'.format(cfg.get('feeds', 'auth-url')),
                      text=json.dumps({'customroles': []}))
    assert not is_feeds_admin(token)
