import hashlib

import pytest
import requests
from responses import matchers

from fuga.api import DEFAULT_TIMEOUT, FUGAAuthError, FUGAClient

from .conftest import API_URL, COOKIE


def login_response(mocked, status=200, cookie="connect.sid=fresh"):
    name, value = cookie.split("=", 1)
    return mocked.post(
        f"{API_URL}/login",
        json={"user": {"id": 7}},
        status=status,
        headers={"Set-Cookie": f"{name}={value}; Path=/"},
    )


# ---- construction and login ----


def test_cookie_client_sends_cookie_without_logging_in(mocked, client):
    mocked.get(
        f"{API_URL}/labels",
        json={"label": []},
        match=[matchers.header_matcher({"Cookie": COOKIE})],
    )

    assert client.get("/labels")["success"] is True
    assert client.auth_cookie == COOKIE


def test_client_needs_a_cookie_or_credentials():
    with pytest.raises(ValueError):
        FUGAClient(API_URL)


def test_constructor_does_not_log_in(mocked):
    FUGAClient(API_URL, username="user", password="secret")

    assert len(mocked.calls) == 0


def test_login_posts_credentials_and_stores_cookie(mocked):
    login = login_response(mocked)

    client = FUGAClient(API_URL, username="user", password="secret")
    client.login()

    assert login.call_count == 1
    assert mocked.calls[0].request.body == b'{"name": "user", "password": "secret"}'
    assert client.auth_cookie == "connect.sid=fresh"
    assert client.session.headers["Cookie"] == "connect.sid=fresh"


def test_first_request_logs_in_once(mocked):
    login = login_response(mocked)
    labels = mocked.get(
        f"{API_URL}/labels",
        json={"label": []},
        match=[matchers.header_matcher({"Cookie": "connect.sid=fresh"})],
    )

    client = FUGAClient(API_URL, username="user", password="secret")
    client.get("/labels")
    client.get("/labels")

    assert login.call_count == 1
    assert labels.call_count == 2


def test_failed_login_raises_auth_error(mocked):
    mocked.post(f"{API_URL}/login", json={"code": "AUTH"}, status=401)

    client = FUGAClient(API_URL, username="user", password="wrong")
    with pytest.raises(FUGAAuthError, match="Login failed: 401"):
        client.login()


def test_failed_login_on_first_request_raises_auth_error(mocked):
    mocked.post(f"{API_URL}/login", json={"code": "AUTH"}, status=401)

    client = FUGAClient(API_URL, username="user", password="wrong")
    with pytest.raises(FUGAAuthError):
        client.get("/labels")


def test_auth_error_is_still_a_value_error():
    assert issubclass(FUGAAuthError, ValueError)


def test_cookie_client_cannot_log_in(client):
    with pytest.raises(FUGAAuthError, match="No username and password"):
        client.login()


def test_401_logs_in_again_and_retries(mocked):
    login = login_response(mocked)
    mocked.get(f"{API_URL}/labels", json={"label": [1]})

    client = FUGAClient(API_URL, username="user", password="secret")
    client.login()
    mocked.replace(
        "GET", f"{API_URL}/labels", json={"code": "NOT_LOGGED_IN"}, status=401
    )
    mocked.add("GET", f"{API_URL}/labels", json={"label": [1]})

    resp = client.get("/labels")

    assert resp == {"success": True, "status_code": 200, "data": {"label": [1]}}
    assert login.call_count == 2


def test_cookie_client_returns_a_401_without_logging_in(mocked, client):
    mocked.get(f"{API_URL}/labels", json={"code": "NOT_LOGGED_IN"}, status=401)

    resp = client.get("/labels")

    assert resp["status_code"] == 401
    assert len(mocked.calls) == 1


def test_cookie_client_with_credentials_logs_in_again_on_a_401(mocked):
    login = login_response(mocked)
    stale = mocked.get(
        f"{API_URL}/labels",
        json={"code": "NOT_LOGGED_IN"},
        status=401,
        match=[matchers.header_matcher({"Cookie": COOKIE})],
    )
    fresh = mocked.get(
        f"{API_URL}/labels",
        json={"label": [1]},
        match=[matchers.header_matcher({"Cookie": "connect.sid=fresh"})],
    )

    client = FUGAClient(API_URL, username="user", password="secret", auth_cookie=COOKIE)
    resp = client.get("/labels")

    assert resp == {"success": True, "status_code": 200, "data": {"label": [1]}}
    assert (stale.call_count, login.call_count, fresh.call_count) == (1, 1, 1)
    assert client.auth_cookie == "connect.sid=fresh"


def test_trailing_slash_is_stripped_from_api_url(mocked):
    client = FUGAClient(API_URL + "/", auth_cookie=COOKIE)
    mocked.get(f"{API_URL}/labels", json={})

    assert client.get("/labels")["success"] is True


