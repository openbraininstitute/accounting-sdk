"""Session factory."""

import logging
import os

import httpx

from obp_accounting_sdk._async.longrun import AsyncLongrunSession, AsyncNullLongrunSession
from obp_accounting_sdk._async.oneshot import AsyncNullOneshotSession, AsyncOneshotSession

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
