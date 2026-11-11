from datetime import datetime, timezone

import pytest
import responses

from fuga.api import FUGAV3TokenClient

API_URL = "https://fuga.test/api/v3"
TOKEN = "test-token"
# Far enough ahead that the token never expires during a test
NEVER = datetime(2100, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def mocked():
    """Every HTTP call goes to `responses`; any request not registered fails."""
    with responses.RequestsMock() as rsps:
        yield rsps


def make_client(api_url=API_URL, **kwargs):
    """A client holding a token that won't expire, so it never asks for one."""
    return FUGAV3TokenClient(api_url, TOKEN, NEVER, **kwargs)


@pytest.fixture
def client(mocked):
    return make_client()
