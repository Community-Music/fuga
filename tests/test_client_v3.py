import base64
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
import requests
from responses import matchers

from fuga.api import (
    DEFAULT_TIMEOUT,
    RENEWAL_RETRY,
    TOKEN_RENEWAL_MARGIN,
    TOKEN_REQUEST_TIMEOUT,
    FUGAAuthError,
    FUGAV3Client,
    MemoryTokenStore,
)

from .test_client import multipart_field

API_URL = "https://fuga.test/api/v3"
TOKEN_URL = f"{API_URL}/oauth/token"
BASIC = "Basic " + base64.b64encode(b"client-1:secret-1").decode()
LIFETIME = 29999  # seconds, what FUGA returned on 27 Oct 2026
NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
EXPIRES = NOW + timedelta(seconds=LIFETIME)
RENEW = EXPIRES - TOKEN_RENEWAL_MARGIN


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr("fuga.api._now", clock)
    return clock


@pytest.fixture(autouse=True)
def sleeps(monkeypatch):
    """Every backoff wait, in seconds, without waiting."""
    waits: list[float] = []
    monkeypatch.setattr("fuga.api.time.sleep", waits.append)
    return waits


@pytest.fixture
def store():
    return MemoryTokenStore()


def save(store, token, expires_at, renew_after=None):
    """Store a token as a renewal would: due TOKEN_RENEWAL_MARGIN before expiry."""
    store.save(token, expires_at, renew_after or expires_at - TOKEN_RENEWAL_MARGIN)


def make_client(store, **kwargs):
    return FUGAV3Client(API_URL, "client-1", "secret-1", store, **kwargs)


@pytest.fixture
def client(store):
    return make_client(store)


def token_response(mocked, token="tok-1", status=200, json=None, lifetime=LIFETIME):
    body = (
        json
        if json is not None
        else {"access_token": token, "token_type": "Bearer", "expires_in": lifetime}
    )
    return mocked.post(TOKEN_URL, json=body, status=status)


def bearer(token):
    return [matchers.header_matcher({"Authorization": f"Bearer {token}"})]


def token_requests(mocked):
    return sum(c.request.url == TOKEN_URL for c in mocked.calls)


# ---- getting a token ----


def test_client_is_v3():
    assert FUGAV3Client.api_version == "v3"


def test_constructor_does_not_request_a_token(mocked, store):
    make_client(store)

    assert len(mocked.calls) == 0


def test_first_request_exchanges_the_credentials_for_a_token(
    mocked, client, store, caplog
):
    token = token_response(mocked)
    labels = mocked.get(f"{API_URL}/labels", json={"label": []}, match=bearer("tok-1"))

    with caplog.at_level(logging.INFO, logger="fuga.api"):
        assert client.get("/labels")["success"] is True

    assert token.call_count == 1
    assert labels.call_count == 1
    request = mocked.calls[0].request
    assert request.headers["Authorization"] == BASIC
    assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
    # FUGA's Login guide: omit `scope`
    assert request.body == "grant_type=client_credentials"
    assert store.load() == ("tok-1", EXPIRES, RENEW)
    assert "Got a FUGA token" in caplog.text


def test_one_token_serves_many_requests(mocked, client):
    token = token_response(mocked)
    mocked.get(f"{API_URL}/labels", json={}, match=bearer("tok-1"))

    client.get("/labels")
    client.get("/labels")

    assert token.call_count == 1


def test_the_token_request_has_its_own_timeout(mocked, store):
    """It runs under the store's lock, so it doesn't wait as long as other calls."""
    token_response(mocked)
    mocked.get(f"{API_URL}/labels", json={})

    make_client(store).get("/labels")
    make_client(MemoryTokenStore(), timeout=(5, 60)).get("/labels")

    timeouts = [c.request.req_kwargs["timeout"] for c in mocked.calls]
    assert timeouts == [
        TOKEN_REQUEST_TIMEOUT,
        DEFAULT_TIMEOUT,
        TOKEN_REQUEST_TIMEOUT,
        (5, 60),
    ]
    assert TOKEN_REQUEST_TIMEOUT == (DEFAULT_TIMEOUT[0], 30)


def test_a_stored_token_is_used_without_a_token_request(mocked, client, store):
    save(store, "stored", NOW + TOKEN_RENEWAL_MARGIN + timedelta(minutes=1))
    labels = mocked.get(f"{API_URL}/labels", json={}, match=bearer("stored"))

    assert client.get("/labels")["success"] is True
    assert labels.call_count == 1


