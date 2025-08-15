from typing import Optional, Dict, Any, List
from .api import FUGAClient  # adjust if your client module is named differently


class FUGAReleaseProject:
    """
    Represents a release project in the FUGA API.
    Always returns dicts like the client: {"success", "status_code", "data"? | "error"?}
    """

    def __init__(self, client: FUGAClient, release_project_id: Optional[str] = None):
        self.client = client
        self.release_project_id = release_project_id

    def _need_id(self) -> Dict[str, Any]:
        return {"success": False, "status_code": None, "error": {"message": "release_project_id is required"}}

    # ---- list / fetch ----
    def fetch_list(self, page: int = 0, page_size: int = 10, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Return a dict with release projects (optionally aggregated across pages up to `limit`).
        Success shape: {"success": True, "status_code": int, "data": {"release_project": [...], "total": int, ...}}
        """
        endpoint = "/release_projects"
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
                return resp

            data = resp.get("data") or {}
            items = data.get("release_project") or []
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
                "release_project": collected,
                "total": total if total is not None else len(collected),
                "pages_fetched": pages_fetched,
                "limit_applied": bool(limit),
            },
        }

    def fetch(self) -> Dict[str, Any]:
        if not self.release_project_id:
            return self._need_id()
        return self.client.get(f"/release_projects/{self.release_project_id}")

    # ---- CRUD ----
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = self.client.post("/release_projects", data=data)
        if resp.get("success"):
            created = resp.get("data") or {}
            if isinstance(created, dict) and "id" in created:
                self.release_project_id = created["id"]
        return resp

    def update(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.release_project_id:
            return self._need_id()
        return self.client.put(f"/release_projects/{self.release_project_id}", data=data)

    def delete(self) -> Dict[str, Any]:
        if not self.release_project_id:
            return self._need_id()
        return self.client.delete(f"/release_projects/{self.release_project_id}")

    # ---- products on a release project ----
    def fetch_products(self, page: int = 0, page_size: int = 10, limit: Optional[int] = None) -> Dict[str, Any]:
        if not self.release_project_id:
            return self._need_id()

        endpoint = f"/release_projects/{self.release_project_id}/products"
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
                return resp

            data = resp.get("data") or {}
            items = data.get("product") or []
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
                "product": collected,
                "total": total if total is not None else len(collected),
                "pages_fetched": pages_fetched,
                "limit_applied": bool(limit),
            },
        }

    def add_products(self, product_ids: List[str]) -> Dict[str, Any]:
        if not self.release_project_id:
            return self._need_id()
        # Per your original code, API expects "products_ids"
        data = {"products_ids": product_ids}
        return self.client.post(f"/release_projects/{self.release_project_id}/products", data=data)

    def remove_products(self, product_ids: List[str]) -> Dict[str, Any]:
        if not self.release_project_id:
            return self._need_id()
        # Many APIs accept a JSON body with DELETE. If FUGA does, add a tiny helper on the client:
        # def delete_json(self, endpoint, data=None): return self._request("DELETE", endpoint, json=data)
        data = {"products_ids": product_ids}
        return self.client.delete_json(f"/release_projects/{self.release_project_id}/products", data=data)