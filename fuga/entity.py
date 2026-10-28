import functools
from collections.abc import Callable
from typing import Any, ClassVar, Concatenate, ParamSpec, TypeVar

from .api import BaseFUGAClient
from .response import FugaResponse, error_response

P = ParamSpec("P")
E = TypeVar("E", bound="FUGAEntity")


class FUGAEntity:
    """A FUGA resource addressed by one id, such as an asset or a product."""

    # Name of the subclass's id attribute, e.g. "asset_id".
    id_field: ClassVar[str]

    def __init__(self, client: BaseFUGAClient) -> None:
        self.client = client

    def _need_id(self) -> FugaResponse:
        return error_response(f"{self.id_field} is required")


EntityMethod = Callable[Concatenate[E, P], FugaResponse]


def requires_id(method: EntityMethod[E, P]) -> EntityMethod[E, P]:
    """Return the "<id> is required" error instead of calling FUGA without an id."""

    @functools.wraps(method)
    def wrapper(self: E, *args: P.args, **kwargs: P.kwargs) -> FugaResponse:
        if not getattr(self, self.id_field):
            return self._need_id()
        return method(self, *args, **kwargs)

    return wrapper


def v2_only(method: EntityMethod[E, P]) -> EntityMethod[E, P]:
    """
    For endpoints FUGA removed in API v3. Through a client of another version
    the call fails here instead of reaching FUGA. A client without a string
    version, such as a test mock, is let through. Remove these methods in
    fuga 2.0.0.
    """

    @functools.wraps(method)
    def wrapper(self: E, *args: P.args, **kwargs: P.kwargs) -> FugaResponse:
        version = self.client.api_version
        if isinstance(version, str) and version != "v2":
            return error_response(
                f"{method.__name__} is only available in FUGA API v2, not {version}"
            )
        return method(self, *args, **kwargs)

    return wrapper


def paginate(
    client: BaseFUGAClient,
    endpoint: str,
    key: str,
    *,
    page: int,
    page_size: int,
    limit: int | None,
    every_page: bool = False,
) -> FugaResponse:
    """
    Without a `limit`, return the one page asked for, or with `every_page`,
    every page from it onwards. With a `limit`, fetch pages until there are
    `limit` items. Either way, stop once FUGA's reported total is reached or a
    page comes back empty, and return the items as one list under `key`.
    """
    params = {"page": page, "page_size": page_size}

    if not limit and not every_page:
        return client.get(endpoint, params=params)

    # FUGA's total counts every item, including those on pages before `page`.
    skipped = page * page_size
    collected: list[Any] = []
    last_status: int | None = None
    total = None
    pages_fetched = 0

    while True:
        resp = client.get(endpoint, params=params)
        last_status = resp["status_code"]

        if not resp["success"]:
            return resp

        data = resp.get("data") or {}
        items = data.get(key) or []
        total = data.get("total", total)

        collected.extend(items)
        pages_fetched += 1

        if limit and len(collected) >= limit:
            collected = collected[:limit]
            break

        if not items or (total is not None and skipped + len(collected) >= total):
            break

        params["page"] += 1

    return {
        "success": True,
        "status_code": last_status,
        "data": {
            key: collected,
            "total": total if total is not None else len(collected),
            "pages_fetched": pages_fetched,
            "limit_applied": bool(limit),
        },
    }
