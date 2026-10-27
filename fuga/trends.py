from collections.abc import Iterable
from typing import Any, ClassVar

from .api import BaseFUGAClient
from .response import FugaResponse, error_response

SelectionType = str  # "dsp" | "territory" | "label" | "product" | "asset"
SaleType = str  # "stream" | "download"


def _normalize_asset_ids(
    value: None | str | int | Iterable[str | int],
) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, (str, int)):
        return [str(value)]
    # any iterable: list, tuple, set, range, generator, queryset
    return [str(v) for v in value]


class FUGATrends:
    """
    Wrapper for FUGA Trends endpoints.

    - fetch_chart:  GET /trends/chart
      "Get amount of downloads or streams for a selection type split by day"
      Requires: selection_type, sale_type, start_date, end_date

    - fetch_totals: GET /trends/totals
      "Get total streams AND downloads and their performance"
      Requires: selection_type, start_date, end_date (no sale_type)
    """

    _SELECTION_ALLOWED: ClassVar[frozenset[str]] = frozenset(
        {"dsp", "territory", "label", "product", "asset"}
    )
    _SALE_ALLOWED: ClassVar[frozenset[str]] = frozenset({"stream", "download"})

    def __init__(self, client: BaseFUGAClient) -> None:
        self.client = client

    # ----- helpers -----
    def _bad_arg(self, message: str) -> FugaResponse:
        return error_response(message)

    def _validate_selection(self, selection_type: SelectionType) -> FugaResponse | None:
        if selection_type not in self._SELECTION_ALLOWED:
            return self._bad_arg(
                f"selection_type must be one of {sorted(self._SELECTION_ALLOWED)}"
            )
        return None

    def _validate_sale(self, sale_type: SaleType) -> FugaResponse | None:
        if sale_type not in self._SALE_ALLOWED:
            return self._bad_arg(
                f"sale_type must be one of {sorted(self._SALE_ALLOWED)}"
            )
        return None

    @staticmethod
    def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
        """Drop None values and coerce asset_ids to a list if present."""
        out: dict[str, Any] = {}
        for k, v in params.items():
            if v is None:
                continue
            if k == "asset_ids":
                # A list, so `requests` repeats the param
                out[k] = _normalize_asset_ids(v)
            else:
                out[k] = v
        return out

    # ----- /trends/chart -----
    def fetch_chart(
        self,
        selection_type: SelectionType,
        start_date: str,
        end_date: str,
        sale_type: SaleType = "stream",
        *,
        product_id: int | None = None,
        artist_id: int | None = None,
        asset_id: int | None = None,
        asset_ids: Iterable[int | str] | None = None,
        release_project_id: int | None = None,
        territory_id: str | None = None,
        dsp_id: int | None = None,
    ) -> FugaResponse:
        """
        GET /trends/chart

        Returns daily counts for the selection (e.g., per-dsp series) within a date range.
        """
        bad = self._validate_selection(selection_type) or self._validate_sale(sale_type)
        if bad:
            return bad

        params = self._clean_params(
            {
                "selection_type": selection_type,
                "sale_type": sale_type,
                "start_date": start_date,
                "end_date": end_date,
                "product_id": product_id,
                "artist_id": artist_id,
                "asset_id": asset_id,
                "asset_ids": asset_ids,
                "release_project_id": release_project_id,
                "territory_id": territory_id,
                "dsp_id": dsp_id,
            }
        )
        return self.client.get("/trends/chart", params=params)

    # ----- /trends/totals -----
    def fetch_totals(
        self,
        selection_type: str,
        start_date: str,
        end_date: str,
        **filters: Any,
    ) -> FugaResponse:
        """
        GET /trends/totals

        Returns total streams/downloads and performance for a selection type
        within a date range. Accepts optional scope filters. `asset_ids` is
        normalized to a repeated query param (list of strings).
        """
        # Validate enums (same behavior as other endpoints)
        bad = self._validate_selection(selection_type)
        if bad:
            return bad

        # Build params; _clean_params drops Nones and ensures asset_ids is a list[str]
        params = self._clean_params(
            {
                "selection_type": selection_type,
                "start_date": start_date,
                "end_date": end_date,
                # single-id filters
                "product_id": filters.get("product_id"),
                "artist_id": filters.get("artist_id"),
                "asset_id": filters.get("asset_id"),
                "release_project_id": filters.get("release_project_id"),
                "territory_id": filters.get("territory_id"),
                "dsp_id": filters.get("dsp_id"),
                "label_id": filters.get("label_id"),
                # multi-id filter
                "asset_ids": filters.get("asset_ids"),
            }
        )

        return self.client.get("/trends/totals", params=params)

    def trends_files_get(self, params: dict[str, Any] | None = None) -> FugaResponse:
        """
        GET /trends_file_reports
        Fetch trends file reports with optional query parameters.
        params: Optional dictionary of query parameters, including:
            - status (number, optional)
            - dsp_id (number, optional)
            - end_date (string <date>, format: yyyy-mm-dd)
            - export_report_type (string <string>, Enum: "standard", "demographics", "aggregated", "nonstandard", "nonroyalty", "playlists")
            - start_date (string <date>, format: yyyy-mm-dd)
            - updated_since (long integer, epoch timestamp format in milliseconds)
            - id_since (string)
            - page (number, default: 0)
            - size (number, default: 20)
        Returns a dictionary with the API response.
        """
        return self.client.get("/trends_file_reports", params=params)
