"""Session factory."""

import logging
import os

import httpx

from obp_accounting_sdk._sync.longrun import SyncLongrunSession, SyncNullLongrunSession
from obp_accounting_sdk._sync.oneshot import NullOneshotSession, OneshotSession

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
