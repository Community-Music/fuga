from collections.abc import Iterable
from typing import Any, cast

from .api import BaseFUGAClient
from .entity import FUGAEntity, requires_id
from .response import FugaResponse

DspArg = int | str | dict[str, Any]
DspsArg = DspArg | Iterable[DspArg]


class FUGADeliveryInstructions(FUGAEntity):
    """
    Wrapper for FUGA delivery instructions endpoints, scoped to a single product.

    All endpoints live under /products/{product_id}/delivery_instructions.
    """

    id_field = "product_id"

    def __init__(self, client: BaseFUGAClient, product_id: str | None = None) -> None:
        super().__init__(client)
        self.product_id = product_id

    # ---- helpers ----
    @staticmethod
    def _normalize_dsps(dsps: DspsArg) -> list[dict[str, Any]]:
        """
        Accept a single DSP id, a list of ids, or a list of dicts and return
        the list-of-dicts wire format FUGA expects: [{"dsp": <id>}, ...].

        - int / str           -> [{"dsp": <id>}]
        - iterable of ints    -> [{"dsp": id}, ...]
        - iterable of dicts   -> passed through (must already contain "dsp")
        """
        if isinstance(dsps, (int, str)):
            return [{"dsp": dsps}]
        if isinstance(dsps, dict):
            # A single instruction such as {"dsp": 1, ...}, not an iterable of ids
            return [cast(dict[str, Any], dsps)]
        out: list[dict[str, Any]] = []
        for item in dsps:
            if isinstance(item, dict):
                out.append(item)
            else:
                out.append({"dsp": item})
        return out

    def _base(self) -> str:
        return f"/products/{self.product_id}/delivery_instructions"

    # ---- read ----
    @requires_id
    def fetch(self) -> FugaResponse:
        return self.client.get(self._base())

    @requires_id
    def fetch_dsp_history(self, dsp_id: int | str) -> FugaResponse:
        return self.client.get(f"{self._base()}/{dsp_id}/history")

    # ---- reset (collection-root DELETE; resets state to NOT_ADDED) ----
    @requires_id
    def reset(self) -> FugaResponse:
        return self.client.delete(self._base())

    # ---- per-DSP actions ----
    @requires_id
    def block(self, dsps: DspsArg) -> FugaResponse:
        return self.client.put(f"{self._base()}/block", data=self._normalize_dsps(dsps))

    @requires_id
    def unblock(self, dsps: DspsArg) -> FugaResponse:
        return self.client.put(
            f"{self._base()}/unblock", data=self._normalize_dsps(dsps)
        )

    @requires_id
    def deliver(self, dsps: DspsArg) -> FugaResponse:
        return self.client.post(
            f"{self._base()}/deliver", data=self._normalize_dsps(dsps)
        )

    @requires_id
    def redeliver(self, dsps: DspsArg) -> FugaResponse:
        return self.client.post(
            f"{self._base()}/redeliver", data=self._normalize_dsps(dsps)
        )

    @requires_id
    def redeliver_all(self) -> FugaResponse:
        return self.client.post(f"{self._base()}/redeliver_all")

    @requires_id
    def takedown(self, dsps: DspsArg) -> FugaResponse:
        return self.client.post(
            f"{self._base()}/takedown", data=self._normalize_dsps(dsps)
        )

    @requires_id
    def edit(self, instructions: list[dict[str, Any]]) -> FugaResponse:
        """
        Edit one or more delivery instructions. Each dict must include "dsp" plus
        any subset of: enable_asset_release_dates, enable_asset_territories,
        lead_time, release_date, release_time, include_territories,
        exclude_territories, preferred_language.
        """
        return self.client.put(f"{self._base()}/edit", data=instructions)

    # ---- exclusivity ----
    @requires_id
    def make_exclusive(self) -> FugaResponse:
        return self.client.put(f"{self._base()}/exclusive")

    @requires_id
    def remove_exclusive(self) -> FugaResponse:
        return self.client.delete(f"{self._base()}/exclusive")
