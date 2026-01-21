"""Session factory."""

import logging
import os
from decimal import Decimal
from uuid import UUID

import httpx

from obp_accounting_sdk._sync.longrun import SyncLongrunSession, SyncNullLongrunSession
from obp_accounting_sdk._sync.oneshot import NullOneshotSession, OneshotSession
from obp_accounting_sdk.constants import ServiceSubtype, ServiceType
from obp_accounting_sdk.errors import AccountingReservationError

L = logging.getLogger(__name__)


class AccountingSessionFactory:
    """Accounting Session Factory."""

    def __init__(
        self,
        http_client_class: type[httpx.Client] | None = None,
        *,
        base_url: str | None = None,
        disabled: bool | None = None,
    ) -> None:
        """Initialization."""
        self._http_client = None
        self._http_client_class = http_client_class or httpx.Client
        self._base_url = os.getenv("ACCOUNTING_BASE_URL", "") if base_url is None else base_url
        self._disabled = (
            os.getenv("ACCOUNTING_DISABLED", "") == "1" if disabled is None else disabled
        )

        if self._disabled:
            L.warning("Accounting integration is disabled")
            return

        self._http_client = self._http_client_class()
        if not self._base_url:
            errmsg = "ACCOUNTING_BASE_URL must be set"
            raise RuntimeError(errmsg)

    def close(self) -> None:
        """Close the resources."""
        if self._http_client:
            self._http_client.close()

    def oneshot_session(self, **kwargs) -> OneshotSession | NullOneshotSession:
        """Return a new oneshot session."""
        if self._disabled:
            return NullOneshotSession()
        if not self._http_client:
            errmsg = "The internal http client is not set"
            raise RuntimeError(errmsg)
        return OneshotSession(http_client=self._http_client, base_url=self._base_url, **kwargs)

    def longrun_session(self, **kwargs) -> SyncLongrunSession | SyncNullLongrunSession:
        """Return a new longrun session."""
        if self._disabled:
            return SyncNullLongrunSession()
        if not self._http_client:
            errmsg = "The internal http client is not set"
            raise RuntimeError(errmsg)
        return SyncLongrunSession(http_client=self._http_client, base_url=self._base_url, **kwargs)

    def estimate_oneshot_cost(
        self,
        subtype: ServiceSubtype | str,
        count: int,
        *,
        proj_id: UUID | str | None = None,
        vlab_id: UUID | str | None = None,
    ) -> Decimal:
        """Estimate the cost in credits for a oneshot job."""
        if self._disabled:
            return Decimal("0")
        if not self._http_client:
            errmsg = "The internal http client is not set"
            raise RuntimeError(errmsg)
        if proj_id is None and vlab_id is None:
            errmsg = "Either proj_id or vlab_id must be provided"
            raise ValueError(errmsg)

        data = {
            "type": ServiceType.ONESHOT,
            "subtype": str(ServiceSubtype(subtype)),
            "count": count,
        }
        if proj_id is not None:
            data["proj_id"] = str(proj_id)
        if vlab_id is not None:
            data["vlab_id"] = str(vlab_id)

        try:
            response = self._http_client.post(
                f"{self._base_url}/price/estimate/oneshot",
                json=data,
            )
            response.raise_for_status()
        except httpx.RequestError as exc:
            errmsg = f"Error in request {exc.request.method} {exc.request.url}"
            raise AccountingReservationError(message=errmsg) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            errmsg = f"Error in response to {exc.request.method} {exc.request.url}: {status_code}"
            raise AccountingReservationError(message=errmsg, http_status_code=status_code) from exc
        try:
            result = response.json()
            cost_str = result["data"]["cost"]
            return Decimal(str(cost_str))
        except Exception as exc:
            errmsg = "Error while parsing the response"
            raise AccountingReservationError(message=errmsg) from exc
