from contextlib import closing
from decimal import Decimal
from unittest.mock import Mock

import httpx
import pytest

from obp_accounting_sdk import OneshotSession
from obp_accounting_sdk._sync import factory as test_module
from obp_accounting_sdk._sync.oneshot import NullOneshotSession
from obp_accounting_sdk.constants import ServiceSubtype
from obp_accounting_sdk.errors import AccountingReservationError

BASE_URL = "http://test"
PROJ_ID = "00000000-0000-0000-0000-000000000001"
USER_ID = "00000000-0000-0000-0000-000000000002"


def test_factory_with_aclosing(monkeypatch):
    monkeypatch.setenv("ACCOUNTING_BASE_URL", BASE_URL)
    with closing(test_module.AccountingSessionFactory()) as session_factory:
        oneshot_session = session_factory.oneshot_session(
            subtype=ServiceSubtype.ML_LLM,
            proj_id=PROJ_ID,
            user_id=USER_ID,
            count=10,
        )
        assert isinstance(oneshot_session, OneshotSession)


def test_factory_with_name(monkeypatch):
    monkeypatch.setenv("ACCOUNTING_BASE_URL", BASE_URL)
    with closing(test_module.AccountingSessionFactory()) as session_factory:
        oneshot_session = session_factory.oneshot_session(
            subtype=ServiceSubtype.ML_LLM,
            proj_id=PROJ_ID,
            user_id=USER_ID,
            name="test job",
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
            user_id=USER_ID,
            count=10,
        )
        assert isinstance(oneshot_session, NullOneshotSession)


def test_factory_with_env_var_accounting_disabled_invalid(monkeypatch):
    monkeypatch.setenv("ACCOUNTING_DISABLED", "1")
    with closing(test_module.AccountingSessionFactory()) as session_factory:
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


def test_factory_constructor_base_url(monkeypatch):
    fake_os = Mock()
    monkeypatch.setattr("obp_accounting_sdk._sync.factory.os", fake_os)

    session_factory = test_module.AccountingSessionFactory(base_url="http://example.com")

    assert session_factory._base_url == "http://example.com"
    assert session_factory._disabled is False
    assert fake_os.getenv.call_count == 1
    fake_os.getenv.assert_called_with("ACCOUNTING_DISABLED", "")


def test_factory_constructor_base_url_and_disabled(monkeypatch):
    fake_os = Mock()
    monkeypatch.setattr("obp_accounting_sdk._sync.factory.os", fake_os)

    session_factory = test_module.AccountingSessionFactory(
        base_url="http://example.com", disabled=True
    )

    assert session_factory._base_url == "http://example.com"
    assert session_factory._disabled is True
    assert fake_os.getenv.call_count == 0


def test_estimate_oneshot_cost_success(httpx_mock, monkeypatch):
    monkeypatch.setenv("ACCOUNTING_BASE_URL", BASE_URL)
    httpx_mock.add_response(
        json={"message": "Cost estimation for oneshot job", "data": {"cost": "123.45"}},
        method="POST",
        url=f"{BASE_URL}/estimate/oneshot",
    )

    with closing(test_module.AccountingSessionFactory()) as session_factory:
        cost = session_factory.estimate_oneshot_cost(
            subtype=ServiceSubtype.ML_LLM,
            count=100,
            proj_id=PROJ_ID,
        )
        assert cost == Decimal("123.45")


def test_estimate_oneshot_cost_with_disabled(monkeypatch):
    monkeypatch.setenv("ACCOUNTING_DISABLED", "1")
    with closing(test_module.AccountingSessionFactory()) as session_factory:
        cost = session_factory.estimate_oneshot_cost(
            subtype=ServiceSubtype.ML_LLM,
            count=100,
            proj_id=PROJ_ID,
        )
        assert cost == Decimal(0)


def test_estimate_oneshot_cost_with_http_client_none(monkeypatch):
    monkeypatch.setenv("ACCOUNTING_DISABLED", "1")
    with closing(test_module.AccountingSessionFactory()) as session_factory:
        assert session_factory._disabled is True
        # enforce an invalid internal status, although this should never happen
        monkeypatch.setattr(session_factory, "_disabled", False)
        with pytest.raises(RuntimeError, match="The internal http client is not set"):
            session_factory.estimate_oneshot_cost(
                subtype=ServiceSubtype.ML_LLM,
                count=100,
                proj_id=PROJ_ID,
            )


def test_estimate_oneshot_cost_with_http_error(httpx_mock, monkeypatch):
    monkeypatch.setenv("ACCOUNTING_BASE_URL", BASE_URL)
    httpx_mock.add_response(
        status_code=400,
        method="POST",
        url=f"{BASE_URL}/estimate/oneshot",
    )

    with closing(test_module.AccountingSessionFactory()) as session_factory:
        with pytest.raises(
            AccountingReservationError,
            match=f"Error in response to POST {BASE_URL}/estimate/oneshot: 400",
        ):
            session_factory.estimate_oneshot_cost(
                subtype=ServiceSubtype.ML_LLM,
                count=100,
                proj_id=PROJ_ID,
            )


def test_estimate_oneshot_cost_with_timeout(httpx_mock, monkeypatch):
    monkeypatch.setenv("ACCOUNTING_BASE_URL", BASE_URL)
    httpx_mock.add_exception(
        httpx.ReadTimeout("Unable to read within timeout"),
        method="POST",
        url=f"{BASE_URL}/estimate/oneshot",
    )

    with closing(test_module.AccountingSessionFactory()) as session_factory:
        with pytest.raises(
            AccountingReservationError,
            match=f"Error in request POST {BASE_URL}/estimate/oneshot",
        ):
            session_factory.estimate_oneshot_cost(
                subtype=ServiceSubtype.ML_LLM,
                count=100,
                proj_id=PROJ_ID,
            )


def test_estimate_oneshot_cost_with_parsing_error(httpx_mock, monkeypatch):
    monkeypatch.setenv("ACCOUNTING_BASE_URL", BASE_URL)
    httpx_mock.add_response(
        json={"message": "", "data": {}},  # missing cost
        method="POST",
        url=f"{BASE_URL}/estimate/oneshot",
    )

    with closing(test_module.AccountingSessionFactory()) as session_factory:
        with pytest.raises(AccountingReservationError, match="Error while parsing the response"):
            session_factory.estimate_oneshot_cost(
                subtype=ServiceSubtype.ML_LLM,
                count=100,
                proj_id=PROJ_ID,
            )


def test_estimate_oneshot_cost_with_invalid_response_format(httpx_mock, monkeypatch):
    monkeypatch.setenv("ACCOUNTING_BASE_URL", BASE_URL)
    httpx_mock.add_response(
        json={"message": "Invalid response"},  # missing data field
        method="POST",
        url=f"{BASE_URL}/estimate/oneshot",
    )

    with closing(test_module.AccountingSessionFactory()) as session_factory:
        with pytest.raises(AccountingReservationError, match="Error while parsing the response"):
            session_factory.estimate_oneshot_cost(
                subtype=ServiceSubtype.ML_LLM,
                count=100,
                proj_id=PROJ_ID,
            )
