from typing import Any

from .api import BaseFUGAClient
from .entity import FUGAEntity, paginate, requires_id
from .response import FugaResponse


class FUGAPublishingHouse(FUGAEntity):
    """Represents a publishing house in the FUGA API."""

    id_field = "publishing_house_id"

    def __init__(
        self, client: BaseFUGAClient, publishing_house_id: str | None = None
    ) -> None:
        super().__init__(client)
        self.publishing_house_id = publishing_house_id

    # ---- list / fetch ----
    def fetch_list(
        self, page: int = 0, page_size: int = 10, limit: int | None = None
    ) -> FugaResponse:
        return paginate(
            self.client,
            "/publishing_houses",
            "publishing_house",
            page=page,
            page_size=page_size,
            limit=limit,
        )

    @requires_id
    def fetch(self) -> FugaResponse:
        return self.client.get(f"/publishing_houses/{self.publishing_house_id}")

    # ---- CRUD ----
    def create(self, data: dict[str, Any]) -> FugaResponse:
        resp = self.client.post("/publishing_houses", data=data)
        if resp["success"]:
            created = resp.get("data") or {}
            if isinstance(created, dict) and "id" in created:
                self.publishing_house_id = created["id"]
        return resp

    @requires_id
    def update(self, data: dict[str, Any]) -> FugaResponse:
        return self.client.put(
            f"/publishing_houses/{self.publishing_house_id}", data=data
        )

    @requires_id
    def delete(self) -> FugaResponse:
        return self.client.delete(f"/publishing_houses/{self.publishing_house_id}")
