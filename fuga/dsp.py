from .api import BaseFUGAClient
from .entity import v3_only
from .response import FugaResponse


class FUGADSP:
    """The DSPs FUGA can deliver to. FUGA API v3 only."""

    def __init__(self, client: BaseFUGAClient) -> None:
        self.client = client

    @v3_only
    def fetch_list(self, delivery_capability: str | None = None) -> FugaResponse:
        """
        Every DSP the organisation can deliver to, as one unpaged list. With a
        `delivery_capability`, such as "ARTIST_IDENTIFIER", only the DSPs that
        support it.
        """
        params = (
            {"delivery_capability": delivery_capability}
            if delivery_capability
            else None
        )
        return self.client.get("/dsps", params=params)
