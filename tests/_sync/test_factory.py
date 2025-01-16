from contextlib import closing

import pytest

from obp_accounting_sdk import OneshotSession
from obp_accounting_sdk._sync import factory as test_module
from obp_accounting_sdk._sync.oneshot import NullOneshotSession
from obp_accounting_sdk.constants import ServiceSubtype

BASE_URL = "http://test"
PROJ_ID = "00000000-0000-0000-0000-000000000001"


def test_factory_with_aclosing(monkeypatch):
    monkeypatch.setenv("ACCOUNTING_BASE_URL", BASE_URL)
    with closing(test_module.AccountingSessionFactory()) as session_factory:
        oneshot_session = session_factory.oneshot_session(
            subtype=ServiceSubtype.ML_LLM,
            proj_id=PROJ_ID,
            count=10,
        )
        assert isinstance(oneshot_session, OneshotSession)


def test_factory_without_env_var_accounting_base_url(monkeypatch):
    monkeypatch.delenv("ACCOUNTING_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="ACCOUNTING_BASE_URL must be set"):
        test_module.AccountingSessionFactory()


def test_factory_with_env_var_accounting_disabled(monkeypatch):
    monkeypatch.setenv("ACCOUNTING_DISABLED", "1")
    with closing(test_module.AccountingSessionFactory()) as session_factory:
        assert session_factory._disabled is True
        oneshot_session = session_factory.oneshot_session(
            subtype=ServiceSubtype.ML_LLM,
            proj_id=PROJ_ID,
            count=10,
        )
        assert isinstance(oneshot_session, NullOneshotSession)


def test_factory_with_env_var_accounting_disabled_invalid(monkeypatch):
    monkeypatch.setenv("ACCOUNTING_DISABLED", "1")
    with closing(test_module.AccountingSessionFactory()) as session_factory:
        assert session_factory._disabled is True
        with monkeypatch.context() as monkeycontext:
            # enforce an invalid internal status, although this should never happen
            monkeycontext.setattr(session_factory, "_disabled", False)
            with pytest.raises(RuntimeError, match="The internal http client is not set"):
                session_factory.oneshot_session(
                    subtype=ServiceSubtype.ML_LLM,
                    proj_id=PROJ_ID,
                    count=10,
                )
