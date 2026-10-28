import hashlib
import json
import math
import os
from abc import ABC, abstractmethod
from typing import Any

import requests

from .response import FugaResponse, JSONBody, error_response

# Seconds to connect, then the longest wait for FUGA to send the next bytes of
# a reply. In 30 days of production logs no task containing FUGA calls ran
# longer than 181 s, so 300 s cuts off only a FUGA that has stopped answering.
DEFAULT_TIMEOUT = (10, 300)
Timeout = float | tuple[float, float]

# The v2 login sets this cookie, and every later request must send it.
SESSION_COOKIE = "connect.sid"


class FUGAAuthError(ValueError):
    """
    FUGA refused the login, or there is nothing to log in with. It subclasses
    ValueError, which login failures raised before, so existing handlers still
    catch it.
    """


class BaseFUGAClient(ABC):
    """
    The HTTP layer shared by every FUGA API version.

    Subclasses supply authentication through `_is_authenticated` and
    `authenticate`, which they must override, and `_can_reauthenticate`, which
    they may. A subclass missing either of the first two can't be constructed.

    A request authenticates first if it needs to, and on a 401 authenticates
    once more and retries when the subclass can. Every request, login and
    upload chunks included, uses `timeout`. Calls return a FugaResponse and
    never raise, with one exception: if the login that `login()` or a client's
    first request makes is refused, it raises FUGAAuthError. A refused re-login
    after a 401 returns the 401.
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

    def _send(self, method: str, endpoint: str, **kwargs: Any) -> requests.Response:
        if not self._is_authenticated():
            self.authenticate()
        url = f"{self.api_url}{endpoint}"
        resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
        if resp.status_code == 401 and self._can_reauthenticate():
            try:
                self.authenticate()
            except FUGAAuthError:
                # The caller gets FUGA's 401 to act on, as before re-login existed
                return resp
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
        return resp

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

                try:
                    resp = self.session.post(
                        f"{self.api_url}/upload",
                        headers=headers,
                        files=files,
                        timeout=self.timeout,
                    )
                except requests.RequestException as e:
                    return error_response(str(e))

                if not resp.ok:
                    return error_response(resp.text, resp.status_code)

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
