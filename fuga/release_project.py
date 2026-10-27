from typing import Any

from .api import BaseFUGAClient
from .entity import FUGAEntity, paginate, requires_id
from .response import FugaResponse


class FUGAReleaseProject(FUGAEntity):
    """Represents a release project in the FUGA API."""

    id_field = "release_project_id"

    def __init__(
        self, client: BaseFUGAClient, release_project_id: str | None = None
    ) -> None:
        super().__init__(client)
        self.release_project_id = release_project_id

    # ---- list / fetch ----
    def fetch_list(
        self, page: int = 0, page_size: int = 10, limit: int | None = None
    ) -> FugaResponse:
        return paginate(
            self.client,
            "/release_projects",
            "release_project",
            page=page,
            page_size=page_size,
            limit=limit,
        )

    @requires_id
    def fetch(self) -> FugaResponse:
        return self.client.get(f"/release_projects/{self.release_project_id}")

    # ---- CRUD ----
    def create(self, data: dict[str, Any]) -> FugaResponse:
        resp = self.client.post("/release_projects", data=data)
        if resp["success"]:
            created = resp.get("data") or {}
            if isinstance(created, dict) and "id" in created:
                self.release_project_id = created["id"]
        return resp

    @requires_id
    def update(self, data: dict[str, Any]) -> FugaResponse:
        return self.client.put(
            f"/release_projects/{self.release_project_id}", data=data
        )

    @requires_id
    def delete(self) -> FugaResponse:
        return self.client.delete(f"/release_projects/{self.release_project_id}")

    # ---- products on a release project ----
    @requires_id
    def fetch_products(
        self, page: int = 0, page_size: int = 10, limit: int | None = None
    ) -> FugaResponse:
        return paginate(
            self.client,
            f"/release_projects/{self.release_project_id}/products",
            "product",
            page=page,
            page_size=page_size,
            limit=limit,
        )

    @requires_id
    def add_products(self, product_ids: list[str]) -> FugaResponse:
        # FUGA's field name is "products_ids"
        data = {"products_ids": product_ids}
        return self.client.post(
            f"/release_projects/{self.release_project_id}/products", data=data
        )

    @requires_id
    def remove_products(self, product_ids: list[str]) -> FugaResponse:
        data = {"products_ids": product_ids}
        return self.client.delete_json(
            f"/release_projects/{self.release_project_id}/products", data=data
        )
