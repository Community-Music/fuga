from typing import Any

from .api import BaseFUGAClient
from .entity import FUGAEntity, paginate, requires_id
from .response import FugaResponse


class FUGAArtist(FUGAEntity):
    """
    Represents an artist in the FUGA API.

    Provides methods for CRUD operations and managing artist identifiers.
    """

    id_field = "artist_id"

    def __init__(self, client: BaseFUGAClient, artist_id: str | None = None) -> None:
        super().__init__(client)
        self.artist_id = artist_id

    def fetch_list(
        self, page: int = 0, page_size: int = 10, limit: int | None = None
    ) -> FugaResponse:
        return paginate(
            self.client,
            "/artists",
            "artist",
            page=page,
            page_size=page_size,
            limit=limit,
        )

    @requires_id
    def fetch(self) -> FugaResponse:
        """Fetch a single artist's details from FUGA."""
        return self.client.get(f"/artists/{self.artist_id}")

    def create(self, data: dict[str, Any]) -> FugaResponse:
        """Create a new artist in FUGA."""
        resp = self.client.post("/artists", data=data)

        if resp["success"]:
            created_data = resp.get("data", {})
            if isinstance(created_data, dict) and "id" in created_data:
                self.artist_id = created_data["id"]

        return resp

    @requires_id
    def update(self, data: dict[str, Any]) -> FugaResponse:
        """Update an existing artist in FUGA."""
        return self.client.put(f"/artists/{self.artist_id}", data=data)

    @requires_id
    def delete(self) -> FugaResponse:
        """Delete the artist from FUGA."""
        return self.client.delete(f"/artists/{self.artist_id}")

    @requires_id
    def fetch_identifiers(self) -> FugaResponse:
        """Fetch all identifiers for the artist."""
        return self.client.get(f"/artists/{self.artist_id}/identifier")

    @requires_id("identifier_id")
    def fetch_identifier(self, identifier_id: str) -> FugaResponse:
        """Fetch a specific identifier for the artist."""
        return self.client.get(f"/artists/{self.artist_id}/identifier/{identifier_id}")

    @requires_id
    def create_identifier(self, data: dict[str, Any]) -> FugaResponse:
        """Create a new identifier for the artist."""
        return self.client.post(f"/artists/{self.artist_id}/identifier", data=data)

    @requires_id("identifier_id")
    def update_identifier(
        self, identifier_id: str, data: dict[str, Any]
    ) -> FugaResponse:
        """Update an existing identifier for the artist."""
        return self.client.put(
            f"/artists/{self.artist_id}/identifier/{identifier_id}", data=data
        )

    @requires_id("identifier_id")
    def delete_identifier(self, identifier_id: str) -> FugaResponse:
        """Delete a specific identifier for the artist."""
        return self.client.delete(
            f"/artists/{self.artist_id}/identifier/{identifier_id}"
        )
