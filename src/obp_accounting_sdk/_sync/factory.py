"""Session factory."""

import os

import httpx

from obp_accounting_sdk._sync.longrun import SyncLongrunSession
from obp_accounting_sdk._sync.oneshot import OneshotSession


class AccountingSessionFactory:
    """Accounting Session Factory."""

    def __init__(self, http_client_class: type[httpx.Client] | None = None) -> None:
        """Initialization."""
        self._http_client_class = http_client_class or httpx.Client
        self._http_client = self._http_client_class()
        self._base_url = os.environ.get("ACCOUNTING_BASE_URL", "")
        if not self._base_url:
            errmsg = "ACCOUNTING_BASE_URL is not set"
            raise RuntimeError(errmsg)

    def close(self) -> None:
        """Close the resources."""
        self._http_client.close()

    def oneshot_session(self, **kwargs) -> OneshotSession:
        """Return a new oneshot session."""
        return OneshotSession(http_client=self._http_client, base_url=self._base_url, **kwargs)

    def longrun_session(self, **kwargs) -> SyncLongrunSession:
        """Return a new longrun session."""
        return SyncLongrunSession(http_client=self._http_client, base_url=self._base_url, **kwargs)