# ---- verbs ----


def test_get_sends_query_params(mocked, client):
    mocked.get(
        f"{API_URL}/labels",
        json={"label": []},
        match=[matchers.query_param_matcher({"page": "0", "page_size": "1"})],
    )

    assert client.get("/labels", params={"page": 0, "page_size": 1}) == {
        "success": True,
        "status_code": 200,
        "data": {"label": []},
    }


@pytest.mark.parametrize("verb", ["post", "put", "patch"])
def test_body_verbs_send_json(mocked, client, verb):
    mocked.add(
        verb.upper(),
        f"{API_URL}/labels/1",
        json={"id": 1},
        match=[matchers.json_params_matcher({"name": "Label"})],
    )

    resp = getattr(client, verb)("/labels/1", data={"name": "Label"})

    assert resp == {"success": True, "status_code": 200, "data": {"id": 1}}


def test_put_sends_a_list_body(mocked, client):
    mocked.put(
        f"{API_URL}/products/1/territories",
        json={},
        match=[matchers.json_params_matcher(["GB", "US"])],
    )

    assert client.put("/products/1/territories", data=["GB", "US"])["success"]


def test_delete_sends_query_params(mocked, client):
    mocked.delete(
        f"{API_URL}/labels/1",
        status=204,
        match=[matchers.query_param_matcher({"force": "true"})],
    )

    resp = client.delete("/labels/1", params={"force": "true"})

    assert resp == {"success": True, "status_code": 204, "data": ""}


def test_delete_json_sends_a_body(mocked, client):
    mocked.delete(
        f"{API_URL}/release_projects/1/products",
        json={},
        match=[matchers.json_params_matcher({"products_ids": ["2"]})],
    )

    resp = client.delete_json(
        "/release_projects/1/products", data={"products_ids": ["2"]}
    )

    assert resp["success"] is True


def test_non_json_success_body_is_returned_as_text(mocked, client):
    mocked.get(f"{API_URL}/labels", body="plain text")

    assert client.get("/labels") == {
        "success": True,
        "status_code": 200,
        "data": "plain text",
    }


# ---- error shapes ----


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        pytest.param(
            {"code": "LABEL_NOT_FOUND", "message": "Label not found"},
            {"code": "LABEL_NOT_FOUND", "message": "Label not found"},
            id="fuga-code-and-message-passes-through",
        ),
        pytest.param(
            {"error": {"code": "X", "message": "Bad"}},
            {"code": "X", "message": "Bad"},
            id="error-object-is-unwrapped",
        ),
        pytest.param(
            {"error": [{"message": "One"}, {"message": "Two"}, {"other": 1}]},
            {
                "message": "One; Two",
                "details": [{"message": "One"}, {"message": "Two"}, {"other": 1}],
            },
            id="error-list-messages-are-joined",
        ),
        pytest.param(
            {"error": []},
            {"message": "Request failed", "details": []},
            id="empty-error-list",
        ),
        pytest.param(
            {"error": "Bad thing"},
            {"message": "Bad thing"},
            id="error-string",
        ),
        pytest.param(
            {"errors": [{"message": "A"}, {"detail": "B"}, {"title": "C"}, "D"]},
            {
                "message": "A; B; C; D",
                "details": [{"message": "A"}, {"detail": "B"}, {"title": "C"}, "D"],
            },
            id="errors-list-uses-message-detail-or-title",
        ),
        pytest.param(
            {"errors": [{"field": "name"}]},
            {"message": '{"field": "name"}', "details": [{"field": "name"}]},
            id="errors-entry-without-message-is-serialised",
        ),
        pytest.param(
            {
                "error": [
                    {"message": None},
                    {"message": ""},
                    {"message": "Two"},
                    {"message": 3},
                ]
            },
            {
                "message": "Two; 3",
                "details": [
                    {"message": None},
                    {"message": ""},
                    {"message": "Two"},
                    {"message": 3},
                ],
            },
            id="error-list-skips-empty-messages",
        ),
        pytest.param(
            {"error": [{"message": None}]},
            {"message": "Request failed", "details": [{"message": None}]},
            id="error-list-with-only-a-null-message",
        ),
        pytest.param(
            {
                "error": "SPLITS_INVALID",
                "message": "Shares must add up to 100",
                "details": {"shares": 90},
            },
            {
                "code": "SPLITS_INVALID",
                "message": "Shares must add up to 100",
                "details": {"shares": 90},
            },
            id="error-string-keeps-fuga-message",
        ),
        pytest.param(
            {"error": "SPLITS_INVALID", "message": "Shares must add up to 100"},
            {"code": "SPLITS_INVALID", "message": "Shares must add up to 100"},
            id="error-string-with-message-and-no-details",
        ),
    ],
)
def test_error_bodies_are_normalised(mocked, client, body, expected):
    mocked.get(f"{API_URL}/labels/1", json=body, status=400)

    assert client.get("/labels/1") == {
        "success": False,
        "status_code": 400,
        "error": expected,
    }