def test_a_stored_token_due_for_renewal_is_renewed(mocked, client, store):
    save(store, "old", NOW + TOKEN_RENEWAL_MARGIN - timedelta(minutes=1))
    token = token_response(mocked, token="new")
    mocked.get(f"{API_URL}/labels", json={}, match=bearer("new"))

    assert client.get("/labels")["success"] is True
    assert token.call_count == 1
    assert store.load() == ("new", EXPIRES, RENEW)


def test_the_token_is_renewed_when_it_reaches_the_margin(mocked, client, clock):
    token_response(mocked, token="tok-1")
    token_response(mocked, token="tok-2")
    first = mocked.get(f"{API_URL}/labels", json={}, match=bearer("tok-1"))
    second = mocked.get(f"{API_URL}/labels", json={}, match=bearer("tok-2"))

    client.get("/labels")
    clock.advance(seconds=LIFETIME - TOKEN_RENEWAL_MARGIN.total_seconds())
    client.get("/labels")

    assert first.call_count == 1
    assert second.call_count == 1


def test_a_short_lived_token_is_renewed_halfway_through_its_life(
    mocked, client, store, clock
):
    """A token shorter than the margin would otherwise be due on arrival."""
    token_response(mocked, token="tok-1", lifetime=3600)
    token_response(mocked, token="tok-2", lifetime=3600)
    mocked.get(f"{API_URL}/labels", json={})

    client.get("/labels")
    clock.advance(minutes=29)
    client.get("/labels")
    assert token_requests(mocked) == 1
    assert store.load() == (
        "tok-1",
        NOW + timedelta(hours=1),
        NOW + timedelta(minutes=30),
    )

    clock.advance(minutes=1)
    client.get("/labels")
    assert token_requests(mocked) == 2


def test_a_client_uses_the_token_another_client_saved(mocked, store):
    token = token_response(mocked)
    mocked.get(f"{API_URL}/labels", json={}, match=bearer("tok-1"))

    make_client(store).get("/labels")
    make_client(store).get("/labels")

    assert token.call_count == 1


def test_authenticate_keeps_a_token_that_is_not_due(mocked, client, store):
    save(store, "tok-1", EXPIRES)
    mocked.get(f"{API_URL}/labels", json={})

    client.get("/labels")
    client.authenticate()

    assert token_requests(mocked) == 0
    assert store.load() == ("tok-1", EXPIRES, RENEW)


# ---- ensure_token ----


def test_ensure_token_returns_a_token_that_is_not_due_without_a_request(
    mocked, client, store
):
    save(store, "tok-1", EXPIRES)

    assert client.ensure_token() == ("tok-1", EXPIRES)
    assert len(mocked.calls) == 0


def test_ensure_token_renews_a_token_that_is_due(mocked, client, store):
    save(store, "old", NOW + timedelta(minutes=60))
    token_response(mocked, token="new")

    assert client.ensure_token() == ("new", EXPIRES)


def test_ensure_token_returns_a_token_with_at_least_min_valid_left(client, store):
    save(store, "tok-1", EXPIRES)

    assert client.ensure_token(min_valid=timedelta(minutes=60)) == ("tok-1", EXPIRES)


def test_ensure_token_refuses_a_kept_token_with_less_than_min_valid_left(
    mocked, client, store
):
    """After a refused renewal the kept token is too short to hand over."""
    save(store, "tok-1", NOW + timedelta(minutes=50))
    token_response(mocked, status=401, json={"code": "AUTHENTICATION_FAILED"})

    assert client.ensure_token() == ("tok-1", NOW + timedelta(minutes=50))
    with pytest.raises(FUGAAuthError, match="less than 1:00:00"):
        client.ensure_token(min_valid=timedelta(minutes=60))
    # The short token makes it try once more before giving up
    assert token_requests(mocked) == 2


def test_ensure_token_renews_a_token_not_yet_due_with_less_than_min_valid_left(
    mocked, client, clock
):
    """A 100-minute token is due at 50 minutes, but has 55 left at 45."""
    token_response(mocked, token="tok-1", lifetime=6000)
    token_response(mocked, token="tok-2", lifetime=6000)

    client.ensure_token()
    clock.advance(minutes=45)

    assert client.ensure_token(min_valid=timedelta(minutes=60)) == (
        "tok-2",
        NOW + timedelta(minutes=145),
    )
    assert token_requests(mocked) == 2


