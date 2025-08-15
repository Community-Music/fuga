from typing import Optional, Dict, Any
from .api import FUGAClient  # adjust if your client module is named differently


class FUGALabel:
    """
    Represents a label in the FUGA API.
    Always returns dicts shaped like the client: {"success", "status_code", "data"? | "error"?}
    """

    def __init__(self, client: FUGAClient, label_id: Optional[str] = None):
        self.client = client
        self.label_id = label_id

    def _need_id(self) -> Dict[str, Any]:
        return {
            "success": False,
            "status_code": None,
            "error": {"message": "label_id is required"},
        }

    # ---- list / fetch ----
    def fetch_list(
        self, page: int = 0, page_size: int = 10, limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Return a dict with labels (optionally aggregated across pages up to `limit`).
        Success shape: {"success": True, "status_code": int, "data": {"label": [...], "total": int, ...}}
        """
        endpoint = "/labels"
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
            items = data.get("label") or []
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
                "label": collected,
                "total": total if total is not None else len(collected),
                "pages_fetched": pages_fetched,
                "limit_applied": bool(limit),
            },
        }

    def fetch(self) -> Dict[str, Any]:
        if not self.label_id:
            return self._need_id()
        return self.client.get(f"/labels/{self.label_id}")

    # ---- CRUD ----
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = self.client.post("/labels", data=data)
        if resp.get("success"):
            created = resp.get("data") or {}
            if isinstance(created, dict) and "id" in created:
                self.label_id = created["id"]
        return resp

    def update(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.label_id:
            return self._need_id()
        return self.client.put(f"/labels/{self.label_id}", data=data)

    def delete(self) -> Dict[str, Any]:
        if not self.label_id:
            return self._need_id()
        return self.client.delete(f"/labels/{self.label_id}")
