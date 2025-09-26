"""Dependencies."""

from typing import Annotated

from fastapi import Depends
from starlette.requests import Request

from obp_accounting_sdk import AccountingSessionFactory, AsyncAccountingSessionFactory


def _get_accounting_async_session_factory(request: Request) -> AsyncAccountingSessionFactory:
    return request.state.async_session_factory


def _get_accounting_sync_session_factory(request: Request) -> AccountingSessionFactory:
    return request.state.sync_session_factory


AsyncAccountingSessionFactoryDep = Annotated[
    AsyncAccountingSessionFactory, Depends(_get_accounting_async_session_factory)
]

SyncAccountingSessionFactoryDep = Annotated[
    AccountingSessionFactory, Depends(_get_accounting_sync_session_factory)
]