def test_a_refused_renewal_for_min_valid_keeps_the_time_the_token_is_due(
    mocked, client, store
):
    """Other clients still renew the token when it is due, not sooner."""
    save(
        store,
        "tok-1",
        NOW + timedelta(minutes=55),
        renew_after=NOW + timedelta(minutes=20),
    )
    token_response(mocked, status=401, json={"code": "AUTHENTICATION_FAILED"})

    with pytest.raises(FUGAAuthError, match="less than 1:00:00"):
        client.ensure_token(min_valid=timedelta(minutes=60))
    assert store.load() == (
        "tok-1",
        NOW + timedelta(minutes=55),
        NOW + timedelta(minutes=20),
    )


def test_ensure_token_raises_when_a_new_token_is_still_too_short(mocked, client):
    token_response(mocked, lifetime=3000)

    with pytest.raises(FUGAAuthError, match="less than 1:00:00"):
        client.ensure_token(min_valid=timedelta(minutes=60))
    assert token_requests(mocked) == 1


# ---- refused token requests, with no valid token ----


@pytest.mark.parametrize(
    ("status", "body"),
    [
        # Handling errors guide: the token endpoint's own error codes
        (
            401,
            {
                "status": 401,
                "code": "AUTHENTICATION_FAILED",
                "message": "The provided credentials are invalid.",
                "serviceName": "CERBERUS",
            },
        ),
        (400, {"code": "UNSUPPORTED_GRANT_TYPE", "message": "Unsupported grant"}),
        # v3 spec: the organisation has no API access
        (403, {"code": "API_ACCESS_DISABLED", "message": "API access is disabled"}),
    ],
)
def test_refused_credentials_raise_with_fugas_code_and_message(
    mocked, client, status, body
):
    token_response(mocked, status=status, json=body)

    with pytest.raises(FUGAAuthError) as raised:
        client.get("/labels")

    assert str(status) in str(raised.value)
    assert body["code"] in str(raised.value)
    assert body["message"] in str(raised.value)
    assert len(mocked.calls) == 1


def test_a_non_json_refusal_raises_with_the_body(mocked, client):
    mocked.post(TOKEN_URL, body="Bad gateway", status=502)

    with pytest.raises(FUGAAuthError, match="502 Bad gateway"):
        client.get("/labels")


def test_auth_error_is_still_a_value_error(mocked, client):
    token_response(mocked, status=401, json={"code": "AUTHENTICATION_FAILED"})

    with pytest.raises(ValueError):
        client.get("/labels")


@pytest.mark.parametrize(
    "body",
    [
        {"token_type": "Bearer", "expires_in": LIFETIME},
        {"access_token": "tok-1"},
        {"access_token": "tok-1", "expires_in": 0},
        {"access_token": "tok-1", "expires_in": -5},
        {"access_token": "tok-1", "expires_in": True},
    ],
)
def test_a_token_response_without_a_token_or_lifetime_raises(mocked, client, body):
    token_response(mocked, json=body)

    with pytest.raises(FUGAAuthError, match="no access_token or expires_in"):
        client.get("/labels")


def test_a_network_failure_on_the_token_request_is_returned(mocked, client):
    mocked.post(TOKEN_URL, body=requests.ConnectionError("reset"))

    assert client.get("/labels") == {
        "success": False,
        "status_code": None,
        "error": {"message": "Token request failed: reset"},
    }


# ---- with no valid token, a failed token request pauses every client ----


def test_after_a_refusal_with_no_token_no_client_asks_again_for_a_while(
    mocked, store, clock
):
    token = token_response(mocked, status=401, json={"code": "AUTHENTICATION_FAILED"})

    with pytest.raises(FUGAAuthError):
        make_client(store).get("/labels")
    resp = make_client(store).get("/labels")

    assert resp["success"] is False
    assert resp["status_code"] is None
    assert "not asking again until" in resp.get("error", {})["message"]
    assert token.call_count == 1
    assert store.load() == ("", NOW, NOW + RENEWAL_RETRY)

    clock.advance(minutes=5)
    with pytest.raises(FUGAAuthError):
        make_client(store).get("/labels")
    assert token.call_count == 2


class TransactionalStore(MemoryTokenStore):
    """Undoes saves made under `lock()` if the block raises, as a database would."""

    @contextmanager
    def lock(self):
        before = self._token
        try:
            yield
        except BaseException:
            self._token = before
            raise


def test_the_pause_survives_a_store_that_rolls_back_on_errors(mocked):
    store = TransactionalStore()
    token = token_response(mocked, status=401, json={"code": "AUTHENTICATION_FAILED"})

    with pytest.raises(FUGAAuthError):
        make_client(store).get("/labels")

    assert store.load() == ("", NOW, NOW + RENEWAL_RETRY)
    assert make_client(store).get("/labels")["status_code"] is None
    assert token.call_count == 1


