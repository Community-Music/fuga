import json
import requests
from typing import Optional, Dict, Any


class FUGAClient:
    def __init__(
        self,
        api_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_cookie: Optional[str] = None,
    ):
        self.api_url = api_url.rstrip("/")
        self.auth_cookie = auth_cookie
        self.session = requests.Session()

        if self.auth_cookie:
            self.session.headers.update({"Cookie": self.auth_cookie})

        if not self.auth_cookie:
            if not (username and password):
                raise ValueError(
                    "Either auth_cookie or username/password must be provided"
                )
            self.credentials = {"name": username, "password": password}
            self.login()

    def login(self) -> None:
        resp = self.session.post(f"{self.api_url}/login", json=self.credentials)
        if resp.status_code != 200:
            raise ValueError(f"Login failed: {resp.status_code} {resp.text}")

        data = resp.json()
        self.user_id = data.get("user", {}).get("id")
        for c in resp.cookies:
            self.auth_cookie = f"{c.name}={c.value}"
            self.session.headers["Cookie"] = self.auth_cookie

    def get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return self._request("GET", endpoint, params=params)

    def post(
        self, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return self._request("POST", endpoint, json=data)

    def put(
        self, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return self._request("PUT", endpoint, json=data)

    def patch(
        self, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return self._request("PATCH", endpoint, json=data)

    def delete(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return self._request("DELETE", endpoint, params=params)

    def delete_json(
        self, endpoint: str, data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return self._request("DELETE", endpoint, json=data)

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        try:
            resp = self.session.request(method, f"{self.api_url}{endpoint}", **kwargs)
            # Try to parse JSON; fall back to text
            try:
                data = resp.json()
            except (ValueError, json.JSONDecodeError):
                data = resp.text

            if resp.ok:
                return {"success": True, "status_code": resp.status_code, "data": data}

            # ---- Normalize error shape ----
            error_payload: Dict[str, Any]
            if isinstance(data, dict):
                # Common FUGA-style: {"error": {...}} or {"errors": [...]}
                if "error" in data:
                    err = data["error"]
                    if isinstance(err, dict):
                        error_payload = err
                    elif isinstance(err, list):
                        # join messages if present; also return raw list
                        msgs = [
                            e.get("message")
                            for e in err
                            if isinstance(e, dict) and "message" in e
                        ]
                        error_payload = {
                            "message": "; ".join(msgs) or "Request failed",
                            "details": err,
                        }
                    else:
                        error_payload = {"message": str(err)}
                elif "errors" in data and isinstance(data["errors"], list):
                    msgs = [
                        e.get("message") if isinstance(e, dict) else str(e)
                        for e in data["errors"]
                    ]
                    error_payload = {
                        "message": "; ".join(msgs) or "Request failed",
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
            return {"success": False, "status_code": None, "error": {"message": str(e)}}

    def get_binary(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        try:
            resp = self.session.get(f"{self.api_url}{endpoint}", params=params)
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
            return {"success": False, "status_code": None, "error": {"message": str(e)}}

    def upload_file(
        self, file_path: str, data: Dict[str, Any], chunk_size: int = 5 * 1024 * 1024
    ) -> Dict[str, Any]:
        """
        Chunked upload to FUGA: /upload/start -> /upload (multipart chunks) -> /upload/finish
        `data` is the JSON you send to /upload/start, e.g. {"id": <asset_id>, "type": "audio", ...}
        """
        import hashlib, math, os

        # 1) start session
        start = self.post("/upload/start", data=data)
        if not start.get("success"):
            return start

        session = start.get("data") or {}
        upload_id = session.get("id")
        if not upload_id:
            return {
                "success": False,
                "status_code": start.get("status_code"),
                "error": {"message": "Missing upload_id"},
            }

        file_name = os.path.basename(file_path)
        try:
            total_size = os.stat(file_path).st_size
        except OSError as e:
            return {"success": False, "status_code": None, "error": {"message": str(e)}}

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
                        f"{self.api_url}/upload", headers=headers, files=files
                    )
                except requests.RequestException as e:
                    return {
                        "success": False,
                        "status_code": None,
                        "error": {"message": str(e)},
                    }

                if not resp.ok:
                    return {
                        "success": False,
                        "status_code": resp.status_code,
                        "error": {"message": resp.text},
                    }

                part_index += 1

        md5sum = md5.hexdigest()

        # 3) finish
        finish = self.post(
            "/upload/finish",
            data={"uuid": upload_id, "filename": file_name, "md5sum": md5sum},
        )
        if finish.get("success"):
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
