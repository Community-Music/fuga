from typing import Optional, Dict, Any
from .api import FUGAClient  # adjust if your client lives elsewhere


class FUGAPublishingHouse:
    """
    Represents a publishing house in the FUGA API.
    Always returns dicts shaped like the client: {"success", "status_code", "data"? | "error"?}
    """

    def __init__(self, client: FUGAClient, publishing_house_id: Optional[str] = None):
        self.client = client
        self.publishing_house_id = publishing_house_id

    def _need_id(self) -> Dict[str, Any]:
        return {
            "success": False,
            "status_code": None,
            "error": {"message": "publishing_house_id is required"},
        }

    # ---- list / fetch ----
    def fetch_list(
        self, page: int = 0, page_size: int = 10, limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Return a dict with publishing houses (optionally aggregated across pages up to `limit`).
        Success shape: {"success": True, "status_code": int, "data": {"publishing_house": [...], "total": int, ...}}
        """
        endpoint = "/publishing_houses"
        params = {"page": page, "page_size": page_size}

        if not limit:
            return self.client.get(endpoint, params=params)

        collected = []
        last_status = None
        total = None
        pages_fetched = 0

        while True:
            resp = self.client.get(endpoint, params=params)
            last_status = resp.get("status_code")

            if not resp.get("success"):
                return resp

            data = resp.get("data") or {}
            items = data.get("publishing_house") or []
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
                "publishing_house": collected,
                "total": total if total is not None else len(collected),
                "pages_fetched": pages_fetched,
                "limit_applied": bool(limit),
            },
        }

    def fetch(self) -> Dict[str, Any]:
        if not self.publishing_house_id:
            return self._need_id()
        return self.client.get(f"/publishing_houses/{self.publishing_house_id}")

    # ---- CRUD ----
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = self.client.post("/publishing_houses", data=data)
        if resp.get("success"):
            created = resp.get("data") or {}
            if isinstance(created, dict) and "id" in created:
                self.publishing_house_id = created["id"]
        return resp

    def update(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.publishing_house_id:
            return self._need_id()
        return self.client.put(
            f"/publishing_houses/{self.publishing_house_id}", data=data
        )

    def delete(self) -> Dict[str, Any]:
        if not self.publishing_house_id:
            return self._need_id()
        return self.client.delete(f"/publishing_houses/{self.publishing_house_id}")