def test_after_rate_limiting_with_no_token_no_client_asks_again_for_a_while(
    mocked, store, sleeps
):
    token = mocked.post(TOKEN_URL, status=429)

    assert make_client(store).get("/labels")["status_code"] == 429
    assert make_client(store).get("/labels")["status_code"] is None

    assert token.call_count == 6
    assert sleeps == [1, 2, 4, 8, 16]


def test_a_new_token_ends_the_pause(mocked, store, clock):
    token_response(mocked, status=401, json={"code": "AUTHENTICATION_FAILED"})
    token_response(mocked, token="tok-1")
    labels = mocked.get(f"{API_URL}/labels", json={}, match=bearer("tok-1"))

    with pytest.raises(FUGAAuthError):
        make_client(store).get("/labels")
    clock.advance(minutes=5)

    assert make_client(store).get("/labels")["success"] is True
    assert labels.call_count == 1
    assert store.load() == (
        "tok-1",
        NOW + timedelta(minutes=5, seconds=LIFETIME),
        NOW + timedelta(minutes=5, seconds=LIFETIME) - TOKEN_RENEWAL_MARGIN,
    )


# ---- a refused renewal keeps a token that is still valid ----


def test_a_refused_renewal_keeps_the_valid_token(mocked, client, store, caplog):
    save(store, "tok-1", NOW + timedelta(minutes=60))
    token_response(mocked, status=401, json={"code": "AUTHENTICATION_FAILED"})
    labels = mocked.get(f"{API_URL}/labels", json={}, match=bearer("tok-1"))

    with caplog.at_level(logging.ERROR, logger="fuga.api"):
        assert client.get("/labels")["success"] is True

    assert labels.call_count == 1
    assert store.load() == ("tok-1", NOW + timedelta(minutes=60), NOW + RENEWAL_RETRY)
    assert "AUTHENTICATION_FAILED" in caplog.text
    assert "keeping the current token" in caplog.text


def test_a_network_failure_on_renewal_keeps_the_valid_token(
    mocked, client, store, caplog
):
    save(store, "tok-1", NOW + timedelta(minutes=60))
    mocked.post(TOKEN_URL, body=requests.ConnectionError("reset"))
    labels = mocked.get(f"{API_URL}/labels", json={}, match=bearer("tok-1"))

    with caplog.at_level(logging.ERROR, logger="fuga.api"):
        assert client.get("/labels")["success"] is True

    assert labels.call_count == 1
    assert store.load() == ("tok-1", NOW + timedelta(minutes=60), NOW + RENEWAL_RETRY)
    assert "Token request failed: reset" in caplog.text
    assert "keeping the current token" in caplog.text


def test_after_a_refused_renewal_every_client_waits_before_asking_again(
    mocked, store, clock
):
    save(store, "tok-1", NOW + timedelta(minutes=60))
    token_response(mocked, status=401, json={"code": "AUTHENTICATION_FAILED"})
    mocked.get(f"{API_URL}/labels", json={})

    make_client(store).get("/labels")
    make_client(store).get("/labels")
    assert token_requests(mocked) == 1

    clock.advance(minutes=5)
    make_client(store).get("/labels")
    assert token_requests(mocked) == 2


def test_a_refused_renewal_raises_once_the_token_expires(mocked, client, store, clock):
    save(store, "tok-1", NOW + timedelta(minutes=3))
    token_response(mocked, status=401, json={"code": "AUTHENTICATION_FAILED"})
    mocked.get(f"{API_URL}/labels", json={})

    assert client.get("/labels")["success"] is True
    # Put off only until the token expires, not the full RENEWAL_RETRY
    assert store.load() == (
        "tok-1",
        NOW + timedelta(minutes=3),
        NOW + timedelta(minutes=3),
    )

    clock.advance(minutes=3)
    with pytest.raises(FUGAAuthError, match="AUTHENTICATION_FAILED"):
        client.get("/labels")


# ---- 401: renew and retry once ----


def test_a_401_renews_the_token_and_retries(mocked, client, store):
    token_response(mocked, token="tok-1")
    token_response(mocked, token="tok-2")
    rejected = mocked.get(f"{API_URL}/labels", status=401, match=bearer("tok-1"))
    accepted = mocked.get(f"{API_URL}/labels", json={}, match=bearer("tok-2"))

    assert client.get("/labels")["success"] is True
    assert rejected.call_count == 1
    assert accepted.call_count == 1
    assert store.load() == ("tok-2", EXPIRES, RENEW)