def test_non_json_error_body_becomes_a_message(mocked, client):
    mocked.get(f"{API_URL}/labels/1", body="Gateway Timeout", status=504)

    assert client.get("/labels/1") == {
        "success": False,
        "status_code": 504,
        "error": {"message": "Gateway Timeout"},
    }


def test_network_error_is_returned_not_raised(mocked, client):
    mocked.get(f"{API_URL}/labels", body=requests.ConnectionError("refused"))

    assert client.get("/labels") == {
        "success": False,
        "status_code": None,
        "error": {"message": "refused"},
    }


# ---- binary ----


def test_get_binary_returns_bytes_and_content_type(mocked, client):
    mocked.get(
        f"{API_URL}/assets/1/audio",
        body=b"\x00\x01",
        content_type="audio/wav",
        match=[matchers.query_param_matcher({"original": "True"})],
    )

    assert client.get_binary("/assets/1/audio", params={"original": True}) == {
        "success": True,
        "status_code": 200,
        "data": b"\x00\x01",
        "headers": {"Content-Type": "audio/wav"},
    }


def test_get_binary_error_returns_text(mocked, client):
    mocked.get(
        f"{API_URL}/assets/1/audio",
        body="missing",
        status=404,
        content_type="text/plain",
    )

    assert client.get_binary("/assets/1/audio") == {
        "success": False,
        "status_code": 404,
        "error": {"message": "missing"},
        "headers": {"Content-Type": "text/plain"},
    }


# ---- chunked upload ----


@pytest.fixture
def audio_file(tmp_path):
    path = tmp_path / "track.wav"
    path.write_bytes(b"abcdefghij")  # 10 bytes: chunks of 4, 4, 2
    return path


def register_upload(mocked, *, finish_json: object = True, chunk_status=200):
    start = mocked.post(
        f"{API_URL}/upload/start",
        json={"id": "upload-1"},
        match=[matchers.json_params_matcher({"id": "asset-1", "type": "audio"})],
    )
    chunk = mocked.post(f"{API_URL}/upload", body="ok", status=chunk_status)
    finish = mocked.post(f"{API_URL}/upload/finish", json=finish_json)
    return start, chunk, finish


def test_upload_sends_start_chunks_and_finish(mocked, client, audio_file):
    start, chunk, finish = register_upload(mocked)

    resp = client.upload_file(
        str(audio_file), {"id": "asset-1", "type": "audio"}, chunk_size=4
    )

    assert start.call_count == 1
    assert chunk.call_count == 3
    chunk_requests = [
        c.request for c in mocked.calls if c.request.url.endswith("/upload")
    ]
    assert [r.headers["Content-Range"] for r in chunk_requests] == [
        "bytes 0-3/10",
        "bytes 4-7/10",
        "bytes 8-9/10",
    ]
    for index, request in enumerate(chunk_requests):
        body = request.body
        assert b'name="uuid"\r\n\r\nupload-1' in body
        assert b'name="filename"\r\n\r\ntrack.wav' in body
        assert b'name="totalfilesize"\r\n\r\n10' in body
        assert f'name="partindex"\r\n\r\n{index}'.encode() in body
        assert b'name="totalparts"\r\n\r\n3' in body
        assert b'name="file"; filename="blob"' in body

    md5 = hashlib.md5(b"abcdefghij").hexdigest()
    assert finish.call_count == 1
    assert mocked.calls[-1].request.body == (
        f'{{"uuid": "upload-1", "filename": "track.wav", "md5sum": "{md5}"}}'.encode()
    )
    assert resp == {
        "success": True,
        "status_code": 200,
        "data": {
            "completed": True,
            "upload_id": "upload-1",
            "filename": "track.wav",
            "md5sum": md5,
        },
    }


def test_upload_keeps_a_useful_finish_payload(mocked, client, audio_file):
    register_upload(mocked, finish_json={"id": "file-9"})

    resp = client.upload_file(
        str(audio_file), {"id": "asset-1", "type": "audio"}, chunk_size=4
    )

    assert resp["data"] == {"id": "file-9"}


def test_upload_replaces_a_bare_success_finish_payload(mocked, client, audio_file):
    register_upload(mocked, finish_json={"success": True})

    resp = client.upload_file(
        str(audio_file), {"id": "asset-1", "type": "audio"}, chunk_size=4
    )

    assert resp["data"]["completed"] is True


