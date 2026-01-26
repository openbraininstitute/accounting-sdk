"""Session factory."""

import logging
import os
from decimal import Decimal
from uuid import UUID

import httpx

from obp_accounting_sdk._async.longrun import AsyncLongrunSession, AsyncNullLongrunSession
from obp_accounting_sdk._async.oneshot import AsyncNullOneshotSession, AsyncOneshotSession
from obp_accounting_sdk.constants import ServiceSubtype
from obp_accounting_sdk.utils import (
    _handle_estimate_oneshot_cost_error,
    _parse_estimate_oneshot_cost_response,
    _prepare_estimate_oneshot_cost_data,
)

L = logging.getLogger(__name__)


class AsyncAccountingSessionFactory:
    """Accounting Session Factory."""

    def __init__(
        self,
        http_client_class: type[httpx.AsyncClient] | None = None,
        *,
        base_url: str | None = None,
        disabled: bool | None = None,
    ) -> None:
        """Initialization."""
        self._http_client = None
        self._http_client_class = http_client_class or httpx.AsyncClient
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

    async def aclose(self) -> None:
        """Close the resources."""
        if self._http_client:
            await self._http_client.aclose()

    def oneshot_session(self, **kwargs) -> AsyncOneshotSession | AsyncNullOneshotSession:
        """Return a new oneshot session."""
        if self._disabled:
            return AsyncNullOneshotSession()
        if not self._http_client:
            errmsg = "The internal http client is not set"
            raise RuntimeError(errmsg)
        return AsyncOneshotSession(http_client=self._http_client, base_url=self._base_url, **kwargs)

    def longrun_session(self, **kwargs) -> AsyncLongrunSession | AsyncNullLongrunSession:
        """Return a new longrun session."""
        if self._disabled:
            return AsyncNullLongrunSession()
        if not self._http_client:
            errmsg = "The internal http client is not set"
            raise RuntimeError(errmsg)
        return AsyncLongrunSession(http_client=self._http_client, base_url=self._base_url, **kwargs)

    async def estimate_oneshot_cost(
        self,
        subtype: ServiceSubtype | str,
        count: int,
        proj_id: UUID | str,
    ) -> Decimal:
        """Estimate the cost in credits for a oneshot job."""
        if self._disabled:
            return Decimal(0)
        if not self._http_client:
            errmsg = "The internal http client is not set"
            raise RuntimeError(errmsg)

        data = _prepare_estimate_oneshot_cost_data(
            subtype=subtype,
            count=count,
            proj_id=proj_id,
        )

        try:
            response = await self._http_client.post(
                f"{self._base_url}/estimate/oneshot",
                json=data,
            )
            response.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            _handle_estimate_oneshot_cost_error(exc, exc.request)

        return _parse_estimate_oneshot_cost_response(response)
