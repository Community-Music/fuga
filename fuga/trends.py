from typing import Optional, Dict, Any, List, Iterable, Union
from .api import FUGAClient


SelectionType = str  # "dsp" | "territory" | "label" | "product" | "asset"
SaleType = str  # "stream" | "download"


def _normalize_asset_ids(value: Union[None, str, int, Iterable[Union[str, int]]]):
    if value is None:
        return None
    if isinstance(value, (str, int)):
        return [str(value)]
    # list/tuple/set etc.
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

    - fetch_entities: GET /trends
      "Get entities that have trends in a range (and their counts/performance)"
      Requires: selection_type, sale_type, start_date, end_date
      Supports offset/size pagination; optional `limit` to aggregate results.
    """

    _SELECTION_ALLOWED = {"dsp", "territory", "label", "product", "asset"}
    _SALE_ALLOWED = {"stream", "download"}

    def __init__(self, client: FUGAClient):
        self.client = client

    # ----- helpers -----
    def _bad_arg(self, message: str) -> Dict[str, Any]:
        return {"success": False, "status_code": None, "error": {"message": message}}

    def _validate_selection(
        self, selection_type: SelectionType
    ) -> Optional[Dict[str, Any]]:
        if selection_type not in self._SELECTION_ALLOWED:
            return self._bad_arg(
                f"selection_type must be one of {sorted(self._SELECTION_ALLOWED)}"
            )
        return None

    def _validate_sale(self, sale_type: SaleType) -> Optional[Dict[str, Any]]:
        if sale_type not in self._SALE_ALLOWED:
            return self._bad_arg(
                f"sale_type must be one of {sorted(self._SALE_ALLOWED)}"
            )
        return None

    @staticmethod
    def _clean_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """Drop None values and coerce asset_ids to a list if present."""
        out: Dict[str, Any] = {}
        for k, v in params.items():
            if v is None:
                continue
            if k == "asset_ids":
                # Accept anything iterable (list/tuple/set), keep as list so `requests` repeats the param.
                if isinstance(v, (list, tuple, set)):
                    out[k] = [str(x) for x in v]
                else:
                    # single value fallback
                    out[k] = [str(v)]
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
        product_id: Optional[int] = None,
        artist_id: Optional[int] = None,
        asset_id: Optional[int] = None,
        asset_ids: Optional[Iterable[Union[int, str]]] = None,
        release_project_id: Optional[int] = None,
        territory_id: Optional[str] = None,
        dsp_id: Optional[int] = None,
    ) -> Dict[str, Any]:
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
    ) -> Dict[str, Any]:
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

    # ----- /trends (entities with pagination: offset/size) -----
    def fetch_entities(
        self,
        selection_type: SelectionType,
        start_date: str,
        end_date: str,
        sale_type: SaleType = "stream",
        *,
        offset: int = 0,
        size: int = 10,
        limit: Optional[int] = None,
        product_id: Optional[int] = None,
        artist_id: Optional[int] = None,
        asset_id: Optional[int] = None,
        asset_ids: Optional[Iterable[Union[int, str]]] = None,
        release_project_id: Optional[int] = None,
        territory_id: Optional[str] = None,
        dsp_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        GET /trends

        Returns an array of entities (assets/products/dsps/labels/territories) that have trends,
        including their counts and performance percentages.

        If `limit` is provided, fetches multiple windows using offset/size until `limit` items collected.
        Aggregated success payload shape:
          {"success": True, "status_code": <last_code>, "data": {"items": [...], "windows_fetched": N, "limit_applied": True/False}}
        """
        bad = self._validate_selection(selection_type) or self._validate_sale(sale_type)
        if bad:
            return bad

        base_params = self._clean_params(
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

        # Single window (no aggregation)
        if limit is None:
            params = {**base_params, "offset": offset, "size": size}
            return self.client.get("/trends", params=params)

        # Aggregate multiple windows
        collected: List[Dict[str, Any]] = []
        windows = 0
        last_status = None
        cur_offset = int(offset)
        sz = int(size) if size and size > 0 else 10

        while True:
            params = {**base_params, "offset": cur_offset, "size": sz}
            resp = self.client.get("/trends", params=params)
            last_status = resp.get("status_code")

            if not resp.get("success"):
                return resp

            payload = resp.get("data")
            # API says the response is an *array* of entries; be flexible just in case
            if isinstance(payload, list):
                items = payload
            elif (
                isinstance(payload, dict)
                and "data" in payload
                and isinstance(payload["data"], list)
            ):
                items = payload["data"]
            else:
                items = []

            if not items:
                break

            collected.extend(items)
            windows += 1

            if len(collected) >= limit:
                collected = collected[:limit]
                break

            cur_offset += sz

        return {
            "success": True,
            "status_code": last_status,
            "data": {
                "items": collected,
                "windows_fetched": windows,
                "limit_applied": True,
            },
        }
