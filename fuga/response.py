from typing import Any, TypedDict


class _FugaResponseBase(TypedDict):
    success: bool
    status_code: int | None


class FugaResponse(_FugaResponseBase, total=False):
    """
    What every call in the package returns instead of raising.

    `data` is set on success and `error` on failure. `headers` is set only by
    binary reads. `status_code` is None when no request reached FUGA.
    """

    data: Any
    error: dict[str, Any]
    headers: dict[str, str]


# A JSON request body: FUGA takes a list on some endpoints, e.g. territories.
JSONBody = dict[str, Any] | list[Any]


def error_response(message: str, status_code: int | None = None) -> FugaResponse:
    return {"success": False, "status_code": status_code, "error": {"message": message}}
