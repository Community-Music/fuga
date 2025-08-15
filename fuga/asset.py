from typing import Optional, Dict, Any
from .api import FUGAClient


class FUGAAsset:
    """
    Represents an asset in the FUGA API.

    Provides methods for CRUD operations and managing related resources
    like contributors, instrument performers, publishers, and media uploads.
    """

    def __init__(self, client: FUGAClient, asset_id: Optional[str] = None):
        self.client = client
        self.asset_id = asset_id

    def _need_id(self) -> Dict[str, Any]:
        return {
            "success": False,
            "status_code": None,
            "error": {"message": "asset_id is required"},
        }

    # --- list/fetch ---
    def fetch_list(
        self, page: int = 0, page_size: int = 10, limit: Optional[int] = None
    ) -> Dict[str, Any]:
        endpoint = "/assets"
        params = {"page": page, "page_size": page_size}

        if not limit:
            return self.client.get(endpoint, params=params)

        collected, last_status, total, pages_fetched = [], None, None, 0

        while True:
            resp = self.client.get(endpoint, params=params)
            last_status = resp.get("status_code")

            if not resp.get("success"):
                return resp

            data = resp.get("data") or {}
            items = data.get("asset") or []
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
                "asset": collected,
                "total": total if total is not None else len(collected),
                "pages_fetched": pages_fetched,
                "limit_applied": bool(limit),
            },
        }

    def fetch(self) -> Dict[str, Any]:
        if not self.asset_id:
            return self._need_id()
        return self.client.get(f"/assets/{self.asset_id}")

    # --- crud ---
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        resp = self.client.post("/assets", data=data)
        if resp.get("success"):
            created = resp.get("data") or {}
            if isinstance(created, dict) and "id" in created:
                self.asset_id = created["id"]
        return resp

    def update(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.asset_id:
            return self._need_id()
        return self.client.put(f"/assets/{self.asset_id}", data=data)

    def delete(self) -> Dict[str, Any]:
        if not self.asset_id:
            return self._need_id()
        return self.client.delete(f"/assets/{self.asset_id}")

    # --- roles ---
    def fetch_roles(self) -> Dict[str, Any]:
        if not self.asset_id:
            return self._need_id()
        return self.client.get(f"/assets/{self.asset_id}/contributors")

    def add_role(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.asset_id:
            return self._need_id()
        return self.client.post(f"/assets/{self.asset_id}/contributors", data=data)

    def remove_role(self, contributor_id: str) -> Dict[str, Any]:
        if not self.asset_id:
            return self._need_id()
        return self.client.delete(
            f"/assets/{self.asset_id}/contributors/{contributor_id}"
        )

    # --- instrument performers ---
    def fetch_instrument_performers(self) -> Dict[str, Any]:
        if not self.asset_id:
            return self._need_id()
        return self.client.get(f"/assets/{self.asset_id}/instrument_performers")

    def add_instrument_performer(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.asset_id:
            return self._need_id()
        return self.client.post(
            f"/assets/{self.asset_id}/instrument_performers", data=data
        )

    def remove_instrument_performer(
        self, instrument_performer_id: str
    ) -> Dict[str, Any]:
        if not self.asset_id:
            return self._need_id()
        return self.client.delete(
            f"/assets/{self.asset_id}/instrument_performers/{instrument_performer_id}"
        )

    # --- publishers ---
    def fetch_publishers(self) -> Dict[str, Any]:
        if not self.asset_id:
            return self._need_id()
        return self.client.get(f"/assets/{self.asset_id}/publishers")

    def add_publisher(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.asset_id:
            return self._need_id()
        return self.client.post(f"/assets/{self.asset_id}/publishers", data=data)

    def remove_publisher(self, publisher_id: str) -> Dict[str, Any]:
        if not self.asset_id:
            return self._need_id()
        return self.client.delete(f"/assets/{self.asset_id}/publishers/{publisher_id}")

    # --- media ---
    def fetch_audio(self, original: bool = True) -> Dict[str, Any]:
        if not self.asset_id:
            return self._need_id()
        return self.client.get_binary(
            f"/assets/{self.asset_id}/audio", params={"original": original}
        )

    def upload_audio(
        self, audio_path: str, is_apple_digital_master: bool = False
    ) -> Dict[str, Any]:
        if not self.asset_id:
            return self._need_id()
        data = {
            "id": self.asset_id,
            "type": "audio",
            "overwrite_all": True,
            "clear_all_encodings": True,
        }
        if is_apple_digital_master:
            data["original_encoding"] = "ADM"
        return self.client.upload_file(audio_path, data)

    def upload_video(self, video_path: str) -> Dict[str, Any]:
        if not self.asset_id:
            return self._need_id()
        data = {"id": self.asset_id, "type": "video"}
        # video chunks can be bigger; 6MB is fine (tweak if needed)
        return self.client.upload_file(video_path, data, chunk_size=6 * 1024 * 1024)

    def upload_video_preview_image(
        self, video_preview_image_id: str, image_path: str
    ) -> Dict[str, Any]:
        if not self.asset_id:
            return self._need_id()
        data = {"id": video_preview_image_id, "type": "image_preview_image"}
        return self.client.upload_file(image_path, data)
