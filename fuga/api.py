import hashlib
import json
import logging
import math
import os
import threading
import time
from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple, Protocol

import requests

from .response import FugaResponse, JSONBody, error_response

logger = logging.getLogger(__name__)

# Seconds to connect, then the longest wait for FUGA to send the next bytes of
# a reply. In 30 days of production logs no task containing FUGA calls ran
# longer than 181 s, so 300 s cuts off only a FUGA that has stopped answering.
DEFAULT_TIMEOUT = (10, 300)
Timeout = float | tuple[float, float]

# The v2 login sets this cookie, and every later request must send it.
SESSION_COOKIE = "connect.sid"

# A v3 token with less than this left is renewed before it is used, or halfway
# through its life if it is shorter. A video upload can run for 60 minutes,
# and the video uploader can't renew the token cm-backend hands it.
TOKEN_RENEWAL_MARGIN = timedelta(minutes=90)

# How long every client sharing a token store waits before asking FUGA for a
# token again after it rate-limits or refuses a token request: keeping the
# token it has if that is still valid, failing calls if not.
RENEWAL_RETRY = timedelta(minutes=5)

# Seconds to wait before each retry of a v3 request FUGA rate-limited with a
# 429. FUGA asks for exponential backoff and may ban an integration that keeps
# calling while it is limited.
RATE_LIMIT_BACKOFF = (1, 2, 4, 8, 16)


class FUGAAuthError(ValueError):
    """
    FUGA refused the login, or there is nothing to log in with. It subclasses
    ValueError, which login failures raised before, so existing handlers still
    catch it.
    """


class _TokenRateLimited(Exception):
    """FUGA's token endpoint is still answering 429, and no token is usable."""

    def __init__(self, response: requests.Response) -> None:
        super().__init__("Token request still rate-limited after retries")
        self.response = response


class _TokenPaused(requests.RequestException):
    """
    The last token request failed and no token is usable, so the client won't
    ask FUGA again yet. A RequestException so a call returns it like any
    request that didn't reach FUGA.
    """