def test_a_second_401_is_returned(mocked, client):
    token = token_response(mocked)
    labels = mocked.get(f"{API_URL}/labels", json={"code": "UNAUTHORIZED"}, status=401)

    resp = client.get("/labels")

    assert resp == {
        "success": False,
        "status_code": 401,
        "error": {"code": "UNAUTHORIZED"},
    }
    assert token.call_count == 2
    assert labels.call_count == 2


def test_a_401_uses_a_token_another_client_already_renewed(mocked, client, store):
    save(store, "tok-1", EXPIRES)
    mocked.get(f"{API_URL}/artists", json={}, match=bearer("tok-1"))
    client.get("/artists")
    # Another client renews the token, and FUGA now rejects tok-1
    save(store, "tok-2", EXPIRES)
    mocked.get(f"{API_URL}/labels", status=401, match=bearer("tok-1"))
    accepted = mocked.get(f"{API_URL}/labels", json={}, match=bearer("tok-2"))

    assert client.get("/labels")["success"] is True
    assert accepted.call_count == 1
    assert token_requests(mocked) == 0


def test_a_token_rejected_after_it_became_due_is_not_used_again(
    mocked, client, store, clock, sleeps
):
    """The request crosses `renew_after` while in flight, then FUGA answers 401."""
    save(store, "tok-1", EXPIRES, renew_after=NOW + timedelta(minutes=1))

    def labels(request):
        if request.headers["Authorization"] == "Bearer tok-1":
            clock.advance(minutes=2)
            return 401, {}, '{"code": "UNAUTHORIZED"}'
        return 200, {}, "{}"

    mocked.add_callback("GET", f"{API_URL}/labels", callback=labels)
    mocked.post(TOKEN_URL, status=429)
    token_response(mocked, token="tok-2")

    assert client.get("/labels")["success"] is True
    assert sleeps == [1]
    sent = [c.request.headers.get("Authorization") for c in mocked.calls]
    assert sent.count("Bearer tok-1") == 1


# ---- a failed renewal: one rule, whichever way it fails ----


class TokenEndpoint:
    """The token endpoint: fails as `kind` until `ok` is set, then gives tok-3."""

    def __init__(self, mocked, kind):
        self.kind = kind
        self.ok = False
        mocked.add_callback("POST", TOKEN_URL, callback=self.respond)

    def respond(self, request):
        if self.ok:
            body = {"access_token": "tok-3", "token_type": "Bearer"}
            return 200, {}, json.dumps(body | {"expires_in": LIFETIME})
        if self.kind == "refused":
            return 401, {}, '{"code": "AUTHENTICATION_FAILED"}'
        if self.kind == "rate-limited":
            return 429, {}, '{"code": "TOO_MANY_REQUESTS"}'
        if self.kind == "network":
            return requests.ConnectionError("reset")
        raise AssertionError("token requested during a pause")


def labels_rejecting_tok_1(request):
    if request.headers.get("Authorization") == "Bearer tok-1":
        return 401, {}, '{"code": "UNAUTHORIZED"}'
    return 200, {}, "{}"


# Each way a renewal can fail, and what ensure_token() raises for it
FAILURES = {
    "refused": "AUTHENTICATION_FAILED",
    "rate-limited": "rate-limited",
    "network": "Token request failed: reset",
    "paused": "not asking again",
}


