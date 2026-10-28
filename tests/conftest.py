import pytest
import responses

from fuga.api import FUGAClient

API_URL = "https://fuga.test/api/v2"
COOKIE = "connect.sid=test-cookie"


@pytest.fixture
def mocked():
    """Every HTTP call goes to `responses`; any request not registered fails."""
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def client(mocked):
    """A v2 client that already holds a cookie, so it never logs in."""
    return FUGAClient(API_URL, auth_cookie=COOKIE)
