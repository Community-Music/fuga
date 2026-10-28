from typing import Any

from .api import BaseFUGAClient
from .entity import FUGAEntity, paginate, requires_id
from .response import FugaResponse


class FUGALabel(FUGAEntity):
    """Represents a label in the FUGA API."""

    id_field = "label_id"

    def __init__(self, client: BaseFUGAClient, label_id: str | None = None) -> None:
        super().__init__(client)
        self.label_id = label_id

    # ---- list / fetch ----
    def fetch_list(
        self, page: int = 0, page_size: int = 10, limit: int | None = None
    ) -> FugaResponse:
        return paginate(
            self.client, "/labels", "label", page=page, page_size=page_size, limit=limit
        )

    @requires_id
    def fetch(self) -> FugaResponse:
        return self.client.get(f"/labels/{self.label_id}")

    # ---- CRUD ----
    def create(self, data: dict[str, Any]) -> FugaResponse:
        resp = self.client.post("/labels", data=data)
        if resp["success"]:
            created = resp.get("data") or {}
            if isinstance(created, dict) and "id" in created:
                self.label_id = created["id"]
        return resp

    @requires_id
    def update(self, data: dict[str, Any]) -> FugaResponse:
        return self.client.put(f"/labels/{self.label_id}", data=data)

    @requires_id
    def delete(self) -> FugaResponse:
        return self.client.delete(f"/labels/{self.label_id}")
