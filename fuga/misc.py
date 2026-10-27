from typing import Any

from .api import BaseFUGAClient
from .entity import paginate
from .response import FugaResponse


class FUGAMisc:
    """Thin wrapper for miscellaneous FUGA endpoints."""

    def __init__(self, client: BaseFUGAClient) -> None:
        self.client = client

    # ---- genres / subgenres ----
    def fetch_genres(self) -> FugaResponse:
        return self.client.get("/miscellaneous/genres")

    def fetch_subgenres(
        self,
        page: int = 0,
        page_size: int = 50,
        limit: int | None = None,
    ) -> FugaResponse:
        """Every subgenre from `page` onwards, or the first `limit` of them."""
        return paginate(
            self.client,
            "/miscellaneous/subgenres",
            "subgenre",
            page=page,
            page_size=page_size,
            limit=limit,
            every_page=True,
        )

    def create_subgenre(self, subgenre_data: dict[str, Any]) -> FugaResponse:
        return self.client.post("/miscellaneous/subgenres", data=subgenre_data)

    def delete_subgenre(self, subgenre_id: str) -> FugaResponse:
        return self.client.delete(f"/miscellaneous/subgenres/{subgenre_id}")

    # ---- simple lookups ----
    def fetch_languages(self) -> FugaResponse:
        return self.client.get("/miscellaneous/languages")

    def fetch_audio_locales(self) -> FugaResponse:
        return self.client.get("/miscellaneous/audio_locales")

    def fetch_contributor_roles(self) -> FugaResponse:
        return self.client.get("/miscellaneous/contributor_roles")

    def fetch_catalog_tiers(self) -> FugaResponse:
        return self.client.get("/miscellaneous/catalog-tiers")

    def fetch_instruments(self) -> FugaResponse:
        return self.client.get("/miscellaneous/instruments")

    def fetch_territories(self) -> FugaResponse:
        return self.client.get("/miscellaneous/territories")

    def fetch_encodings(self) -> FugaResponse:
        return self.client.get("/miscellaneous/encodings")

    def fetch_lead_times(self) -> FugaResponse:
        return self.client.get("/miscellaneous/lead_times")
