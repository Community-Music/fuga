from typing import Optional, Dict, Any, List, Union, Iterable
from .api import FUGAClient


DspArg = Union[int, str, Dict[str, Any]]
DspsArg = Union[DspArg, Iterable[DspArg]]


class FUGADeliveryInstructions:
    """
    Wrapper for FUGA delivery instructions endpoints, scoped to a single product.

    All endpoints live under /products/{product_id}/delivery_instructions.
    Responses follow the standard FUGAClient shape: {"success", "status_code", "data" | "error"}.
    """

    def __init__(self, client: FUGAClient, product_id: Optional[str] = None):
        self.client = client
        self.product_id = product_id

    # ---- helpers ----
    def _need_id(self) -> Dict[str, Any]:
        return {
            "success": False,
            "status_code": None,
            "error": {"message": "product_id is required"},
        }

    @staticmethod
    def _normalize_dsps(dsps: DspsArg) -> List[Dict[str, Any]]:
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
            return [dsps]
        out: List[Dict[str, Any]] = []
        for item in dsps:
            if isinstance(item, dict):
                out.append(item)
            else:
                out.append({"dsp": item})
        return out

    def _base(self) -> str:
        return f"/products/{self.product_id}/delivery_instructions"

    # ---- read ----
    def fetch(self) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.get(self._base())

    def fetch_dsp_history(self, dsp_id: Union[int, str]) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.get(f"{self._base()}/{dsp_id}/history")

    # ---- reset (collection-root DELETE; resets state to NOT_ADDED) ----
    def reset(self) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.delete(self._base())

    # ---- per-DSP actions ----
    def block(self, dsps: DspsArg) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.put(f"{self._base()}/block", data=self._normalize_dsps(dsps))

    def unblock(self, dsps: DspsArg) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.put(f"{self._base()}/unblock", data=self._normalize_dsps(dsps))

    def deliver(self, dsps: DspsArg) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.post(f"{self._base()}/deliver", data=self._normalize_dsps(dsps))

    def redeliver(self, dsps: DspsArg) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.post(f"{self._base()}/redeliver", data=self._normalize_dsps(dsps))

    def redeliver_all(self) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.post(f"{self._base()}/redeliver_all")

    def takedown(self, dsps: DspsArg) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.post(f"{self._base()}/takedown", data=self._normalize_dsps(dsps))

    def edit(self, instructions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Edit one or more delivery instructions. Each dict must include "dsp" plus
        any subset of: enable_asset_release_dates, enable_asset_territories,
        lead_time, release_date, release_time, include_territories,
        exclude_territories, preferred_language.
        """
        if not self.product_id:
            return self._need_id()
        return self.client.put(f"{self._base()}/edit", data=instructions)

    # ---- exclusivity ----
    def make_exclusive(self) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.put(f"{self._base()}/exclusive")

    def remove_exclusive(self) -> Dict[str, Any]:
        if not self.product_id:
            return self._need_id()
        return self.client.delete(f"{self._base()}/exclusive")
