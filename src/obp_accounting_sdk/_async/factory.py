"""Session factory."""

import os

import httpx

from obp_accounting_sdk._async.longrun import AsyncLongrunSession
from obp_accounting_sdk._async.oneshot import AsyncOneshotSession


class AsyncAccountingSessionFactory:
    """Accounting Session Factory."""

    def __init__(self, http_client_class: type[httpx.AsyncClient] | None = None) -> None:
        """Initialization."""
        self._http_client_class = http_client_class or httpx.AsyncClient
        self._http_client = self._http_client_class()
        self._base_url = os.environ.get("ACCOUNTING_BASE_URL", "")
        if not self._base_url:
            errmsg = "ACCOUNTING_BASE_URL is not set"
            raise RuntimeError(errmsg)

    async def aclose(self) -> None:
        """Close the resources."""
        await self._http_client.aclose()

    def oneshot_session(self, **kwargs) -> AsyncOneshotSession:
        """Return a new oneshot session."""
        return AsyncOneshotSession(http_client=self._http_client, base_url=self._base_url, **kwargs)

    def longrun_session(self, **kwargs) -> AsyncLongrunSession:
        """Return a new longrun session."""
        return AsyncLongrunSession(http_client=self._http_client, base_url=self._base_url, **kwargs)
