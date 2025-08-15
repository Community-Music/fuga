from typing import Optional, Dict, Any
from .api import FUGAClient


class FUGAPerson:
    """
    Represents a person in the FUGA API.
    Always returns dicts shaped like the client: {"success", "status_code", "data"? | "error"?}
    """

    def __init__(self, client: FUGAClient, person_id: Optional[str] = None):
        self.client = client
        self.person_id = person_id

    def _need_id(self) -> Dict[str, Any]:
        return {
            "success": False,
            "status_code": None,
            "error": {"message": "person_id is required"},
        }

    # ---- collection ----
    def fetch_list(
        self, page: int = 0, page_size: int = 10, limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Return a dict with people (optionally aggregated across pages up to `limit`).
        Success shape: {"success": True, "status_code": int, "data": {"person": [...], "total": int, ...}}
        """
        endpoint = "/people"
        params = {"page": page, "page_size": page_size}

        # Single page
        if not limit:
            return self.client.get(endpoint, params=params)

        # Aggregate up to `limit`
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
            items = data.get("person") or []
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
                "person": collected,
                "total": total if total is not None else len(collected),
                "pages_fetched": pages_fetched,
                "limit_applied": bool(limit),
            },
        }

    # ---- single ----
    def fetch(self) -> Dict[str, Any]:
        if not self.person_id:
            return self._need_id()
        return self.client.get(f"/people/{self.person_id}")

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = self.client.post("/people", data=data)
        if resp.get("success"):
            created = resp.get("data") or {}
            if isinstance(created, dict) and "id" in created:
                self.person_id = created["id"]
        return resp

    def update(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.person_id:
            return self._need_id()
        return self.client.put(f"/people/{self.person_id}", data=data)

    def delete(self) -> Dict[str, Any]:
        if not self.person_id:
            return self._need_id()
        return self.client.delete(f"/people/{self.person_id}")