@pytest.mark.parametrize(
    ("kind", "kept", "entry"),
    [
        pytest.param(
            kind,
            kept,
            entry,
            id=f"{kind}, {'valid token' if kept else 'no valid token'}, {entry}",
        )
        for kind in FAILURES
        for kept in (False, True)
        for entry in ("call after a 401", "ensure_token")
        # A pause means the store holds no valid token
        if not (kind == "paused" and kept)
    ],
)
def test_a_failed_renewal(mocked, store, clock, caplog, kind, kept, entry):
    """
    Whichever way a renewal fails, a valid token FUGA hasn't rejected is
    kept. With none, every client waits out the pause without sending tok-1.
    """
    caplog.set_level(logging.WARNING, logger="fuga.api")
    endpoint = TokenEndpoint(mocked, kind)
    mocked.add_callback("GET", f"{API_URL}/labels", callback=labels_rejecting_tok_1)
    client = make_client(store)
    if entry == "call after a 401":
        save(store, "tok-1", EXPIRES)
        client.ensure_token()  # the client holds tok-1, which FUGA now rejects
    else:
        save(store, "tok-1", NOW)  # expired
    if kept:
        save(store, "tok-2", NOW + timedelta(minutes=60))  # due, still valid
    if kind == "paused":
        store.save("", NOW, NOW + RENEWAL_RETRY)

    # What the caller gets
    if entry == "call after a 401":
        resp = client.get("/labels")
        if kept:
            assert resp["success"] is True
        elif kind == "rate-limited":
            assert resp == {
                "success": False,
                "status_code": 429,
                "error": {"code": "TOO_MANY_REQUESTS"},
            }
        else:
            assert resp == {
                "success": False,
                "status_code": 401,
                "error": {"code": "UNAUTHORIZED"},
            }
    elif kept:
        assert client.ensure_token() == ("tok-2", NOW + timedelta(minutes=60))
    else:
        with pytest.raises(FUGAAuthError, match=FAILURES[kind]):
            client.ensure_token()

    # What the store holds, and what every client does until RENEWAL_RETRY
    requested = token_requests(mocked)
    if kept:
        assert store.load() == (
            "tok-2",
            NOW + timedelta(minutes=60),
            NOW + RENEWAL_RETRY,
        )
        assert "keeping the current token" in caplog.text
        for c in (client, make_client(store)):
            assert c.get("/labels")["success"] is True
            assert c.ensure_token() == ("tok-2", NOW + timedelta(minutes=60))
    else:
        assert store.load() == ("", NOW, NOW + RENEWAL_RETRY)
        for c in (client, make_client(store)):
            assert "not asking again" in c.get("/labels").get("error", {})["message"]
            with pytest.raises(FUGAAuthError, match="not asking again"):
                c.ensure_token()
    assert token_requests(mocked) == requested

    # After it, a new token
    clock.advance(minutes=5)
    endpoint.ok = True
    assert client.ensure_token() == ("tok-3", EXPIRES + timedelta(minutes=5))
    assert make_client(store).get("/labels")["success"] is True
    sent = [c.request.headers.get("Authorization") for c in mocked.calls]
    assert sent.count("Bearer tok-1") == (1 if entry == "call after a 401" else 0)


# ---- the store's lock ----


class RecordingStore(MemoryTokenStore):
    """Records lock, load and save calls; `on_lock` runs as the lock is taken."""

    def __init__(self, on_lock=None):
        super().__init__()
        self.events: list[str] = []
        self.on_lock = on_lock

    @contextmanager
    def lock(self):
        self.events.append("lock")
        if self.on_lock:
            self.on_lock(self)
        yield
        self.events.append("unlock")

    def load(self):
        self.events.append("load")
        return super().load()

    def save(self, access_token, expires_at, renew_after):
        self.events.append(f"save {access_token}")
        super().save(access_token, expires_at, renew_after)


def test_the_token_is_requested_and_saved_inside_the_lock(mocked):
    store = RecordingStore()

    def token(request):
        store.events.append("token request")
        return 200, {}, f'{{"access_token": "tok-1", "expires_in": {LIFETIME}}}'

    mocked.add_callback("POST", TOKEN_URL, callback=token)
    mocked.get(f"{API_URL}/labels", json={})

    make_client(store).get("/labels")

    assert store.events == [
        "load",
        "lock",
        "load",
        "token request",
        "save tok-1",
        "unlock",
    ]


def test_a_token_saved_while_waiting_for_the_lock_is_used(mocked):
    def renewed_elsewhere(store):
        MemoryTokenStore.save(store, "tok-other", EXPIRES, RENEW)

    store = RecordingStore(on_lock=renewed_elsewhere)
    labels = mocked.get(f"{API_URL}/labels", json={}, match=bearer("tok-other"))

    assert make_client(store).get("/labels")["success"] is True
    assert labels.call_count == 1
    assert "save tok-other" not in store.events


# ---- 429 on the token endpoint ----


def test_a_rate_limited_renewal_keeps_the_stored_token(
    mocked, client, store, sleeps, caplog
):
    save(store, "tok-1", NOW + timedelta(minutes=30))
    token = mocked.post(TOKEN_URL, json={"code": "TOO_MANY_REQUESTS"}, status=429)
    labels = mocked.get(f"{API_URL}/labels", json={}, match=bearer("tok-1"))

    with caplog.at_level(logging.WARNING, logger="fuga.api"):
        assert client.get("/labels")["success"] is True
        assert client.get("/labels")["success"] is True

    assert token.call_count == 1
    assert labels.call_count == 2
    assert sleeps == []
    assert store.load() == ("tok-1", NOW + timedelta(minutes=30), NOW + RENEWAL_RETRY)
    assert "Token request rate-limited; keeping the current token" in caplog.text


