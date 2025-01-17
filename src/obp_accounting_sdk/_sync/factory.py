"""Session factory."""

import logging
import os

import httpx

from obp_accounting_sdk._sync.oneshot import NullOneshotSession, OneshotSession

L = logging.getLogger(__name__)


class AccountingSessionFactory:
    """Accounting Session Factory."""

    def __init__(self, http_client_class: type[httpx.Client] | None = None) -> None:
        """Initialization."""
        self._http_client = None
        self._http_client_class = http_client_class or httpx.Client
        self._base_url = os.getenv("ACCOUNTING_BASE_URL", "")
        self._disabled = os.getenv("ACCOUNTING_DISABLED", "") == "1"

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
