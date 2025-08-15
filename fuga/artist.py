# python imports
from typing import Optional, Dict, Any

# local imports
from .api import FUGAClient


class FUGAArtist:
    """
    Represents an artist in the FUGA API.

    Provides methods for CRUD operations and managing artist identifiers.
    """

    def __init__(self, client: FUGAClient, artist_id: Optional[str] = None):
        """
        Initialize the FUGAArtist instance.

        Args:
            client (FUGAClient): The FUGA API client.
            artist_id (Optional[str]): The ID of the artist, if available.
        """
        self.client: FUGAClient = client
        self.artist_id: Optional[str] = artist_id

    def _need_id(self) -> Dict[str, Any]:
        return {"success": False, "status_code": None, "error": {"message": "artist_id is required"}}

    def fetch_list(self, page: int = 0, page_size: int = 10, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Return a dict with artists (possibly across multiple pages if limit is set).
        Shape: {"success", "status_code", "data": {"artist": [...], "total": int, ...}} | {"success": False, "error": ...}
        """
        endpoint = "/artists"
        params = {"page": page, "page_size": page_size}

        # Single page if no limit requested
        if not limit:
            return self.client.get(endpoint, params=params)

        # Aggregate up to `limit` across pages (still returns one dict)
        collected = []
        last_status = None
        total = None
        pages_fetched = 0

        while True:
            resp = self.client.get(endpoint, params=params)
            last_status = resp.get("status_code")

            if not resp.get("success"):
                return resp  # bubble up error as-is

            data = resp.get("data") or {}
            items = data.get("artist") or []
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
                "artist": collected,
                "total": total if total is not None else len(collected),
                "pages_fetched": pages_fetched,
                "limit_applied": bool(limit),
            },
        }


    def fetch(self) -> Dict[str, Any]:
        """Fetch a single artist's details from FUGA."""
        if not self.artist_id:
            return self._need_id()

        resp = self.client.get(f"/artists/{self.artist_id}")
        return resp

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new artist in FUGA. """
        resp = self.client.post("/artists", data=data)

        if resp["success"]:
            created_data = resp.get("data", {})
            if isinstance(created_data, dict) and "id" in created_data:
                self.artist_id = created_data["id"]

        return resp

    def update(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing artist in FUGA."""
        if not self.artist_id:
            return self._need_id()

        return self.client.put(f"/artists/{self.artist_id}", data=data)

    def delete(self) -> Dict[str, Any]:
        """Delete the artist from FUGA."""
        if not self.artist_id:
            return self._need_id()

        return self.client.delete(f"/artists/{self.artist_id}")

    def fetch_identifiers(self) -> Dict[str, Any]:
        """Fetch all identifiers for the artist."""
        if not self.artist_id:
            return self._need_id()
        return self.client.get(f"/artists/{self.artist_id}/identifier")

    def fetch_identifier(self, identifier_id: str) -> Dict[str, Any]:
        """Fetch a specific identifier for the artist."""
        if not self.artist_id:
            return self._need_id()
        return self.client.get(f"/artists/{self.artist_id}/identifier/{identifier_id}")

    def create_identifier(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new identifier for the artist."""
        if not self.artist_id:
            return self._need_id()
        return self.client.post(f"/artists/{self.artist_id}/identifier", data=data)

    def update_identifier(self, identifier_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing identifier for the artist."""
        if not self.artist_id:
            return self._need_id()
        return self.client.put(f"/artists/{self.artist_id}/identifier/{identifier_id}", data=data)

    def delete_identifier(self, identifier_id: str) -> Dict[str, Any]:
        """Delete a specific identifier for the artist."""
        if not self.artist_id:
            return self._need_id()
        return self.client.delete(f"/artists/{self.artist_id}/identifier/{identifier_id}")