def test_upload_finish_rejection_returns_fugas_code_and_message(
    mocked, client, audio_file
):
    """The shape FUGA's spec gives for /upload/finish errors (UploadErrorResponse)."""
    mocked.post(f"{API_URL}/upload/start", json={"id": "upload-1"})
    mocked.post(f"{API_URL}/upload", body="ok")
    mocked.post(
        f"{API_URL}/upload/finish",
        status=400,
        json={
            "success": False,
            "error": {
                "code": "AUDIO_QUALITY_TOO_LOW",
                "message": "The audio quality is below the minimum required",
            },
        },
    )

    resp = client.upload_file(
        str(audio_file), {"id": "asset-1", "type": "audio"}, chunk_size=100
    )

    assert resp == {
        "success": False,
        "status_code": 400,
        "error": {
            "code": "AUDIO_QUALITY_TOO_LOW",
            "message": "The audio quality is below the minimum required",
        },
    }


def test_upload_returns_a_failed_start(mocked, client, audio_file):
    mocked.post(f"{API_URL}/upload/start", json={"code": "NOPE"}, status=400)

    resp = client.upload_file(str(audio_file), {"id": "asset-1", "type": "audio"})

    assert resp == {"success": False, "status_code": 400, "error": {"code": "NOPE"}}


def test_upload_without_an_upload_id_fails(mocked, client, audio_file):
    mocked.post(f"{API_URL}/upload/start", json={})

    resp = client.upload_file(str(audio_file), {"id": "asset-1", "type": "audio"})

    assert resp == {
        "success": False,
        "status_code": 200,
        "error": {"message": "Missing upload_id"},
    }


def test_upload_of_a_missing_file_fails(mocked, client, tmp_path):
    mocked.post(f"{API_URL}/upload/start", json={"id": "upload-1"})

    resp = client.upload_file(str(tmp_path / "nope.wav"), {"id": "a", "type": "audio"})

    assert resp["success"] is False
    assert resp["status_code"] is None
    assert "nope.wav" in resp["error"]["message"]


def test_upload_stops_at_a_failed_chunk(mocked, client, audio_file):
    mocked.post(f"{API_URL}/upload/start", json={"id": "upload-1"})
    chunk = mocked.post(f"{API_URL}/upload", body="chunk rejected", status=500)

    resp = client.upload_file(
        str(audio_file), {"id": "asset-1", "type": "audio"}, chunk_size=4
    )

    assert chunk.call_count == 1
    assert resp == {
        "success": False,
        "status_code": 500,
        "error": {"message": "chunk rejected"},
    }


def test_upload_chunk_network_error_is_returned(mocked, client, audio_file):
    mocked.post(f"{API_URL}/upload/start", json={"id": "upload-1"})
    mocked.post(f"{API_URL}/upload", body=requests.ConnectionError("reset"))

    resp = client.upload_file(
        str(audio_file), {"id": "asset-1", "type": "audio"}, chunk_size=4
    )

    assert resp == {
        "success": False,
        "status_code": None,
        "error": {"message": "reset"},
    }


# ---- timeouts ----


def test_every_request_uses_the_default_timeout(mocked, audio_file):
    login_response(mocked)
    mocked.get(f"{API_URL}/labels", json={})
    mocked.get(f"{API_URL}/assets/1/audio", body=b"RIFF")
    register_upload(mocked)

    client = FUGAClient(API_URL, username="user", password="secret")
    client.get("/labels")
    client.get_binary("/assets/1/audio")
    client.upload_file(
        str(audio_file), {"id": "asset-1", "type": "audio"}, chunk_size=4
    )

    paths = [c.request.path_url for c in mocked.calls]
    assert paths[0] == "/api/v2/login"
    assert "/api/v2/upload" in paths
    assert {c.request.req_kwargs["timeout"] for c in mocked.calls} == {DEFAULT_TIMEOUT}
    assert DEFAULT_TIMEOUT == (10, 300)


def test_timeout_can_be_set_on_the_client(mocked):
    mocked.get(f"{API_URL}/labels", json={})

    client = FUGAClient(API_URL, auth_cookie=COOKIE, timeout=(5, 60))
    client.get("/labels")

    assert mocked.calls[0].request.req_kwargs["timeout"] == (5, 60)


def test_a_timed_out_call_is_returned_not_raised(mocked, client):
    mocked.get(f"{API_URL}/labels", body=requests.ReadTimeout("read timed out"))

    assert client.get("/labels") == {
        "success": False,
        "status_code": None,
        "error": {"message": "read timed out"},
    }


def test_a_timed_out_upload_chunk_is_returned(mocked, client, audio_file):
    mocked.post(f"{API_URL}/upload/start", json={"id": "upload-1"})
    mocked.post(f"{API_URL}/upload", body=requests.ReadTimeout("read timed out"))

    resp = client.upload_file(
        str(audio_file), {"id": "asset-1", "type": "audio"}, chunk_size=4
    )

    assert resp == {
        "success": False,
        "status_code": None,
        "error": {"message": "read timed out"},
    }
