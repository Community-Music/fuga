# python imports
from typing import Optional, Dict, Any, List

# local imports
from .api import FUGAClient


class FUGAMisc:
    """
    Thin wrapper for miscellaneous FUGA endpoints.
    Always returns dicts like the client: {"success", "status_code", "data"? | "error"?}
    """

    def __init__(self, client: FUGAClient):
        self.client = client

    # ---- genres / subgenres ----
    def fetch_genres(self) -> Dict[str, Any]:
        return self.client.get("/miscellaneous/genres")

    def fetch_subgenres(
        self,
        page: int = 0,
        page_size: int = 50,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Return a dict with subgenres (optionally aggregated across pages up to `limit`).
        Success shape: {"success": True, "status_code": int, "data": {"subgenre": [...], "total": int, ...}}
        """
        endpoint = "/miscellaneous/subgenres"
        params = {"page": page, "page_size": page_size}

        if not limit:
            return self.client.get(endpoint, params=params)

        collected: List[Dict[str, Any]] = []
        last_status = None
        total = None
        pages_fetched = 0

        while True:
            resp = self.client.get(endpoint, params=params)
            last_status = resp.get("status_code")

            if not resp.get("success"):
                return resp  # bubble up error

            data = resp.get("data") or {}
            items = data.get("subgenre") or []
            total = data.get("total", total)

            collected.extend(items)
            pages_fetched += 1

            if limit and len(collected) >= limit:
                collected = collected[:limit]
                break

            if not items or (total is not None and len(collected) >= total):
                break

            params["page"] += 1

        return {
            "success": True,
            "status_code": last_status,
            "data": {
                "subgenre": collected,
                "total": total if total is not None else len(collected),
                "pages_fetched": pages_fetched,
                "limit_applied": bool(limit),
            },
        }

    def create_subgenre(self, subgenre_data: Dict[str, Any]) -> Dict[str, Any]:
        return self.client.post("/miscellaneous/subgenres", data=subgenre_data)

    def delete_subgenre(self, subgenre_id: str) -> Dict[str, Any]:
        return self.client.delete(f"/miscellaneous/subgenres/{subgenre_id}")

    # ---- simple lookups ----
    def fetch_languages(self) -> Dict[str, Any]:
        return self.client.get("/miscellaneous/languages")

    def fetch_audio_locales(self) -> Dict[str, Any]:
        return self.client.get("/miscellaneous/audio_locales")

    def fetch_contributor_roles(self) -> Dict[str, Any]:
        return self.client.get("/miscellaneous/contributor_roles")

    def fetch_catalog_tiers(self) -> Dict[str, Any]:
        # Path matches your original (hyphen)
        return self.client.get("/miscellaneous/catalog-tiers")

    def fetch_instruments(self) -> Dict[str, Any]:
        return self.client.get("/miscellaneous/instruments")

    def fetch_territories(self) -> Dict[str, Any]:
        return self.client.get("/miscellaneous/territories")

    def fetch_encodings(self) -> Dict[str, Any]:
        return self.client.get("/miscellaneous/encodings")

    def fetch_lead_times(self) -> Dict[str, Any]:
        return self.client.get("/miscellaneous/lead_times")
