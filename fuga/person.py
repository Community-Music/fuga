from typing import Any

from .api import BaseFUGAClient
from .entity import FUGAEntity, paginate, requires_id
from .response import FugaResponse


class FUGAPerson(FUGAEntity):
    """Represents a person in the FUGA API."""

    id_field = "person_id"

    def __init__(self, client: BaseFUGAClient, person_id: str | None = None) -> None:
        super().__init__(client)
        self.person_id = person_id

    # ---- collection ----
    def fetch_list(
        self, page: int = 0, page_size: int = 10, limit: int | None = None
    ) -> FugaResponse:
        return paginate(
            self.client,
            "/people",
            "person",
            page=page,
            page_size=page_size,
            limit=limit,
        )

    # ---- single ----
    @requires_id
    def fetch(self) -> FugaResponse:
        return self.client.get(f"/people/{self.person_id}")

    def create(self, data: dict[str, Any]) -> FugaResponse:
        resp = self.client.post("/people", data=data)
        if resp["success"]:
            created = resp.get("data") or {}
            if isinstance(created, dict) and "id" in created:
                self.person_id = created["id"]
        return resp

    @requires_id
    def update(self, data: dict[str, Any]) -> FugaResponse:
        return self.client.put(f"/people/{self.person_id}", data=data)

    @requires_id
    def delete(self) -> FugaResponse:
        return self.client.delete(f"/people/{self.person_id}")
