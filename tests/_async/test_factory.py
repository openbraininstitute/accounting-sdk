from contextlib import aclosing
from unittest.mock import Mock

import pytest

from obp_accounting_sdk import AsyncOneshotSession
from obp_accounting_sdk._async import factory as test_module
from obp_accounting_sdk._async.oneshot import AsyncNullOneshotSession
from obp_accounting_sdk.constants import ServiceSubtype

BASE_URL = "http://test"
PROJ_ID = "00000000-0000-0000-0000-000000000001"
USER_ID = "00000000-0000-0000-0000-000000000002"


async def test_factory_with_aclosing(monkeypatch):
    monkeypatch.setenv("ACCOUNTING_BASE_URL", BASE_URL)
    async with aclosing(test_module.AsyncAccountingSessionFactory()) as session_factory:
        oneshot_session = session_factory.oneshot_session(
            subtype=ServiceSubtype.ML_LLM,
            proj_id=PROJ_ID,
            user_id=USER_ID,
            count=10,
        )
        assert isinstance(oneshot_session, AsyncOneshotSession)


async def test_factory_with_name(monkeypatch):
    monkeypatch.setenv("ACCOUNTING_BASE_URL", BASE_URL)
    async with aclosing(test_module.AsyncAccountingSessionFactory()) as session_factory:
        oneshot_session = session_factory.oneshot_session(
            subtype=ServiceSubtype.ML_LLM,
            proj_id=PROJ_ID,
            user_id=USER_ID,
            name="test job",
            count=10,
        )
        assert isinstance(oneshot_session, AsyncOneshotSession)


async def test_factory_without_env_var_accounting_base_url(monkeypatch):
    monkeypatch.delenv("ACCOUNTING_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="ACCOUNTING_BASE_URL must be set"):
        test_module.AsyncAccountingSessionFactory()


async def test_factory_with_env_var_accounting_disabled(monkeypatch):
    monkeypatch.setenv("ACCOUNTING_DISABLED", "1")
    async with aclosing(test_module.AsyncAccountingSessionFactory()) as session_factory:
        assert session_factory._disabled is True
        oneshot_session = session_factory.oneshot_session(
            subtype=ServiceSubtype.ML_LLM,
            proj_id=PROJ_ID,
            user_id=USER_ID,
            count=10,
        )
        assert isinstance(oneshot_session, AsyncNullOneshotSession)


async def test_factory_with_env_var_accounting_disabled_invalid(monkeypatch):
    monkeypatch.setenv("ACCOUNTING_DISABLED", "1")
    async with aclosing(test_module.AsyncAccountingSessionFactory()) as session_factory:
        assert session_factory._disabled is True
        # enforce an invalid internal status, although this should never happen
        monkeypatch.setattr(session_factory, "_disabled", False)
        with pytest.raises(RuntimeError, match="The internal http client is not set"):
            session_factory.oneshot_session(
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                count=10,
            )


async def test_factory_constructor_base_url(monkeypatch):
    fake_os = Mock()
    monkeypatch.setattr("obp_accounting_sdk._async.factory.os", fake_os)

    session_factory = test_module.AsyncAccountingSessionFactory(base_url="http://example.com")

    assert session_factory._base_url == "http://example.com"
    assert session_factory._disabled is False
    assert fake_os.getenv.call_count == 1
    fake_os.getenv.assert_called_with("ACCOUNTING_DISABLED", "")


async def test_factory_constructor_base_url_and_disabled(monkeypatch):
    fake_os = Mock()
    monkeypatch.setattr("obp_accounting_sdk._async.factory.os", fake_os)

    session_factory = test_module.AsyncAccountingSessionFactory(
        base_url="http://example.com", disabled=True
    )

    assert session_factory._base_url == "http://example.com"
    assert session_factory._disabled is True
    assert fake_os.getenv.call_count == 0
