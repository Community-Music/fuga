"""Every entity method sends the right method, path, body and query to FUGA."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest
from responses import matchers

from fuga.api import BaseFUGAClient
from fuga.artist import FUGAArtist
from fuga.asset import FUGAAsset
from fuga.delivery_instructions import FUGADeliveryInstructions
from fuga.entity import requires_id
from fuga.label import FUGALabel
from fuga.misc import FUGAMisc
from fuga.person import FUGAPerson
from fuga.product import FUGAProduct
from fuga.publishing_house import FUGAPublishingHouse
from fuga.release_project import FUGAReleaseProject
from fuga.response import FugaResponse

from .conftest import API_URL

BODY = {"name": "Example"}
PAGE = {"page": "0", "page_size": "10"}


@dataclass
class Case:
    name: str
    make: Callable[[Any, Any], Any]  # (client, entity_id) -> entity
    entity_id: Any
    invoke: Callable[[Any], Any]
    method: str
    path: str
    body: Any = None
    query: Any = None
    id_name: str | None = None  # set when the call needs an id


def entity_cases(cls, entity_id, id_name, base, *, list_query=PAGE):
    """The list/fetch/create/update/delete calls every entity has."""
    return [
        Case(
            f"{cls.__name__}.fetch_list",
            cls,
            entity_id,
            lambda e: e.fetch_list(),
            "GET",
            base,
            query=list_query,
        ),
        Case(
            f"{cls.__name__}.fetch",
            cls,
            entity_id,
            lambda e: e.fetch(),
            "GET",
            f"{base}/{entity_id}",
            id_name=id_name,
        ),
        Case(
            f"{cls.__name__}.create",
            cls,
            entity_id,
            lambda e: e.create(BODY),
            "POST",
            base,
            body=BODY,
        ),
        Case(
            f"{cls.__name__}.update",
            cls,
            entity_id,
            lambda e: e.update(BODY),
            "PUT",
            f"{base}/{entity_id}",
            body=BODY,
            id_name=id_name,
        ),
        Case(
            f"{cls.__name__}.delete",
            cls,
            entity_id,
            lambda e: e.delete(),
            "DELETE",
            f"{base}/{entity_id}",
            id_name=id_name,
        ),
    ]


CASES = [
    *entity_cases(FUGAAsset, "a1", "asset_id", "/assets"),
    Case(
        "FUGAAsset.attach_to_product",
        FUGAAsset,
        "a1",
        lambda e: e.attach_to_product("p1", BODY),
        "PUT",
        "/products/p1/assets/a1",
        body=BODY,
        id_name="asset_id",
    ),
    Case(
        "FUGAAsset.fetch_roles",
        FUGAAsset,
        "a1",
        lambda e: e.fetch_roles(),
        "GET",
        "/assets/a1/contributors",
        id_name="asset_id",
    ),
    Case(
        "FUGAAsset.add_role",
        FUGAAsset,
        "a1",
        lambda e: e.add_role(BODY),
        "POST",
        "/assets/a1/contributors",
        body=BODY,
        id_name="asset_id",
    ),
    Case(
        "FUGAAsset.remove_role",
        FUGAAsset,
        "a1",
        lambda e: e.remove_role("c1"),
        "DELETE",
        "/assets/a1/contributors/c1",
        id_name="asset_id",
    ),
    Case(
        "FUGAAsset.fetch_instrument_performers",
        FUGAAsset,
        "a1",
        lambda e: e.fetch_instrument_performers(),
        "GET",
        "/assets/a1/instrument_performers",
        id_name="asset_id",
    ),
    Case(
        "FUGAAsset.add_instrument_performer",
        FUGAAsset,
        "a1",
        lambda e: e.add_instrument_performer(BODY),
        "POST",
        "/assets/a1/instrument_performers",
        body=BODY,
        id_name="asset_id",
    ),
    Case(
        "FUGAAsset.remove_instrument_performer",
        FUGAAsset,
        "a1",
        lambda e: e.remove_instrument_performer("ip1"),
        "DELETE",
        "/assets/a1/instrument_performers/ip1",
        id_name="asset_id",
    ),
    Case(
        "FUGAAsset.fetch_publishers",
        FUGAAsset,
        "a1",
        lambda e: e.fetch_publishers(),
        "GET",
        "/assets/a1/publishers",
        id_name="asset_id",
    ),
    Case(
        "FUGAAsset.add_publisher",
        FUGAAsset,
        "a1",
        lambda e: e.add_publisher(BODY),
        "POST",
        "/assets/a1/publishers",
        body=BODY,
        id_name="asset_id",
    ),
    Case(
        "FUGAAsset.remove_publisher",
        FUGAAsset,
        "a1",
        lambda e: e.remove_publisher("ph1"),
        "DELETE",
        "/assets/a1/publishers/ph1",
        id_name="asset_id",
    ),
    *entity_cases(FUGAProduct, "p1", "product_id", "/products"),
    Case(
        "FUGAProduct.publish",
        FUGAProduct,
        "p1",
        lambda e: e.publish(),
        "POST",
        "/products/p1/publish",
        id_name="product_id",
    ),
    Case(
        "FUGAProduct.assign_barcode",
        FUGAProduct,
        "p1",
        lambda e: e.assign_barcode(),
        "POST",
        "/products/p1/barcode",
        id_name="product_id",
    ),
    Case(
        "FUGAProduct.fetch_artworks",
        FUGAProduct,
        "p1",
        lambda e: e.fetch_artworks(),
        "GET",
        "/products/p1/artworks",
        id_name="product_id",
    ),
    Case(
        "FUGAProduct.fetch_live_links",
        FUGAProduct,
        "p1",
        lambda e: e.fetch_live_links(),
        "GET",
        "/products/p1/live_links",
        id_name="product_id",
    ),
    Case(
        "FUGAProduct.update_territories",
        FUGAProduct,
        "p1",
        lambda e: e.update_territories(["GB", "US"]),
        "PUT",
        "/products/p1/territories",
        body=["GB", "US"],
        id_name="product_id",
    ),
    Case(
        "FUGAProduct.fetch_assets",
        FUGAProduct,
        "p1",
        lambda e: e.fetch_assets(),
        "GET",
        "/products/p1/assets",
        id_name="product_id",
    ),
    Case(
        "FUGAProduct.add_asset",
        FUGAProduct,
        "p1",
        lambda e: e.add_asset("a1", 2),
        "POST",
        "/products/p1/assets",
        body={"id": "a1", "sequence": 2},
        id_name="product_id",
    ),
    Case(
        "FUGAProduct.remove_asset",
        FUGAProduct,
        "p1",
        lambda e: e.remove_asset("a1"),
        "DELETE",
        "/products/p1/assets/a1",
        id_name="product_id",
    ),
    Case(
        "FUGAProduct.update_asset_sequence",
        FUGAProduct,
        "p1",
        lambda e: e.update_asset_sequence("a1", 3),
        "PUT",
        "/products/p1/assets/a1/position/3",
        body={},
        id_name="product_id",
    ),
    *entity_cases(FUGAArtist, "ar1", "artist_id", "/artists"),
    Case(
        "FUGAArtist.fetch_identifiers",
        FUGAArtist,
        "ar1",
        lambda e: e.fetch_identifiers(),
        "GET",
        "/artists/ar1/identifier",
        id_name="artist_id",
    ),
    Case(
        "FUGAArtist.fetch_identifier",
        FUGAArtist,
        "ar1",
        lambda e: e.fetch_identifier("i1"),
        "GET",
        "/artists/ar1/identifier/i1",
        id_name="artist_id",
    ),
    Case(
        "FUGAArtist.create_identifier",
        FUGAArtist,
        "ar1",
        lambda e: e.create_identifier(BODY),
        "POST",
        "/artists/ar1/identifier",
        body=BODY,
        id_name="artist_id",
    ),
    Case(
        "FUGAArtist.update_identifier",
        FUGAArtist,
        "ar1",
        lambda e: e.update_identifier("i1", BODY),
        "PUT",
        "/artists/ar1/identifier/i1",
        body=BODY,
        id_name="artist_id",
    ),
    Case(
        "FUGAArtist.delete_identifier",
        FUGAArtist,
        "ar1",
        lambda e: e.delete_identifier("i1"),
        "DELETE",
        "/artists/ar1/identifier/i1",
        id_name="artist_id",
    ),
    *entity_cases(FUGALabel, "l1", "label_id", "/labels"),
    *entity_cases(FUGAPerson, "pe1", "person_id", "/people"),
    *entity_cases(
        FUGAPublishingHouse, "ph1", "publishing_house_id", "/publishing_houses"
    ),
    *entity_cases(FUGAReleaseProject, "rp1", "release_project_id", "/release_projects"),
    Case(
        "FUGAReleaseProject.fetch_products",
        FUGAReleaseProject,
        "rp1",
        lambda e: e.fetch_products(),
        "GET",
        "/release_projects/rp1/products",
        query=PAGE,
        id_name="release_project_id",
    ),
    Case(
        "FUGAReleaseProject.add_products",
        FUGAReleaseProject,
        "rp1",
        lambda e: e.add_products(["p1"]),
        "POST",
        "/release_projects/rp1/products",
        body={"products_ids": ["p1"]},
        id_name="release_project_id",
    ),
    Case(
        "FUGAReleaseProject.remove_products",
        FUGAReleaseProject,
        "rp1",
        lambda e: e.remove_products(["p1"]),
        "DELETE",
        "/release_projects/rp1/products",
        body={"products_ids": ["p1"]},
        id_name="release_project_id",
    ),
    Case(
        "FUGADeliveryInstructions.fetch",
        FUGADeliveryInstructions,
        "p1",
        lambda e: e.fetch(),
        "GET",
        "/products/p1/delivery_instructions",
        id_name="product_id",
    ),
    Case(
        "FUGADeliveryInstructions.fetch_dsp_history",
        FUGADeliveryInstructions,
        "p1",
        lambda e: e.fetch_dsp_history(5),
        "GET",
        "/products/p1/delivery_instructions/5/history",
        id_name="product_id",
    ),
    Case(
        "FUGADeliveryInstructions.reset",
        FUGADeliveryInstructions,
        "p1",
        lambda e: e.reset(),
        "DELETE",
        "/products/p1/delivery_instructions",
        id_name="product_id",
    ),
    Case(
        "FUGADeliveryInstructions.block",
        FUGADeliveryInstructions,
        "p1",
        lambda e: e.block([1, 2]),
        "PUT",
        "/products/p1/delivery_instructions/block",
        body=[{"dsp": 1}, {"dsp": 2}],
        id_name="product_id",
    ),
    Case(
        "FUGADeliveryInstructions.unblock",
        FUGADeliveryInstructions,
        "p1",
        lambda e: e.unblock(3),
        "PUT",
        "/products/p1/delivery_instructions/unblock",
        body=[{"dsp": 3}],
        id_name="product_id",
    ),
    Case(
        "FUGADeliveryInstructions.deliver",
        FUGADeliveryInstructions,
        "p1",
        lambda e: e.deliver([{"dsp": 4, "lead_time": 2}]),
        "POST",
        "/products/p1/delivery_instructions/deliver",
        body=[{"dsp": 4, "lead_time": 2}],
        id_name="product_id",
    ),
    Case(
        "FUGADeliveryInstructions.redeliver",
        FUGADeliveryInstructions,
        "p1",
        lambda e: e.redeliver("5"),
        "POST",
        "/products/p1/delivery_instructions/redeliver",
        body=[{"dsp": "5"}],
        id_name="product_id",
    ),
    Case(
        "FUGADeliveryInstructions.redeliver_all",
        FUGADeliveryInstructions,
        "p1",
        lambda e: e.redeliver_all(),
        "POST",
        "/products/p1/delivery_instructions/redeliver_all",
        id_name="product_id",
    ),
    Case(
        "FUGADeliveryInstructions.takedown",
        FUGADeliveryInstructions,
        "p1",
        lambda e: e.takedown({"dsp": 6}),
        "POST",
        "/products/p1/delivery_instructions/takedown",
        body=[{"dsp": 6}],
        id_name="product_id",
    ),
    Case(
        "FUGADeliveryInstructions.edit",
        FUGADeliveryInstructions,
        "p1",
        lambda e: e.edit([{"dsp": 7, "lead_time": 1}]),
        "PUT",
        "/products/p1/delivery_instructions/edit",
        body=[{"dsp": 7, "lead_time": 1}],
        id_name="product_id",
    ),
    Case(
        "FUGADeliveryInstructions.make_exclusive",
        FUGADeliveryInstructions,
        "p1",
        lambda e: e.make_exclusive(),
        "PUT",
        "/products/p1/delivery_instructions/exclusive",
        id_name="product_id",
    ),
    Case(
        "FUGADeliveryInstructions.remove_exclusive",
        FUGADeliveryInstructions,
        "p1",
        lambda e: e.remove_exclusive(),
        "DELETE",
        "/products/p1/delivery_instructions/exclusive",
        id_name="product_id",
    ),
    Case(
        "FUGAMisc.fetch_genres",
        lambda c, _: FUGAMisc(c),
        None,
        lambda e: e.fetch_genres(),
        "GET",
        "/miscellaneous/genres",
    ),
    Case(
        "FUGAMisc.create_subgenre",
        lambda c, _: FUGAMisc(c),
        None,
        lambda e: e.create_subgenre(BODY),
        "POST",
        "/miscellaneous/subgenres",
        body=BODY,
    ),
    Case(
        "FUGAMisc.delete_subgenre",
        lambda c, _: FUGAMisc(c),
        None,
        lambda e: e.delete_subgenre("s1"),
        "DELETE",
        "/miscellaneous/subgenres/s1",
    ),
    *[
        Case(
            f"FUGAMisc.{method}",
            lambda c, _: FUGAMisc(c),
            None,
            lambda e, m=method: getattr(e, m)(),
            "GET",
            f"/miscellaneous/{path}",
        )
        for method, path in [
            ("fetch_languages", "languages"),
            ("fetch_audio_locales", "audio_locales"),
            ("fetch_contributor_roles", "contributor_roles"),
            ("fetch_catalog_tiers", "catalog-tiers"),
            ("fetch_instruments", "instruments"),
            ("fetch_territories", "territories"),
            ("fetch_encodings", "encodings"),
            ("fetch_lead_times", "lead_times"),
        ]
    ],
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_endpoint(mocked, client, case):
    match = []
    if case.body is not None:
        match.append(matchers.json_params_matcher(case.body))
    if case.query is not None:
        match.append(matchers.query_param_matcher(case.query))
    mocked.add(case.method, f"{API_URL}{case.path}", json={"ok": True}, match=match)

    resp = case.invoke(case.make(client, case.entity_id))

    assert resp == {"success": True, "status_code": 200, "data": {"ok": True}}
    if case.body is None:
        assert not mocked.calls[0].request.body


@pytest.mark.parametrize("case", [c for c in CASES if c.id_name], ids=lambda c: c.name)
def test_calls_without_an_id_fail_without_a_request(mocked, client, case):
    resp = case.invoke(case.make(client, None))

    assert resp == {
        "success": False,
        "status_code": None,
        "error": {"message": f"{case.id_name} is required"},
    }
    assert len(mocked.calls) == 0


def id_arg_case(name, invoke, arg_name):
    return pytest.param(invoke, arg_name, id=name)


@pytest.mark.parametrize(
    ("invoke", "arg_name"),
    [
        id_arg_case(
            "FUGAAsset.attach_to_product",
            lambda c: FUGAAsset(c, "a1").attach_to_product("", BODY),
            "product_id",
        ),
        id_arg_case(
            "FUGAAsset.remove_publisher",
            lambda c: FUGAAsset(c, "a1").remove_publisher(""),
            "publisher_id",
        ),
        id_arg_case(
            "FUGAAsset.remove_role",
            lambda c: FUGAAsset(c, "a1").remove_role(""),
            "contributor_id",
        ),
        id_arg_case(
            "FUGAAsset.remove_instrument_performer",
            lambda c: FUGAAsset(c, "a1").remove_instrument_performer(""),
            "instrument_performer_id",
        ),
        id_arg_case(
            "FUGAProduct.remove_asset",
            lambda c: FUGAProduct(c, "p1").remove_asset(""),
            "asset_id",
        ),
        id_arg_case(
            "FUGAProduct.update_asset_sequence",
            lambda c: FUGAProduct(c, "p1").update_asset_sequence(
                asset_id="", sequence=1
            ),
            "asset_id",
        ),
        id_arg_case(
            "FUGAArtist.fetch_identifier",
            lambda c: FUGAArtist(c, "ar1").fetch_identifier(""),
            "identifier_id",
        ),
        id_arg_case(
            "FUGAArtist.update_identifier",
            lambda c: FUGAArtist(c, "ar1").update_identifier("", BODY),
            "identifier_id",
        ),
        id_arg_case(
            "FUGAArtist.delete_identifier",
            lambda c: FUGAArtist(c, "ar1").delete_identifier(""),
            "identifier_id",
        ),
        id_arg_case(
            "FUGADeliveryInstructions.fetch_dsp_history",
            lambda c: FUGADeliveryInstructions(c, "p1").fetch_dsp_history(""),
            "dsp_id",
        ),
        id_arg_case(
            "FUGAMisc.delete_subgenre",
            lambda c: FUGAMisc(c).delete_subgenre(""),
            "subgenre_id",
        ),
    ],
)
def test_calls_without_an_id_argument_fail_without_a_request(
    mocked, client, invoke, arg_name
):
    resp = invoke(client)

    assert resp == {
        "success": False,
        "status_code": None,
        "error": {"message": f"{arg_name} is required"},
    }
    assert len(mocked.calls) == 0


def test_the_entity_id_is_checked_before_id_arguments(mocked, client):
    resp = FUGAAsset(client).remove_publisher("")

    assert resp.get("error") == {"message": "asset_id is required"}


def test_requires_id_rejects_an_argument_the_method_lacks():
    with pytest.raises(TypeError, match="has no argument publisher_id"):

        @requires_id("publisher_id")
        def remove(self: Any, other_id: str) -> FugaResponse:
            ...


# ---- create stores the new id ----


@pytest.mark.parametrize(
    ("cls", "path", "id_name"),
    [
        (FUGAAsset, "/assets", "asset_id"),
        (FUGAProduct, "/products", "product_id"),
        (FUGAArtist, "/artists", "artist_id"),
        (FUGALabel, "/labels", "label_id"),
        (FUGAPerson, "/people", "person_id"),
        (FUGAPublishingHouse, "/publishing_houses", "publishing_house_id"),
        (FUGAReleaseProject, "/release_projects", "release_project_id"),
    ],
)
def test_create_stores_the_new_id(mocked, client, cls, path, id_name):
    mocked.post(f"{API_URL}{path}", json={"id": "new-1"})

    entity = cls(client)
    entity.create(BODY)

    assert getattr(entity, id_name) == "new-1"


@pytest.mark.parametrize(
    "payload",
    [{"asset": {"id": "new-1"}}, {"asset": [{"id": "new-1"}]}],
    ids=["asset-object", "asset-list"],
)
def test_asset_create_finds_the_id_in_other_shapes(mocked, client, payload):
    mocked.post(f"{API_URL}/assets", json=payload)

    asset = FUGAAsset(client)
    asset.create(BODY)

    assert asset.asset_id == "new-1"


def test_failed_create_leaves_the_id_unset(mocked, client):
    mocked.post(f"{API_URL}/labels", json={"code": "BAD"}, status=400)

    label = FUGALabel(client)
    resp = label.create(BODY)

    assert resp["success"] is False
    assert label.label_id is None


# ---- pagination with a limit ----

LISTS = [
    pytest.param(
        lambda c, **kw: FUGAAsset(c).fetch_list(**kw),
        "/assets",
        "asset",
        10,
        id="assets",
    ),
    pytest.param(
        lambda c, **kw: FUGAProduct(c).fetch_list(**kw),
        "/products",
        "product",
        10,
        id="products",
    ),
    pytest.param(
        lambda c, **kw: FUGAArtist(c).fetch_list(**kw),
        "/artists",
        "artist",
        10,
        id="artists",
    ),
    pytest.param(
        lambda c, **kw: FUGALabel(c).fetch_list(**kw),
        "/labels",
        "label",
        10,
        id="labels",
    ),
    pytest.param(
        lambda c, **kw: FUGAPerson(c).fetch_list(**kw),
        "/people",
        "person",
        10,
        id="people",
    ),
    pytest.param(
        lambda c, **kw: FUGAPublishingHouse(c).fetch_list(**kw),
        "/publishing_houses",
        "publishing_house",
        10,
        id="publishing-houses",
    ),
    pytest.param(
        lambda c, **kw: FUGAReleaseProject(c).fetch_list(**kw),
        "/release_projects",
        "release_project",
        10,
        id="release-projects",
    ),
    pytest.param(
        lambda c, **kw: FUGAReleaseProject(c, "rp1").fetch_products(**kw),
        "/release_projects/rp1/products",
        "product",
        10,
        id="release-project-products",
    ),
    pytest.param(
        lambda c, **kw: FUGAMisc(c).fetch_subgenres(**kw),
        "/miscellaneous/subgenres",
        "subgenre",
        50,
        id="subgenres",
    ),
]


def register_pages(mocked, path, key, page_size, pages, total):
    for number, items in enumerate(pages):
        mocked.get(
            f"{API_URL}{path}",
            json={key: items, "total": total},
            match=[
                matchers.query_param_matcher(
                    {"page": str(number), "page_size": str(page_size)}
                )
            ],
        )


@pytest.mark.parametrize(("fetch", "path", "key", "page_size"), LISTS)
def test_limit_collects_pages_until_total(mocked, client, fetch, path, key, page_size):
    register_pages(mocked, path, key, page_size, [[1, 2], [3, 4], [5]], total=5)

    resp = fetch(client, limit=100)

    assert resp == {
        "success": True,
        "status_code": 200,
        "data": {
            key: [1, 2, 3, 4, 5],
            "total": 5,
            "pages_fetched": 3,
            "limit_applied": True,
        },
    }


@pytest.mark.parametrize(("fetch", "path", "key", "page_size"), LISTS)
def test_limit_stops_at_the_limit(mocked, client, fetch, path, key, page_size):
    register_pages(mocked, path, key, page_size, [[1, 2], [3, 4]], total=9)

    resp = fetch(client, limit=3)

    assert resp["data"] == {
        key: [1, 2, 3],
        "total": 9,
        "pages_fetched": 2,
        "limit_applied": True,
    }


@pytest.mark.parametrize(("fetch", "path", "key", "page_size"), LISTS)
def test_limit_stops_at_an_empty_page(mocked, client, fetch, path, key, page_size):
    register_pages(mocked, path, key, page_size, [[1, 2], []], total=None)

    resp = fetch(client, limit=100)

    assert resp["data"] == {
        key: [1, 2],
        "total": 2,
        "pages_fetched": 2,
        "limit_applied": True,
    }


@pytest.mark.parametrize(("fetch", "path", "key", "page_size"), LISTS)
def test_limit_returns_a_failed_page(mocked, client, fetch, path, key, page_size):
    register_pages(mocked, path, key, page_size, [[1, 2]], total=9)
    mocked.get(f"{API_URL}{path}", json={"code": "BOOM"}, status=500)

    resp = fetch(client, limit=100)

    assert resp == {"success": False, "status_code": 500, "error": {"code": "BOOM"}}


# ---- media ----


def test_fetch_audio_returns_bytes(mocked, client):
    mocked.get(
        f"{API_URL}/assets/a1/audio",
        body=b"RIFF",
        content_type="audio/wav",
        match=[matchers.query_param_matcher({"original": "True"})],
    )

    resp = FUGAAsset(client, "a1").fetch_audio()

    assert resp["success"] is True
    assert resp.get("data") == b"RIFF"


def test_fetch_image_returns_bytes(mocked, client):
    mocked.get(
        f"{API_URL}/products/p1/image/full_size",
        body=b"\x89PNG",
        content_type="image/png",
    )

    resp = FUGAProduct(client, "p1").fetch_image()

    assert resp.get("data") == b"\x89PNG"


@pytest.fixture
def media_file(tmp_path):
    path = tmp_path / "media.bin"
    path.write_bytes(b"0123")
    return str(path)


def register_single_chunk_upload(mocked, start_body):
    mocked.post(
        f"{API_URL}/upload/start",
        json={"id": "upload-1"},
        match=[matchers.json_params_matcher(start_body)],
    )
    chunk = mocked.post(f"{API_URL}/upload", body="ok")
    mocked.post(f"{API_URL}/upload/finish", json=True)
    return chunk


@pytest.mark.parametrize(
    ("invoke", "start_body"),
    [
        pytest.param(
            lambda c, f: FUGAAsset(c, "a1").upload_audio(f),
            {
                "id": "a1",
                "type": "audio",
                "overwrite_all": True,
                "clear_all_encodings": True,
            },
            id="audio",
        ),
        pytest.param(
            lambda c, f: FUGAAsset(c, "a1").upload_audio(
                f, is_apple_digital_master=True
            ),
            {
                "id": "a1",
                "type": "audio",
                "overwrite_all": True,
                "clear_all_encodings": True,
                "original_encoding": "ADM",
            },
            id="audio-apple-digital-master",
        ),
        pytest.param(
            lambda c, f: FUGAAsset(c, "a1").upload_video(f),
            {"id": "a1", "type": "video"},
            id="video",
        ),
        pytest.param(
            lambda c, f: FUGAAsset(c, "a1").upload_video_preview_image("img9", f),
            {"id": "img9", "type": "image_preview_image"},
            id="video-preview-image",
        ),
        pytest.param(
            lambda c, f: FUGAProduct(c, "p1").upload_cover_image("img1", f),
            {"id": "img1", "type": "image"},
            id="cover-image",
        ),
    ],
)
def test_uploads_start_with_the_right_payload(
    mocked, client, media_file, invoke, start_body
):
    chunk = register_single_chunk_upload(mocked, start_body)

    resp = invoke(client, media_file)

    assert resp["success"] is True
    assert chunk.call_count == 1


@pytest.mark.parametrize(
    ("invoke", "id_name"),
    [
        (lambda c, f: FUGAAsset(c).upload_audio(f), "asset_id"),
        (lambda c, f: FUGAAsset(c).upload_video(f), "asset_id"),
        (lambda c, f: FUGAAsset(c).upload_video_preview_image("img9", f), "asset_id"),
        (lambda c, f: FUGAAsset(c).fetch_audio(), "asset_id"),
        (lambda c, f: FUGAProduct(c).upload_cover_image("img1", f), "product_id"),
        (lambda c, f: FUGAProduct(c).fetch_image(), "product_id"),
    ],
)
def test_media_calls_need_an_id(mocked, client, media_file, invoke, id_name):
    resp = invoke(client, media_file)

    assert resp["error"] == {"message": f"{id_name} is required"}
    assert len(mocked.calls) == 0


# ---- v2-only methods ----


class V3Client(BaseFUGAClient):
    """Stands in for the v3 client: same HTTP layer, no login."""

    api_version = "v3"

    def _is_authenticated(self):
        return True

    def authenticate(self):
        pass


@pytest.mark.parametrize(
    ("name", "invoke"),
    [
        ("remove_role", lambda a: a.remove_role("c1")),
        ("fetch_instrument_performers", lambda a: a.fetch_instrument_performers()),
        ("add_instrument_performer", lambda a: a.add_instrument_performer(BODY)),
        ("remove_instrument_performer", lambda a: a.remove_instrument_performer("ip1")),
    ],
)
def test_v2_only_methods_fail_on_another_version(mocked, name, invoke):
    resp = invoke(FUGAAsset(V3Client(API_URL), "a1"))

    assert resp == {
        "success": False,
        "status_code": None,
        "error": {"message": f"{name} is only available in FUGA API v2, not v3"},
    }
    assert len(mocked.calls) == 0


def test_shared_methods_work_on_another_version(mocked):
    mocked.get(f"{API_URL}/assets/a1/contributors", json={"contributors": []})

    resp = FUGAAsset(V3Client(API_URL), "a1").fetch_roles()

    assert resp["success"] is True


# ---- subgenres: every page unless a limit is given ----

SUBGENRES = "/miscellaneous/subgenres"


def test_subgenres_without_a_limit_fetch_every_page(mocked, client):
    first = [{"id": f"S{i}"} for i in range(50)]
    second = [{"id": f"S{i}"} for i in range(50, 65)]
    register_pages(mocked, SUBGENRES, "subgenre", 50, [first, second], total=65)

    resp = FUGAMisc(client).fetch_subgenres()

    assert resp == {
        "success": True,
        "status_code": 200,
        "data": {
            "subgenre": first + second,
            "total": 65,
            "pages_fetched": 2,
            "limit_applied": False,
        },
    }


def test_subgenres_without_a_total_stop_at_an_empty_page(mocked, client):
    register_pages(mocked, SUBGENRES, "subgenre", 50, [[1, 2], [3], []], total=None)

    resp = FUGAMisc(client).fetch_subgenres()

    assert resp.get("data", {})["subgenre"] == [1, 2, 3]
    assert resp.get("data", {})["pages_fetched"] == 3


def test_subgenres_start_from_the_page_asked_for(mocked, client):
    mocked.get(
        f"{API_URL}{SUBGENRES}",
        json={"subgenre": [9], "total": 1},
        match=[matchers.query_param_matcher({"page": "2", "page_size": "5"})],
    )

    resp = FUGAMisc(client).fetch_subgenres(page=2, page_size=5)

    assert resp.get("data", {})["subgenre"] == [9]


def test_subgenres_return_a_failed_page(mocked, client):
    register_pages(mocked, SUBGENRES, "subgenre", 50, [[1]], total=65)
    mocked.get(f"{API_URL}{SUBGENRES}", json={"code": "BOOM"}, status=500)

    resp = FUGAMisc(client).fetch_subgenres()

    assert resp == {"success": False, "status_code": 500, "error": {"code": "BOOM"}}


@pytest.mark.parametrize(
    "reply",
    [
        {"json": [1, 2]},
        {"body": "ok"},
        {"json": None},
        {"json": {"subgenre": {"id": "S1"}}},
    ],
    ids=["list", "text", "null", "subgenre-not-a-list"],
)
def test_a_page_without_a_list_is_an_error(mocked, client, reply):
    mocked.get(f"{API_URL}{SUBGENRES}", **reply)

    resp = FUGAMisc(client).fetch_subgenres()

    assert resp == {
        "success": False,
        "status_code": 200,
        "error": {
            "message": f"FUGA returned a page of {SUBGENRES} without a subgenre list"
        },
    }


def test_pagination_stops_at_the_page_cap(mocked, client, monkeypatch):
    monkeypatch.setattr("fuga.entity.MAX_PAGES", 3)
    # The same non-empty page, with no total, for every page number
    page = mocked.get(f"{API_URL}{SUBGENRES}", json={"subgenre": [1]})

    resp = FUGAMisc(client).fetch_subgenres()

    assert resp == {
        "success": False,
        "status_code": 200,
        "error": {
            "message": f"Stopped after 3 pages of {SUBGENRES} without reaching the end"
        },
    }
    assert page.call_count == 3


# ---- audit follow-ups: pagination start page, limit=0, mocked clients ----


def test_every_page_counts_pages_before_the_start(mocked, client):
    last = [{"id": f"S{i}"} for i in range(50, 65)]
    mocked.get(
        f"{API_URL}{SUBGENRES}",
        json={"subgenre": last, "total": 65},
        match=[matchers.query_param_matcher({"page": "1", "page_size": "50"})],
    )

    resp = FUGAMisc(client).fetch_subgenres(page=1)

    assert resp["success"] is True
    assert resp.get("data", {})["subgenre"] == last
    assert resp.get("data", {})["pages_fetched"] == 1


def test_limit_counts_pages_before_the_start(mocked, client):
    mocked.get(
        f"{API_URL}/labels",
        json={"label": [3, 4], "total": 4},
        match=[matchers.query_param_matcher({"page": "1", "page_size": "2"})],
    )

    resp = FUGALabel(client).fetch_list(page=1, page_size=2, limit=10)

    assert resp.get("data", {})["label"] == [3, 4]
    assert resp.get("data", {})["pages_fetched"] == 1


def test_a_limit_of_zero_returns_the_one_page_as_sent(mocked, client):
    mocked.get(f"{API_URL}/labels", json={"label": [1], "total": 5})

    resp = FUGALabel(client).fetch_list(limit=0)

    assert resp == {
        "success": True,
        "status_code": 200,
        "data": {"label": [1], "total": 5},
    }


def test_v2_only_methods_reach_a_mocked_v2_client():
    client = MagicMock(api_version="v2")

    FUGAAsset(client, "a1").fetch_instrument_performers()

    client.get.assert_called_once_with("/assets/a1/instrument_performers")


@pytest.mark.parametrize(
    "client",
    [MagicMock(), MagicMock(api_version=2), MagicMock(spec=["get"])],
    ids=["mock-without-a-version", "non-string-version", "no-version-attribute"],
)
def test_v2_only_methods_refuse_a_client_that_is_not_v2(client):
    resp = FUGAAsset(client, "a1").fetch_instrument_performers()

    assert resp["success"] is False
    assert "only available in FUGA API v2" in resp.get("error", {})["message"]
    client.get.assert_not_called()


def test_a_client_without_its_auth_hooks_cannot_be_built():
    class NoAuthClient(BaseFUGAClient):
        api_version = "v3"

    with pytest.raises(TypeError, match="abstract"):
        NoAuthClient(API_URL)  # type: ignore[abstract]