class BaseFUGAClient(ABC):
    """
    The HTTP layer shared by every FUGA API version.

    Subclasses supply authentication through `_is_authenticated` and
    `authenticate`, which they must override, and `_can_reauthenticate` and
    `_reauthenticate`, which they may. A subclass missing either of the first
    two can't be constructed.

    A request authenticates first if it needs to, and on a 401 calls
    `_reauthenticate` and retries once when the subclass can. Then
    `_retry_delay` decides whether to wait and send it again; by default it
    never does. Every request, login and upload chunks included, uses
    `timeout`. Calls return a FugaResponse and never raise, with one
    exception: when a client has no usable login or token and FUGA refuses to
    give it one, it raises FUGAAuthError. A refused re-login after a 401
    returns the 401.
    """

    # "v2" or "v3", set by each subclass. v2-only methods refuse any client
    # that doesn't set "v2".
    api_version: str

    def __init__(self, api_url: str, timeout: Timeout = DEFAULT_TIMEOUT) -> None:
        self.api_url = api_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    # ---- authentication, provided by subclasses ----
    @abstractmethod
    def _is_authenticated(self) -> bool:
        ...

    @abstractmethod
    def authenticate(self) -> None:
        ...

    def _can_reauthenticate(self) -> bool:
        return False

    def _reauthenticate(self) -> None:
        """Authenticate again after FUGA answered 401 to the current login."""
        self.authenticate()

    def _retry_delay(self, resp: requests.Response, attempt: int) -> float | None:
        """
        Seconds to wait before sending a request again after `resp`, its reply
        to retry number `attempt` (0 for the first send), or None to return
        `resp` to the caller.
        """
        return None

    def _send(self, method: str, endpoint: str, **kwargs: Any) -> requests.Response:
        try:
            if not self._is_authenticated():
                self.authenticate()
        except _TokenRateLimited as e:
            return e.response
        url = f"{self.api_url}{endpoint}"
        reauthenticated = False
        attempt = 0
        while True:
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
            if (
                resp.status_code == 401
                and not reauthenticated
                and self._can_reauthenticate()
            ):
                reauthenticated = True
                try:
                    self._reauthenticate()
                except FUGAAuthError:
                    # The caller gets FUGA's 401 to act on, as before re-login existed
                    return resp
                except _TokenRateLimited as e:
                    return e.response
                continue
            delay = self._retry_delay(resp, attempt)
            if delay is None:
                return resp
            time.sleep(delay)
            attempt += 1

    # ---- verbs ----
    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> FugaResponse:
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, data: JSONBody | None = None) -> FugaResponse:
        return self._request("POST", endpoint, json=data)

    def put(self, endpoint: str, data: JSONBody | None = None) -> FugaResponse:
        return self._request("PUT", endpoint, json=data)

    def patch(self, endpoint: str, data: JSONBody | None = None) -> FugaResponse:
        return self._request("PATCH", endpoint, json=data)

    def delete(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> FugaResponse:
        return self._request("DELETE", endpoint, params=params)

    def delete_json(self, endpoint: str, data: JSONBody | None = None) -> FugaResponse:
        return self._request("DELETE", endpoint, json=data)

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> FugaResponse:
        try:
            resp = self._send(method, endpoint, **kwargs)
            # Try to parse JSON; fall back to text
            try:
                data = resp.json()
            except (ValueError, json.JSONDecodeError):
                data = resp.text

            if resp.ok:
                return {"success": True, "status_code": resp.status_code, "data": data}

            # ---- Normalize error shape ----
            error_payload: dict[str, Any]
            if isinstance(data, dict):
                # Common FUGA-style: {"error": {...}} or {"errors": [...]}
                if "error" in data:
                    err = data["error"]
                    if isinstance(err, dict):
                        error_payload = err
                    elif isinstance(err, list):
                        # join messages if present, skipping empty ones; also return raw list
                        msgs = [
                            str(e["message"])
                            for e in err
                            if isinstance(e, dict) and e.get("message")
                        ]
                        error_payload = {
                            "message": "; ".join(msgs) or "Request failed",
                            "details": err,
                        }
                    elif (
                        isinstance(err, str)
                        and isinstance(data.get("message"), str)
                        and data["message"]
                    ):
                        # e.g. royalty splits: {"error": "<code>", "message": "...", "details": {...}}
                        error_payload = {"code": str(err), "message": data["message"]}
                        if "details" in data:
                            error_payload["details"] = data["details"]
                    else:
                        error_payload = {"message": str(err)}
                elif "errors" in data and isinstance(data["errors"], list):
                    msgs = []
                    for e in data["errors"]:
                        if isinstance(e, dict):
                            m = (
                                e.get("message")
                                or e.get("detail")
                                or e.get("title")
                                or ""
                            )
                            if not m:
                                # last resort: serialize the dict so you see *something*
                                try:
                                    m = json.dumps(e, ensure_ascii=False)
                                except (TypeError, ValueError):
                                    m = str(e)
                            msgs.append(str(m))
                        else:
                            msgs.append(str(e))
                    error_payload = {
                        "message": "; ".join([m for m in msgs if m])
                        or "Request failed",
                        "details": data["errors"],
                    }
                else:
                    # Unknown schema: surface as-is so callers can inspect
                    error_payload = data
            else:
                # Non-JSON or non-dict body
                error_payload = {"message": str(data)}

            return {
                "success": False,
                "status_code": resp.status_code,
                "error": error_payload,
            }

        except requests.RequestException as e:
            return error_response(str(e))

    def get_binary(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> FugaResponse:
        try:
            resp = self._send("GET", endpoint, params=params)
            ctype = resp.headers.get("Content-Type", "")
            if resp.ok:
                return {
                    "success": True,
                    "status_code": resp.status_code,
                    "data": resp.content,  # BYTES
                    "headers": {"Content-Type": ctype},
                }
            else:
                # error bodies might be text/json; return as text for readability
                return {
                    "success": False,
                    "status_code": resp.status_code,
                    "error": {"message": resp.text},
                    "headers": {"Content-Type": ctype},
                }
        except requests.RequestException as e:
            return error_response(str(e))

    def upload_file(
        self, file_path: str, data: dict[str, Any], chunk_size: int = 5 * 1024 * 1024
    ) -> FugaResponse:
        """
        Chunked upload to FUGA: /upload/start -> /upload (multipart chunks) -> /upload/finish
        `data` is the JSON you send to /upload/start, e.g. {"id": <asset_id>, "type": "audio", ...}
        """
        # Check the file first, so a bad path doesn't leave an upload session open
        file_name = os.path.basename(file_path)
        try:
            total_size = os.stat(file_path).st_size
        except OSError as e:
            return error_response(str(e))

        # 1) start session
        start = self.post("/upload/start", data=data)
        if not start["success"]:
            return start

        session = start.get("data") or {}
        upload_id = session.get("id")
        if not upload_id:
            return error_response("Missing upload_id", start["status_code"])

        total_parts = math.ceil(total_size / chunk_size)
        md5 = hashlib.md5()

        # 2) upload chunks
        with open(file_path, "rb") as f:
            part_index = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                offset = part_index * chunk_size
                md5.update(chunk)

                files = {
                    "uuid": (None, upload_id),
                    "filename": (None, file_name),
                    "totalfilesize": (None, str(total_size)),
                    "partindex": (None, str(part_index)),
                    "partbyteoffset": (None, str(offset)),
                    "totalparts": (None, str(total_parts)),
                    "file": ("blob", chunk, "application/octet-stream"),
                }
                headers = {
                    "Content-Range": f"bytes {offset}-{offset + len(chunk) - 1}/{total_size}"
                }

                part = self._request("POST", "/upload", headers=headers, files=files)
                if not part["success"]:
                    return part

                part_index += 1

        md5sum = md5.hexdigest()

        # 3) finish
        finish = self.post(
            "/upload/finish",
            data={"uuid": upload_id, "filename": file_name, "md5sum": md5sum},
        )
        if finish["success"]:
            payload = finish.get("data")
            # If API just returns True or {"success": True}, replace with something useful
            if payload is True or (
                isinstance(payload, dict)
                and set(payload.keys()) == {"success"}
                and payload["success"] is True
            ):
                finish["data"] = {
                    "completed": True,
                    "upload_id": upload_id,
                    "filename": file_name,
                    "md5sum": md5sum,
                }
        return finish


class FUGAClient(BaseFUGAClient):
    """
    FUGA API v2. Logs in with a username and password and sends the session
    cookie, or uses a cookie it is given. Logs in on the first request that
    needs it, or when `login()` is called. Given a cookie and credentials, it
    starts with the cookie and logs in again if FUGA rejects it.
    """

    api_version = "v2"

    def __init__(
        self,
        api_url: str,
        username: str | None = None,
        password: str | None = None,
        auth_cookie: str | None = None,
        timeout: Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        super().__init__(api_url, timeout)
        self.auth_cookie = auth_cookie
        self.credentials: dict[str, str] | None = None

        if username and password:
            self.credentials = {"name": username, "password": password}

        if self.auth_cookie:
            self.session.headers["Cookie"] = self.auth_cookie
        elif self.credentials is None:
            raise ValueError("Either auth_cookie or username/password must be provided")

    def login(self) -> None:
        if self.credentials is None:
            raise FUGAAuthError("No username and password to log in with")

        resp = self.session.post(
            f"{self.api_url}/login", json=self.credentials, timeout=self.timeout
        )
        if resp.status_code != 200:
            raise FUGAAuthError(f"Login failed: {resp.status_code} {resp.text}")

        # The reply may set other cookies too, such as a load balancer's
        session_id = resp.cookies.get(SESSION_COOKIE)
        if not session_id:
            raise FUGAAuthError("Login succeeded but FUGA set no session cookie")

        cookie = f"{SESSION_COOKIE}={session_id}"
        self.auth_cookie = cookie
        self.session.headers["Cookie"] = cookie

    def _is_authenticated(self) -> bool:
        return bool(self.auth_cookie)

    def authenticate(self) -> None:
        self.login()

    def _can_reauthenticate(self) -> bool:
        return self.credentials is not None


class Token(NamedTuple):
    """A v3 access token, when it expires, and when to start renewing it."""

    access_token: str
    expires_at: datetime
    renew_after: datetime


class TokenStore(Protocol):
    """
    Where a v3 client keeps its access token, supplied by the caller so that
    processes sharing a credential share its token and its renewal time.
    `load` returns the token, its expiry and when to renew it, all
    timezone-aware, or None if there is no token yet. An empty token is a
    pause the client saved after a failed token request: `renew_after` says
    when to ask again. `lock` must stop other clients renewing the same token
    while it is held. The client calls `load`
    outside the lock too, and `save` only inside it.
    """

    def lock(self) -> AbstractContextManager[Any]:
        ...

    def load(self) -> tuple[str, datetime, datetime] | None:
        ...

    def save(
        self, access_token: str, expires_at: datetime, renew_after: datetime
    ) -> None:
        ...


class MemoryTokenStore:
    """A token store for one process, such as a script or a test."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token: Token | None = None

    def lock(self) -> AbstractContextManager[Any]:
        return self._lock

    def load(self) -> tuple[str, datetime, datetime] | None:
        return self._token

    def save(
        self, access_token: str, expires_at: datetime, renew_after: datetime
    ) -> None:
        self._token = Token(access_token, expires_at, renew_after)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FUGAV3Client(BaseFUGAClient):
    """
    FUGA API v3. Exchanges a client id and secret for a Bearer token at
    `POST /oauth/token` and keeps it in the token store it is given. Gets a
    token on the first request that needs one, and renews it once its
    `renew_after` has passed: TOKEN_RENEWAL_MARGIN before it expires, or
    halfway through its life if that is sooner. After a 401 it renews the
    token FUGA rejected, unless another client already has. Every request is
    checked, upload chunks included, and any request FUGA rate-limits is
    retried after RATE_LIMIT_BACKOFF.

    If FUGA rate-limits or refuses a renewal while the stored token is still
    valid, every client keeps that token for RENEWAL_RETRY before asking
    again. With no valid token, a refusal raises FUGAAuthError, and a token
    endpoint still rate-limiting after the backoff makes the call return its
    429. Either way no client asks again for RENEWAL_RETRY: calls until then
    return an error without reaching FUGA.
    """

    api_version = "v3"

    def __init__(
        self,
        api_url: str,
        client_id: str,
        client_secret: str,
        token_store: TokenStore,
        timeout: Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        super().__init__(api_url, timeout)
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_store = token_store
        self.token: Token | None = None

    def _is_authenticated(self) -> bool:
        return self.token is not None and _now() < self.token.renew_after

    def _can_reauthenticate(self) -> bool:
        return True

    def authenticate(self) -> None:
        self._renew(rejected=None)

    def _reauthenticate(self) -> None:
        self._renew(rejected=self.token.access_token if self.token else None)

    def ensure_token(self, min_valid: timedelta = timedelta(0)) -> tuple[str, datetime]:
        """
        The token and its expiry, renewed first if it is due. Raises
        FUGAAuthError if there is no valid token and FUGA won't give one, or
        if the token has less than `min_valid` left, which can happen after
        FUGA refuses renewals. A caller handing the token to a process that
        can't renew it passes that process's longest run.
        """
        if not self._is_authenticated():
            try:
                self.authenticate()
            except (_TokenRateLimited, _TokenPaused) as e:
                raise FUGAAuthError(str(e)) from None
        assert self.token is not None
        if self.token.expires_at - _now() < min_valid:
            raise FUGAAuthError(
                f"The FUGA token expires at {self.token.expires_at.isoformat()}, "
                f"less than {min_valid} from now"
            )
        return self.token.access_token, self.token.expires_at

    def _renew(self, rejected: str | None) -> None:
        """Use a stored token that isn't due, or get a new one from FUGA."""
        stored = self.token_store.load()
        if self._use_stored_token(stored, rejected):
            return
        self._check_not_paused(stored)
        failure: FUGAAuthError | _TokenRateLimited | None = None
        with self.token_store.lock():
            # Another client may have renewed the token, or failed to, while
            # this one waited
            stored = self.token_store.load()
            if self._use_stored_token(stored, rejected):
                return
            self._check_not_paused(stored)
            # A token FUGA hasn't rejected stands in if the renewal fails
            current = Token(*stored) if stored else None
            if current and (
                current.access_token == rejected or current.expires_at <= _now()
            ):
                current = None
            try:
                token = self._request_token(current)
            except (FUGAAuthError, _TokenRateLimited) as e:
                # No token to keep: an empty one whose renew_after tells every
                # client sharing the store not to ask before then. The error
                # is raised once the lock is released, so a store that rolls
                # back on an error, such as a database transaction, keeps it.
                now = _now()
                self.token_store.save("", now, now + RENEWAL_RETRY)
                failure = e
            else:
                self.token_store.save(*token)
                self._use_token(token)
        if failure is not None:
            raise failure

    def _use_stored_token(
        self, stored: tuple[str, datetime, datetime] | None, rejected: str | None
    ) -> bool:
        if stored is None:
            return False
        token = Token(*stored)
        if (
            not token.access_token
            or token.access_token == rejected
            or _now() >= token.renew_after
        ):
            return False
        self._use_token(token)
        return True

    @staticmethod
    def _check_not_paused(stored: tuple[str, datetime, datetime] | None) -> None:
        if stored is None:
            return
        token = Token(*stored)
        if not token.access_token and _now() < token.renew_after:
            raise _TokenPaused(
                "The last FUGA token request failed; not asking again until "
                + token.renew_after.isoformat()
            )

    def _use_token(self, token: Token) -> None:
        self.token = token
        self.session.headers["Authorization"] = f"Bearer {token.access_token}"

    def _request_token(self, current: Token | None) -> Token:
        """
        A new token from FUGA. If FUGA rate-limits or refuses the request,
        returns `current` with its renewal put off by RENEWAL_RETRY. With no
        `current`, backs off on a 429 and raises _TokenRateLimited after the
        last wait, and raises FUGAAuthError on a refusal.
        """
        attempt = 0
        while True:
            resp = self.session.post(
                f"{self.api_url}/oauth/token",
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
                timeout=self.timeout,
            )
            if resp.status_code != 429:
                break
            if current:
                logger.warning(
                    "FUGA rate-limited a token renewal; keeping the current token"
                )
                return self._put_off(current)
            delay = self._retry_delay(resp, attempt)
            if delay is None:
                raise _TokenRateLimited(resp)
            logger.warning("FUGA rate-limited a token request; retrying in %s s", delay)
            time.sleep(delay)
            attempt += 1

        try:
            body = resp.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            body = {}
        access_token = body.get("access_token")
        expires_in = body.get("expires_in")

        if resp.status_code != 200:
            parts = [str(resp.status_code), body.get("code"), body.get("message")]
            if not body:
                parts.append(resp.text)
            detail = " ".join(str(p) for p in parts if p)
            problem = f"Token request failed: {detail}"
        elif (
            not access_token
            or not isinstance(expires_in, (int, float))
            or isinstance(expires_in, bool)
            or expires_in <= 0
        ):
            problem = "Token response has no access_token or expires_in"
        else:
            now = _now()
            lifetime = timedelta(seconds=expires_in)
            expires_at = now + lifetime
            renew_after = expires_at - min(TOKEN_RENEWAL_MARGIN, lifetime / 2)
            logger.info("Got a FUGA token; it expires at %s", expires_at.isoformat())
            return Token(access_token, expires_at, renew_after)

        if current:
            logger.error(
                "%s; keeping the current token, which expires at %s",
                problem,
                current.expires_at.isoformat(),
            )
            return self._put_off(current)
        raise FUGAAuthError(problem)

    @staticmethod
    def _put_off(token: Token) -> Token:
        return token._replace(renew_after=min(_now() + RENEWAL_RETRY, token.expires_at))

    def _retry_delay(self, resp: requests.Response, attempt: int) -> float | None:
        if resp.status_code != 429 or attempt >= len(RATE_LIMIT_BACKOFF):
            return None
        # FUGA doesn't document Retry-After; if it sends one in seconds, use it
        retry_after = resp.headers.get("Retry-After", "")
        return (
            int(retry_after) if retry_after.isdigit() else RATE_LIMIT_BACKOFF[attempt]
        )
