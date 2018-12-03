import os
import configparser
import pytest
import tempfile
import json
import feeds
import test.util as test_util
from .util import test_config
from .mongo_controller import MongoController
import shutil


def pytest_sessionstart(session):
    os.environ['AUTH_TOKEN'] = 'foo'
    os.environ['FEEDS_CONFIG'] = os.path.join(os.path.dirname(__file__), 'test.cfg')

def pytest_sessionfinish(session, exitstatus):
    pass

@pytest.fixture(scope="module")
def mongo():
    mongoexe = test_util.get_mongo_exe()
    tempdir = test_util.get_temp_dir()
    mongo = MongoController(mongoexe, tempdir)
    print("running MongoDB {} on port {} in dir {}".format(
        mongo.db_version, mongo.port, mongo.temp_dir
    ))
    feeds.config.__config.db_port = mongo.port
    feeds.storage.mongodb.connection._connection = None

    yield mongo
    del_temp = test_util.get_delete_temp_files()
    print("Shutting down MongoDB,{} deleting temp files".format(" not" if not del_temp else ""))
    mongo.destroy(del_temp)
    if del_temp:
        shutil.rmtree(test_util.get_temp_dir())

@pytest.fixture(scope="module")
def app():
    from feeds.server import create_app
    db_fd, db_path = tempfile.mkstemp()
    app = create_app({
        'TESTING': True
    })

    yield app
    os.close(db_fd)
    os.unlink(db_path)

@pytest.fixture(scope="module")
def client(app):
    return app.test_client()

@pytest.fixture
def mock_valid_user(requests_mock):
    """
    Use this to mock a valid user name sent to the service as a target or recipient of a
    notification. Can use as a fixture as follows:
    def test_something(mock_valid_user):
        mock_valid_user("wjriehl", "Bill Riehl")
        ... continue with test that uses auth. Now wjriehl is the expected user ...
    """
    def auth_valid_user(user_id, user_name):
        cfg = test_config()
        auth_url = cfg.get('feeds', 'auth-url')
        requests_mock.get('{}/api/V2/users?list={}'.format(auth_url, user_id),
            text=json.dumps({user_id: user_name}))
    return auth_valid_user

@pytest.fixture
def mock_invalid_user(requests_mock):
    """
    Use this to mock an invalid user name being sent to the service as a target or recipient of
    a notification. Use as follows:
    def test_bad_user(mock_invalid_user):
        mock_invalid_user("not_a_real_user")
        ... continue with test. auth will fail, and should return "not_a_real_user" as the user that was attempted ...
    """
    def auth_invalid_user(user_id):
        cfg = test_config()
        requests_mock.get('{}/api/V2/users?list={}'.format(cfg.get('feeds', 'auth-url'), user_id), text="{}")
    return auth_invalid_user

@pytest.fixture
def mock_valid_user_token(requests_mock):
    """
    Use this to mock a valid authenticated request coming from a user (not an admin or service).
    Use the fixture as follows:
    def test_something(mock_valid_user_token):
        mock_valid_user_token('someuser', 'Some User')
        ... continue test ...
    """
    def auth_valid_user_token(user_id, user_name):
        cfg = test_config()
        auth_url = cfg.get('feeds', 'auth-url')
        requests_mock.get('{}/api/V2/token'.format(auth_url), json={
            'user': user_id,
            'type': 'Login',
            'name': None
        })
        requests_mock.get('{}/api/V2/me'.format(auth_url), json={
            'customroles': [],
            'display': user_name,
            'user': user_id
        })
    return auth_valid_user_token

@pytest.fixture
def mock_valid_service_token(requests_mock):
    """
    Use this to mock a valid authenticated request coming from a service (not a user).
    Use as follows:
    def test_something(mock_valid_service_token):
        mock_valid_service_token('some_user', 'Some User', 'MyKBaseService')
        ...continue test...
    """
    def auth_valid_service_token(user_id, user_name, service_name):
        cfg = test_config()
        auth_url = cfg.get('feeds', 'auth-url')
        requests_mock.get('{}/api/V2/token'.format(auth_url), json={
            'user': user_id,
            'type': 'Service',
            'name': service_name  # only really in the config, but that's ok for now.
        })
        requests_mock.get('{}/api/V2/me'.format(auth_url), json={
            'customroles': [],
            'display': user_name,
            'user': user_id
        })
    return auth_valid_service_token

@pytest.fixture
def mock_valid_admin_token(requests_mock):
    """
    Use this to mock a valid authenticated request coming from a Feeds admin (i.e. a user
    with the FEEDS_ADMIN custom role). Use as follows:
        def test_something(mock_valid_admin_token):
            mock_valid_admin_token('some_admin', 'Valid Admin')
            ... rest of test ...
    """
    def auth_valid_admin_token(user_id, user_name):
        cfg = test_config()
        auth_url = cfg.get('feeds', 'auth-url')
        requests_mock.get('{}/api/V2/token'.format(auth_url), json={
            'user': user_id,
            'type': 'Login',
            'name': None
        })
        requests_mock.get('{}/api/V2/me'.format(auth_url), json={
            'customroles': ['FEEDS_ADMIN'],
            'display': user_name,
            'user': user_id
        })
    return auth_valid_admin_token

@pytest.fixture
def mock_invalid_user_token(requests_mock):
    """
    Mocks an invalid (for whatever reason) user token. Probably should be treated as present,
    but expired.
    As above, just call it inside your test as:
    mock_invalid_user_token(user_id)
    """
    def auth_invalid_user_token(user_id):
        cfg = test_config()
        auth_url = cfg.get('feeds', 'auth-url')
        requests_mock.register_uri('GET', '{}/api/V2/token'.format(auth_url),
            status_code=403,
            json={
                "error": {
                    "appcode": 10020,
                    "apperror": "Invalid token",
                    "httpcode": 403,
                    "httpstatus": "Unauthorized"
                }
            }
        )
    return auth_invalid_user_token

@pytest.fixture
def mock_auth_error(requests_mock):
    cfg = test_config()
    auth_url = cfg.get('feeds', 'auth-url')
    requests_mock.register_uri('GET', '{}/api/V2/token'.format(auth_url),
        status_code=500,
        json={
            "error": {
                "httpcode": 500,
                "httpstatus": "FAIL",
                "apperror": "Something very bad happened, mm'kay?"
            }
        })
