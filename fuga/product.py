from typing import Any

from .api import BaseFUGAClient
from .entity import FUGAEntity, paginate, requires_id
from .response import FugaResponse


class FUGAProduct(FUGAEntity):
    """Represents a product in the FUGA API."""

    id_field = "product_id"

    def __init__(self, client: BaseFUGAClient, product_id: str | None = None) -> None:
        super().__init__(client)
        self.product_id = product_id

    # ---- list / fetch ----
    def fetch_list(
        self, page: int = 0, page_size: int = 10, limit: int | None = None
    ) -> FugaResponse:
        return paginate(
            self.client,
            "/products",
            "product",
            page=page,
            page_size=page_size,
            limit=limit,
        )

    @requires_id
    def fetch(self) -> FugaResponse:
        return self.client.get(f"/products/{self.product_id}")

    # ---- CRUD ----
    def create(self, data: dict[str, Any]) -> FugaResponse:
        resp = self.client.post("/products", data=data)
        if resp["success"]:
            created = resp.get("data") or {}
            if isinstance(created, dict) and "id" in created:
                self.product_id = created["id"]
        return resp

    @requires_id
    def update(self, data: dict[str, Any]) -> FugaResponse:
        return self.client.put(f"/products/{self.product_id}", data=data)

    @requires_id
    def delete(self) -> FugaResponse:
        return self.client.delete(f"/products/{self.product_id}")

    # ---- actions ----
    @requires_id
    def publish(self) -> FugaResponse:
        return self.client.post(f"/products/{self.product_id}/publish")

    @requires_id
    def assign_barcode(self) -> FugaResponse:
        return self.client.post(f"/products/{self.product_id}/barcode")

    # ---- product media/metadata ----
    @requires_id
    def fetch_image(self, size: str = "full_size") -> FugaResponse:
        return self.client.get_binary(f"/products/{self.product_id}/image/{size}")

    @requires_id
    def fetch_artworks(self) -> FugaResponse:
        return self.client.get(f"/products/{self.product_id}/artworks")

    @requires_id
    def fetch_live_links(self) -> FugaResponse:
        return self.client.get(f"/products/{self.product_id}/live_links")

    @requires_id
    def update_territories(self, territories: list[str]) -> FugaResponse:
        return self.client.put(
            f"/products/{self.product_id}/territories", data=territories
        )

    # ---- tracks / assets on a product ----
    @requires_id
    def fetch_assets(self) -> FugaResponse:
        return self.client.get(f"/products/{self.product_id}/assets")

    @requires_id
    def add_asset(self, asset_id: str, sequence: int) -> FugaResponse:
        return self.client.post(
            f"/products/{self.product_id}/assets",
            data={"id": asset_id, "sequence": sequence},
        )

    @requires_id("asset_id")
    def remove_asset(self, asset_id: str) -> FugaResponse:
        return self.client.delete(f"/products/{self.product_id}/assets/{asset_id}")

    @requires_id("asset_id")
    def update_asset_sequence(self, asset_id: str, sequence: int) -> FugaResponse:
        endpoint = f"/products/{self.product_id}/assets/{asset_id}/position/{sequence}"
        return self.client.put(endpoint, data={})

    # ---- uploads ----
    @requires_id
    def upload_cover_image(self, entity_id: str, image_path: str) -> FugaResponse:
        data = {"id": entity_id, "type": "image"}
        return self.client.upload_file(image_path, data)
