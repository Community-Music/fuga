import pytest
from responses import matchers

from fuga.trends import FUGATrends

from .conftest import API_URL

START, END = "2026-01-01", "2026-01-31"


def test_fetch_chart_sends_selection_and_filters(mocked, client):
    mocked.get(
        f"{API_URL}/trends/chart",
        json={"ok": True},
        match=[
            matchers.query_param_matcher(
                {
                    "selection_type": "dsp",
                    "sale_type": "stream",
                    "start_date": START,
                    "end_date": END,
                    "product_id": "9",
                    "asset_ids": ["1", "2"],
                }
            )
        ],
    )

    resp = FUGATrends(client).fetch_chart(
        "dsp", START, END, product_id=9, asset_ids=[1, 2]
    )

    assert resp == {"success": True, "status_code": 200, "data": {"ok": True}}


def test_fetch_totals_sends_only_given_filters(mocked, client):
    mocked.get(
        f"{API_URL}/trends/totals",
        json={"ok": True},
        match=[
            matchers.query_param_matcher(
                {
                    "selection_type": "asset",
                    "start_date": START,
                    "end_date": END,
                    "label_id": "4",
                    "asset_ids": "7",
                }
            )
        ],
    )

    resp = FUGATrends(client).fetch_totals(
        "asset", START, END, label_id=4, asset_ids=7, unknown_filter="ignored"
    )

    assert resp["success"] is True


def test_trends_files_get_passes_params_through(mocked, client):
    mocked.get(
        f"{API_URL}/trends_file_reports",
        json={"trends_file_report": []},
        match=[
            matchers.query_param_matcher(
                {"updated_since": "1700000000000", "page": "0"}
            )
        ],
    )

    resp = FUGATrends(client).trends_files_get(
        params={"updated_since": 1700000000000, "page": 0}
    )

    assert resp["success"] is True


@pytest.mark.parametrize(
    ("invoke", "message"),
    [
        pytest.param(
            lambda t: t.fetch_chart("artist", START, END),
            "selection_type must be one of ['asset', 'dsp', 'label', 'product', 'territory']",
            id="chart-bad-selection",
        ),
        pytest.param(
            lambda t: t.fetch_chart("dsp", START, END, sale_type="rental"),
            "sale_type must be one of ['download', 'stream']",
            id="chart-bad-sale-type",
        ),
        pytest.param(
            lambda t: t.fetch_totals("artist", START, END),
            "selection_type must be one of ['asset', 'dsp', 'label', 'product', 'territory']",
            id="totals-bad-selection",
        ),
    ],
)
def test_bad_arguments_fail_without_a_request(mocked, client, invoke, message):
    resp = invoke(FUGATrends(client))

    assert resp == {
        "success": False,
        "status_code": None,
        "error": {"message": message},
    }
    assert len(mocked.calls) == 0


@pytest.mark.parametrize(
    "asset_ids",
    [
        pytest.param([1, 2], id="list"),
        pytest.param({1, 2}, id="set"),
        pytest.param(range(1, 3), id="range"),
        pytest.param((i for i in [1, 2]), id="generator"),
    ],
)
def test_asset_ids_from_any_iterable_are_repeated(mocked, client, asset_ids):
    mocked.get(
        f"{API_URL}/trends/chart",
        json={"ok": True},
        match=[
            matchers.query_param_matcher(
                {
                    "selection_type": "asset",
                    "sale_type": "stream",
                    "start_date": START,
                    "end_date": END,
                    "asset_ids": ["1", "2"],
                }
            )
        ],
    )

    resp = FUGATrends(client).fetch_chart("asset", START, END, asset_ids=asset_ids)

    assert resp["success"] is True
