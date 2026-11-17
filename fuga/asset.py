from typing import Any

from .api import BaseFUGAClient
from .entity import FUGAEntity, paginate, requires_id
from .response import FugaResponse


class FUGAAsset(FUGAEntity):
    """
    Represents an asset in the FUGA API.

    Provides methods for CRUD operations and managing related resources
    like contributors, publishers, and media uploads.
    """

    id_field = "asset_id"

    def __init__(self, client: BaseFUGAClient, asset_id: str | None = None) -> None:
        super().__init__(client)
        self.asset_id = asset_id

    # --- list/fetch ---
    def fetch_list(
        self, page: int = 0, page_size: int = 10, limit: int | None = None
    ) -> FugaResponse:
        return paginate(
            self.client, "/assets", "asset", page=page, page_size=page_size, limit=limit
        )

    @requires_id
    def fetch(self) -> FugaResponse:
        return self.client.get(f"/assets/{self.asset_id}")

    # --- crud ---
    def create(self, data: dict[str, Any]) -> FugaResponse:
        resp = self.client.post("/assets", data=data)
        if not resp["success"]:
            return resp

        payload = resp.get("data")
        asset_id = None
        if isinstance(payload, dict):
            if payload.get("id"):
                asset_id = payload["id"]
            elif isinstance(payload.get("asset"), dict) and payload["asset"].get("id"):
                asset_id = payload["asset"]["id"]
            elif isinstance(payload.get("asset"), list) and payload["asset"]:
                first = payload["asset"][0]
                if isinstance(first, dict) and first.get("id"):
                    asset_id = first["id"]

        if asset_id:
            self.asset_id = asset_id
        return resp

    @requires_id
    def update(self, data: dict[str, Any]) -> FugaResponse:
        return self.client.put(f"/assets/{self.asset_id}", data=data)

    @requires_id("product_id")
    def attach_to_product(self, product_id: str, data: dict[str, Any]) -> FugaResponse:
        return self.client.put(
            f"/products/{product_id}/assets/{self.asset_id}", data=data
        )

    @requires_id
    def delete(self) -> FugaResponse:
        return self.client.delete(f"/assets/{self.asset_id}")

    # --- contributors: one entry per person, {person_id, roles, instruments} ---
    @requires_id
    def fetch_contributors(self) -> FugaResponse:
        return self.client.get(f"/assets/{self.asset_id}/contributors")

    @requires_id
    def replace_contributors(self, contributors: list[dict[str, Any]]) -> FugaResponse:
        """Replaces the whole list; anyone left out is removed, so [] clears it."""
        return self.client.put(
            f"/assets/{self.asset_id}/contributors", data=contributors
        )

    @requires_id
    def save_contributor(self, data: dict[str, Any]) -> FugaResponse:
        """Adds the person in `data`, or replaces their roles and instruments."""
        return self.client.post(f"/assets/{self.asset_id}/contributors", data=data)

    @requires_id("person_id")
    def fetch_contributor(self, person_id: str) -> FugaResponse:
        return self.client.get(f"/assets/{self.asset_id}/contributors/{person_id}")

    @requires_id("person_id")
    def remove_contributor(self, person_id: str) -> FugaResponse:
        return self.client.delete(f"/assets/{self.asset_id}/contributors/{person_id}")

    # --- publishers ---
    @requires_id
    def fetch_publishers(self) -> FugaResponse:
        return self.client.get(f"/assets/{self.asset_id}/publishers")

    @requires_id
    def add_publisher(self, data: dict[str, Any]) -> FugaResponse:
        return self.client.post(f"/assets/{self.asset_id}/publishers", data=data)

    @requires_id("publisher_id")
    def remove_publisher(self, publisher_id: str) -> FugaResponse:
        return self.client.delete(f"/assets/{self.asset_id}/publishers/{publisher_id}")

    # --- media ---
    @requires_id
    def fetch_audio(self, original: bool = True) -> FugaResponse:
        return self.client.get_binary(
            f"/assets/{self.asset_id}/audio", params={"original": original}
        )

    @requires_id
    def upload_audio(
        self, audio_path: str, is_apple_digital_master: bool = False
    ) -> FugaResponse:
        data = {
            "id": self.asset_id,
            "type": "audio",
            "overwrite_all": True,
            "clear_all_encodings": True,
        }
        if is_apple_digital_master:
            data["original_encoding"] = "ADM"
        return self.client.upload_file(audio_path, data)

    @requires_id
    def upload_video(self, video_path: str) -> FugaResponse:
        data = {"id": self.asset_id, "type": "video"}
        # video chunks can be bigger; 6MB is fine (tweak if needed)
        return self.client.upload_file(video_path, data, chunk_size=6 * 1024 * 1024)

    @requires_id
    def upload_video_preview_image(
        self, video_preview_image_id: str, image_path: str
    ) -> FugaResponse:
        data = {"id": video_preview_image_id, "type": "image_preview_image"}
        return self.client.upload_file(image_path, data)