def test_after_a_rate_limited_renewal_every_client_waits(mocked, store):
    """cm-backend builds a client per task; none of them should ask again."""
    save(store, "tok-1", NOW + timedelta(minutes=30))
    token = mocked.post(TOKEN_URL, status=429)
    mocked.get(f"{API_URL}/labels", json={})

    for _ in range(5):
        assert make_client(store).get("/labels")["success"] is True

    assert token.call_count == 1


def test_a_kept_token_is_renewed_after_the_retry_time(mocked, client, store, clock):
    save(store, "tok-1", NOW + timedelta(minutes=30))
    mocked.post(TOKEN_URL, status=429)
    token_response(mocked, token="tok-2")
    mocked.get(f"{API_URL}/labels", json={}, match=bearer("tok-1"))
    renewed = mocked.get(f"{API_URL}/labels", json={}, match=bearer("tok-2"))

    client.get("/labels")
    clock.advance(minutes=5)
    client.get("/labels")

    assert renewed.call_count == 1


def test_a_rate_limited_token_request_without_a_valid_token_backs_off(
    mocked, client, sleeps
):
    mocked.post(TOKEN_URL, status=429)
    mocked.post(TOKEN_URL, status=429)
    token_response(mocked)
    mocked.get(f"{API_URL}/labels", json={}, match=bearer("tok-1"))

    assert client.get("/labels")["success"] is True
    assert sleeps == [1, 2]


def test_a_token_request_still_rate_limited_after_backing_off_returns_the_429(
    mocked, client, sleeps
):
    token = mocked.post(TOKEN_URL, json={"code": "TOO_MANY_REQUESTS"}, status=429)

    assert client.get("/labels") == {
        "success": False,
        "status_code": 429,
        "error": {"code": "TOO_MANY_REQUESTS"},
    }
    assert sleeps == [1, 2, 4, 8, 16]
    assert token.call_count == 6
    assert len(mocked.calls) == 6


def test_a_rate_limited_renewal_after_a_401_waits_rather_than_reuse_the_rejected_token(
    mocked, client, store, sleeps
):
    save(store, "tok-1", EXPIRES)
    mocked.get(f"{API_URL}/labels", status=401, match=bearer("tok-1"))
    mocked.post(TOKEN_URL, status=429)
    token_response(mocked, token="tok-2")
    accepted = mocked.get(f"{API_URL}/labels", json={}, match=bearer("tok-2"))

    assert client.get("/labels")["success"] is True
    assert accepted.call_count == 1
    assert sleeps == [1]


# ---- 429 on any other request: exponential backoff ----


def test_a_429_is_retried_with_exponential_backoff(mocked, client, store, sleeps):
    save(store, "tok-1", EXPIRES)
    mocked.get(f"{API_URL}/labels", status=429)
    mocked.get(f"{API_URL}/labels", status=429)
    mocked.get(f"{API_URL}/labels", json={"label": []})

    assert client.get("/labels") == {
        "success": True,
        "status_code": 200,
        "data": {"label": []},
    }
    assert sleeps == [1, 2]


def test_a_429_is_returned_after_the_last_retry(mocked, client, store, sleeps):
    save(store, "tok-1", EXPIRES)
    labels = mocked.get(
        f"{API_URL}/labels", json={"code": "TOO_MANY_REQUESTS"}, status=429
    )

    resp = client.get("/labels")

    assert resp == {
        "success": False,
        "status_code": 429,
        "error": {"code": "TOO_MANY_REQUESTS"},
    }
    assert labels.call_count == 6
    assert sleeps == [1, 2, 4, 8, 16]


def test_a_429_waits_as_long_as_retry_after_says(mocked, client, store, sleeps):
    save(store, "tok-1", EXPIRES)
    mocked.get(f"{API_URL}/labels", status=429, headers={"Retry-After": "30"})
    # Not a number of seconds: falls back to the schedule
    mocked.get(f"{API_URL}/labels", status=429, headers={"Retry-After": "soon"})
    mocked.get(f"{API_URL}/labels", json={})

    assert client.get("/labels")["success"] is True
    assert sleeps == [30, 2]


def test_a_429_with_a_retry_after_over_the_limit_is_returned(
    mocked, client, store, sleeps
):
    save(store, "tok-1", EXPIRES)
    labels = mocked.get(f"{API_URL}/labels", status=429, headers={"Retry-After": "61"})

    assert client.get("/labels")["status_code"] == 429
    assert labels.call_count == 1
    assert sleeps == []


