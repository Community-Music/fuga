import functools
import inspect
from collections.abc import Callable
from typing import Any, ClassVar, Concatenate, ParamSpec, Protocol, TypeVar, overload

from .api import BaseFUGAClient
from .response import FugaResponse, error_response

P = ParamSpec("P")
E = TypeVar("E", bound="FUGAEntity")
C = TypeVar("C", bound="HasClient")

# The most pages one paginate() call fetches. It only stops a FUGA that never
# sends an empty page or a total; the longest real list, subgenres, is 2 pages.
MAX_PAGES = 1000


class FUGAEntity:
    """A FUGA resource addressed by one id, such as an asset or a product."""

    # Name of the subclass's id attribute, e.g. "asset_id".
    id_field: ClassVar[str]

    def __init__(self, client: BaseFUGAClient) -> None:
        self.client = client

    def _need_id(self) -> FugaResponse:
        return error_response(f"{self.id_field} is required")


class HasClient(Protocol):
    """Anything that sends its requests through a client, entity or not."""

    client: BaseFUGAClient


EntityMethod = Callable[Concatenate[E, P], FugaResponse]
ClientMethod = Callable[Concatenate[C, P], FugaResponse]


@overload
def requires_id(method: EntityMethod[E, P], /) -> EntityMethod[E, P]:
    ...


@overload
def requires_id(
    *arg_names: str,
) -> Callable[[EntityMethod[E, P]], EntityMethod[E, P]]:
    ...


def requires_id(*args: Any) -> Any:
    """
    Return the "<id> is required" error instead of calling FUGA without an id.

    `@requires_id` checks the entity's own id. `@requires_id("publisher_id")`
    also checks the named arguments, for ids that go into the path, so an empty
    one can't turn a call on one item into a call on the whole collection.
    """
    # Bare, the one argument is the method; called, every argument is a name
    if len(args) == 1 and not isinstance(args[0], str):
        return _check_ids(args[0], ())
    return functools.partial(_check_ids, arg_names=args)


def _check_ids(
    method: EntityMethod[E, P], arg_names: tuple[str, ...]
) -> EntityMethod[E, P]:
    signature = inspect.signature(method)
    for name in arg_names:
        if name not in signature.parameters:
            raise TypeError(f"{method.__name__} has no argument {name}")

    @functools.wraps(method)
    def wrapper(self: E, *args: P.args, **kwargs: P.kwargs) -> FugaResponse:
        if not getattr(self, self.id_field):
            return self._need_id()
        if arg_names:
            bound = signature.bind(self, *args, **kwargs)
            bound.apply_defaults()
            for name in arg_names:
                if not bound.arguments[name]:
                    return error_response(f"{name} is required")
        return method(self, *args, **kwargs)

    return wrapper


def v2_only(method: EntityMethod[E, P]) -> EntityMethod[E, P]:
    """
    For endpoints FUGA removed in API v3, or whose request and reply changed
    shape there. Through any client whose `api_version` isn't "v2", including
    a test mock that doesn't set one, the call fails here instead of reaching
    FUGA. Remove these methods in fuga 2.0.0.
    """

    @functools.wraps(method)
    def wrapper(self: E, *args: P.args, **kwargs: P.kwargs) -> FugaResponse:
        version = getattr(self.client, "api_version", None)
        if version != "v2":
            return error_response(
                f"{method.__name__} is only available in FUGA API v2, not {version}"
            )
        return method(self, *args, **kwargs)

    return wrapper


def v3_only(method: ClientMethod[C, P]) -> ClientMethod[C, P]:
    """
    For endpoints only FUGA API v3 has, or whose meaning changed there, such as
    the contributor delete keyed by person id rather than entry id. Through any
    client whose `api_version` isn't "v3", including a test mock that doesn't
    set one, the call fails here instead of reaching FUGA.
    """

    @functools.wraps(method)
    def wrapper(self: C, *args: P.args, **kwargs: P.kwargs) -> FugaResponse:
        version = getattr(self.client, "api_version", None)
        if version != "v3":
            return error_response(
                f"{method.__name__} is only available in FUGA API v3, not {version}"
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
    A page that isn't an object with a list under `key`, or a list that runs
    past MAX_PAGES pages, returns an error.
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
        if pages_fetched == MAX_PAGES:
            return error_response(
                f"Stopped after {MAX_PAGES} pages of {endpoint} without reaching the end",
                last_status,
            )

        resp = client.get(endpoint, params=params)
        last_status = resp["status_code"]

        if not resp["success"]:
            return resp

        # A page must be an object with a list under `key`; an empty page may
        # leave the key out
        data = resp.get("data")
        if not isinstance(data, dict) or not isinstance(data.get(key) or [], list):
            return error_response(
                f"FUGA returned a page of {endpoint} without a {key} list",
                last_status,
            )
        items = data.get(key) or []
        if isinstance(data.get("total"), int):
            total = data["total"]

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
