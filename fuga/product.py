from typing import Optional, Dict, Any, List
from .api import FUGAClient


class FUGAProduct:
    """
    Represents a product in the FUGA API.
    Always returns dicts like the client: {"success", "status_code", "data"? | "error"?}
    """

    def __init__(self, client: FUGAClient, product_id: Optional[str] = None):
        self.client = client
        self.product_id = product_id

    def _need_id(self) -> Dict[str, Any]:
        return {"success": False, "status_code": None, "error": {"message": "product_id is required"}}

    # ---- list / fetch ----
    def fetch_list(self, page: int = 0, page_size: int = 10, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Return a dict with products (optionally aggregated across pages up to `limit`).
        Success shape: {"success": True, "status_code": int, "data": {"product": [...], "total": int, ...}}
        """
        endpoint = "/products"
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

    def fetch(self) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.get(f"/products/{self.product_id}")

    # ---- CRUD ----
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = self.client.post("/products", data=data)
        if resp.get("success"):
            created = resp.get("data") or {}
            if isinstance(created, dict) and "id" in created:
                self.product_id = created["id"]
        return resp

    def update(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.put(f"/products/{self.product_id}", data=data)

    def delete(self) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.delete(f"/products/{self.product_id}")

    # ---- actions ----
    def publish(self) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.post(f"/products/{self.product_id}/publish")

    def assign_barcode(self) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.post(f"/products/{self.product_id}/barcode")

    # ---- product media/metadata ----
    def fetch_image(self, size: str = "full_size") -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.get_binary(f"/products/{self.product_id}/image/{size}")

    def fetch_artworks(self) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.get(f"/products/{self.product_id}/artworks")

    def fetch_live_links(self) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.get(f"/products/{self.product_id}/live_links")

    def update_territories(self, territories: List[str]) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        # Assuming FUGA expects the raw list (per your original implementation)
        return self.client.put(f"/products/{self.product_id}/territories", data=territories)

    # ---- tracks / assets on a product ----
    def fetch_assets(self) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.get(f"/products/{self.product_id}/assets")

    def add_asset(self, asset_id: str, sequence: int) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.post(
            f"/products/{self.product_id}/assets",
            data={"id": asset_id, "sequence": sequence},
        )

    def remove_asset(self, asset_id: str) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.delete(f"/products/{self.product_id}/assets/{asset_id}")

    def update_asset_sequence(self, asset_id: str, sequence: int) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        endpoint = f"/products/{self.product_id}/assets/{asset_id}/position/{sequence}"
        return self.client.put(endpoint, data={})

    # ---- uploads ----
    def upload_cover_image(self, entity_id: str, image_path: str) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        data = {"id": entity_id, "type": "image"}
        return self.client.upload_file(image_path, data)