def test_a_retry_after_at_the_limit_is_waited_for(mocked, client, store, sleeps):
    save(store, "tok-1", EXPIRES)
    mocked.get(f"{API_URL}/labels", status=429, headers={"Retry-After": "60"})
    mocked.get(f"{API_URL}/labels", json={})

    assert client.get("/labels")["success"] is True
    assert sleeps == [60]


def test_a_token_request_with_a_retry_after_over_the_limit_pauses(
    mocked, store, sleeps
):
    token = mocked.post(TOKEN_URL, status=429, headers={"Retry-After": "3600"})

    assert make_client(store).get("/labels")["status_code"] == 429
    assert make_client(store).get("/labels")["status_code"] is None
    assert token.call_count == 1
    assert sleeps == []


def test_a_rate_limited_token_request_waits_as_long_as_retry_after_says(
    mocked, client, sleeps
):
    mocked.post(TOKEN_URL, status=429, headers={"Retry-After": "12"})
    token_response(mocked)
    mocked.get(f"{API_URL}/labels", json={})

    assert client.get("/labels")["success"] is True
    assert sleeps == [12]


def test_other_failures_are_not_retried(mocked, client, store, sleeps):
    save(store, "tok-1", EXPIRES)
    labels = mocked.get(f"{API_URL}/labels", status=503)

    assert client.get("/labels")["status_code"] == 503
    assert labels.call_count == 1
    assert sleeps == []


def test_v3_errors_are_returned_as_fuga_sends_them(mocked, client, store):
    """Handling errors guide: one top-level {code, message} shape."""
    save(store, "tok-1", EXPIRES)
    body = {
        "code": "ENTITY_NOT_FOUND",
        "message": "Could not find {0} with ID {1}.",
        "messageVariables": ["Entity", "12717125371"],
    }
    mocked.get(f"{API_URL}/products/12717125371", json=body, status=404)

    assert client.get("/products/12717125371") == {
        "success": False,
        "status_code": 404,
        "error": body,
    }


# ---- uploads ----


@pytest.fixture
def audio_file(tmp_path):
    path = tmp_path / "track.wav"
    path.write_bytes(b"abcdefghij")  # 10 bytes: chunks of 4, 4, 2
    return path


def test_upload_renews_the_token_between_chunks(mocked, client, clock, audio_file):
    token_response(mocked, token="tok-1")
    token_response(mocked, token="tok-2")
    mocked.post(f"{API_URL}/upload/start", json={"id": "upload-1"})

    def chunk(request):
        # The first chunk takes long enough to make the token due for renewal
        if request.headers["Authorization"] == "Bearer tok-1":
            clock.advance(seconds=LIFETIME - TOKEN_RENEWAL_MARGIN.total_seconds())
        return 200, {}, '{"success": true}'

    mocked.add_callback("POST", f"{API_URL}/upload", callback=chunk)
    mocked.post(f"{API_URL}/upload/finish", json={"success": True})

    resp = client.upload_file(
        str(audio_file), {"id": "asset-1", "type": "audio"}, chunk_size=4
    )

    assert resp["success"] is True
    sent = [
        (c.request.path_url, c.request.headers.get("Authorization"))
        for c in mocked.calls
    ]
    assert sent == [
        ("/api/v3/oauth/token", BASIC),
        ("/api/v3/upload/start", "Bearer tok-1"),
        ("/api/v3/upload", "Bearer tok-1"),
        ("/api/v3/oauth/token", BASIC),
        ("/api/v3/upload", "Bearer tok-2"),
        ("/api/v3/upload", "Bearer tok-2"),
        ("/api/v3/upload/finish", "Bearer tok-2"),
    ]


def test_upload_chunk_401_renews_the_token_and_resends_the_chunk(
    mocked, client, audio_file
):
    token_response(mocked, token="tok-1")
    token_response(mocked, token="tok-2")
    mocked.post(f"{API_URL}/upload/start", json={"id": "upload-1"})
    mocked.post(f"{API_URL}/upload", status=401, match=bearer("tok-1"))
    mocked.post(f"{API_URL}/upload", json={"success": True}, match=bearer("tok-2"))
    mocked.post(f"{API_URL}/upload/finish", json={"success": True})

    resp = client.upload_file(
        str(audio_file), {"id": "asset-1", "type": "audio"}, chunk_size=100
    )

    assert resp["success"] is True
    chunks = [c.request for c in mocked.calls if c.request.url.endswith("/upload")]
    assert [multipart_field(r.body, "file") for r in chunks] == [b"abcdefghij"] * 2
