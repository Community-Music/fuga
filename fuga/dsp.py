from .api import BaseFUGAClient
from .response import FugaResponse


class FUGADSP:
    """The DSPs FUGA can deliver to."""

    def __init__(self, client: BaseFUGAClient) -> None:
        self.client = client

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
