"""
This module handles authentication management. This mainly means:
* validating auth tokens
* validating user ids
"""

from .config import get_config
import requests
import json
from .exceptions import (
    InvalidTokenError,
    TokenLookupError,
    MissingTokenError
)
from .util import epoch_ms
from cachetools import (
    Cache,
    TTLCache
)
config = get_config()
AUTH_URL = config.auth_url
AUTH_API_PATH = '/api/V2/'
CACHE_EXPIRE_TIME = 300  # seconds


class TokenCache(TTLCache):
    """
    Extends the TTLCache to handle KBase auth tokens.
    So they have a base expiration of 5 minutes,
    but expire sooner if the token itself expires.
    """
    def __getitem__(self, key, cache_getitem=Cache.__getitem__):
        token = super(TokenCache, self).__getitem__(key, cache_getitem=cache_getitem)
        if token.get('expires', 0) <= epoch_ms():
            return self.__missing__(key)
        else:
            return token


__token_cache = TokenCache(1000, CACHE_EXPIRE_TIME)
__user_cache = TTLCache(1000, CACHE_EXPIRE_TIME)


def validate_service_token(token):
    """
    Validates a service token. If valid, and of type Service, returns the token name.
    If invalid, raises an InvalidTokenError. If any other errors occur, raises
    a TokenLookupError.

    TODO: I know this is going to be rife with issues. The name of the token doesn't have
    to be the service. But as long as it's a Service token, then it came from in KBase, so
    everything should be ok.
    """
    token = __fetch_token(token)
    if token.get('type') == 'Service':
        service = config.uid_to_service.get(token.get('user'))
        if service is None:
            raise InvalidTokenError("Authentication token does not come from a known service.")
        else:
            return service
    else:
        raise InvalidTokenError("Authentication token must be a Service token.")


def is_feeds_admin(token):
    """
    check token associated user has 'FEEDS_ADMIN' customroles
    """
    token = __fetch_token(token)
    roles = token.get('customroles')
    if roles is not None and 'FEEDS_ADMIN' in roles:
        return True
    else:
        return False


def validate_user_token(token):
    """
    Validates a user auth token.
    If valid, returns the user id. If invalid, raises an InvalidTokenError.
    If debug is True, always validates and returns a nonsense user name
    """
    return __fetch_token(token)['user']


def validate_user_id(user_id):
    """
    Validates whether a SINGLE user is real or not.
    Returns a boolean.
    """
    return user_id in validate_user_ids([user_id])


def validate_user_ids(user_ids):
    """
    Validates whether users are real or not.
    Returns the parsed response from the server, as a dict. Each
    key is a user that exists, each value is their user name.
    Raises an HTTPError if something bad happens.
    """
    users = dict()
    # fetch ones we know of from the cache
    for user_id in user_ids:
        try:
            users[user_id] = __user_cache[user_id]
        except KeyError:
            pass
    # now we have a partial list. the ones that weren't found will
    # not be in the users dict. Use set difference to find the
    # remaining user ids.
    filtered_users = set(user_ids).difference(set(users))
    if not filtered_users:
        return users
    r = __auth_request('users?list={}'.format(','.join(filtered_users)), config.auth_token)
    found_users = json.loads(r.content)
    __user_cache.update(found_users)
    users.update(found_users)
    return users


def get_auth_token(request, required=True):
    token = request.headers.get('Authorization')
    if not token and required:
        raise MissingTokenError()
    return token


def __fetch_token(token):
    """
    Returns token info from the auth server. Caches it locally for a while.
    If the token is invalid or there's any other auth problems, either
    an InvalidTokenError or TokenLookupError gets raised.
    """
    try:
        fetched = __token_cache.get(token)
    except KeyError:  # this wants to throw a KeyError in some tests. Don't know why.
        fetched = None
    if fetched is not None:
        return fetched
    else:
        try:
            r = __auth_request('token', token)
            token_info = json.loads(r.content)
            # includes customroles info
            r_me = __auth_request('me', token)
            token_me_info = json.loads(r_me.content)
            token_info['customroles'] = token_me_info.get('customroles')
            __token_cache[token] = token_info
            return token_info
        except requests.HTTPError as e:
            _handle_errors(e)


def __auth_request(path, token):
    """
    Makes a request of the auth server after cramming the token in a header.
    Only makes GET requests, since that's all we should need.
    """
    headers = {'Authorization': token}
    r = requests.get(AUTH_URL + AUTH_API_PATH + path, headers=headers)
    # the requests that fail based on the token (401, 403) get returned for the
    # calling function to turn into an informative error
    # others - 404, 500 - get raised
    r.raise_for_status()
    return r


def _handle_errors(err):
    if err.response.status_code == 403:
        err_content = json.loads(err.response.content)
        err_msg = err_content.get('error', {}).get('apperror', 'Invalid token')
        raise InvalidTokenError(msg=err_msg, http_error=err)
    else:
        raise TokenLookupError(http_error=err)
