import re

import httpx
import pytest

from obp_accounting_sdk._sync import oneshot as test_module
from obp_accounting_sdk.constants import MAX_JOB_NAME_LENGTH, ServiceSubtype
from obp_accounting_sdk.errors import (
    AccountingReservationError,
    AccountingUsageError,
    InsufficientFundsError,
)

BASE_URL = "http://test"
PROJ_ID = "00000000-0000-0000-0000-000000000001"
JOB_ID = "00000000-0000-0000-0000-000000000002"
USER_ID = "00000000-0000-0000-0000-000000000003"


def test_oneshot_session_success(httpx_mock):
    httpx_mock.add_response(
        json={"message": "", "data": {"job_id": JOB_ID}},
        method="POST",
        url=f"{BASE_URL}/reservation/oneshot",
    )
    httpx_mock.add_response(
        json={"message": "", "data": None},
        method="POST",
        url=f"{BASE_URL}/usage/oneshot",
    )

    with httpx.Client() as http_client:
        with test_module.OneshotSession(
            http_client=http_client,
            base_url=BASE_URL,
            subtype=ServiceSubtype.ML_LLM,
            proj_id=PROJ_ID,
            user_id=USER_ID,
            count=10,
        ) as session:
            assert session.count == 10
            with pytest.raises(ValueError, match="count must be an integer >= 0"):
                session.count = None
            with pytest.raises(ValueError, match="count must be an integer >= 0"):
                session.count = -10
            session.count = 20
            assert session.count == 20

            assert session.name is None
            name_value_error = f"Job name must be a string with max length {MAX_JOB_NAME_LENGTH}"
            with pytest.raises(ValueError, match=name_value_error):
                session.name = None
            with pytest.raises(ValueError, match=name_value_error):
                session.name = 123
            session.name = "test job"
            assert session.name == "test job"

            # Overwrite existing name
            session.name = "test job 2 updated"
            assert session.name == "test job 2 updated"


def test_oneshot_session_with_name(httpx_mock):
    httpx_mock.add_response(
        json={"message": "", "data": {"job_id": JOB_ID}},
        method="POST",
        url=f"{BASE_URL}/reservation/oneshot",
    )
    httpx_mock.add_response(
        json={"message": "", "data": None},
        method="POST",
        url=f"{BASE_URL}/usage/oneshot",
    )

    with httpx.Client() as http_client:
        with test_module.OneshotSession(
            http_client=http_client,
            base_url=BASE_URL,
            subtype=ServiceSubtype.ML_LLM,
            proj_id=PROJ_ID,
            user_id=USER_ID,
            name="test job",
            count=10,
        ) as session:
            assert session.name == "test job"


def test_oneshot_session_with_insufficient_funds(httpx_mock):
    httpx_mock.add_response(
        status_code=402,
        method="POST",
        url=f"{BASE_URL}/reservation/oneshot",
    )
    with httpx.Client() as http_client:
        with pytest.raises(InsufficientFundsError):
            with test_module.OneshotSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                count=10,
            ):
                pass


def test_oneshot_session_with_payload_error(httpx_mock):
    httpx_mock.add_response(
        json={"message": "", "data": {}},  # missing job_id
        method="POST",
        url=f"{BASE_URL}/reservation/oneshot",
    )
    with httpx.Client() as http_client:
        with pytest.raises(AccountingReservationError, match="Error while parsing the response"):
            with test_module.OneshotSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                count=10,
            ):
                pass


def test_oneshot_session_with_reservation_timeout(httpx_mock):
    httpx_mock.add_exception(
        httpx.ReadTimeout("Unable to read within timeout"),
        method="POST",
        url=f"{BASE_URL}/reservation/oneshot",
    )
    with httpx.Client() as http_client:
        with pytest.raises(
            AccountingReservationError,
            match=f"Error in request POST {BASE_URL}/reservation/oneshot",
        ):
            with test_module.OneshotSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                count=10,
            ):
                pass


def test_oneshot_session_with_reservation_error(httpx_mock):
    httpx_mock.add_response(
        status_code=400,
        method="POST",
        url=f"{BASE_URL}/reservation/oneshot",
    )
    with httpx.Client() as http_client:
        with pytest.raises(
            AccountingReservationError,
            match=f"Error in response to POST {BASE_URL}/reservation/oneshot: 400",
        ):
            with test_module.OneshotSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                count=10,
            ):
                pass


def test_oneshot_session_with_usage_timeout(httpx_mock):
    httpx_mock.add_response(
        json={"message": "", "data": {"job_id": JOB_ID}},
        method="POST",
        url=f"{BASE_URL}/reservation/oneshot",
    )
    httpx_mock.add_exception(
        httpx.ReadTimeout("Unable to read within timeout"),
        method="POST",
        url=f"{BASE_URL}/usage/oneshot",
    )
    with httpx.Client() as http_client:
        with pytest.raises(
            AccountingUsageError,
            match=f"Error in request POST {BASE_URL}/usage/oneshot",
        ):
            with test_module.OneshotSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                count=10,
            ):
                pass


def test_oneshot_session_with_usage_error(httpx_mock):
    httpx_mock.add_response(
        json={"message": "", "data": {"job_id": JOB_ID}},
        method="POST",
        url=f"{BASE_URL}/reservation/oneshot",
    )
    httpx_mock.add_response(
        status_code=400,
        method="POST",
        url=f"{BASE_URL}/usage/oneshot",
    )
    with httpx.Client() as http_client:
        with pytest.raises(
            AccountingUsageError,
            match=f"Error in response to POST {BASE_URL}/usage/oneshot: 400",
        ):
            with test_module.OneshotSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                count=10,
            ):
                pass


def test_oneshot_session_improperly_used(httpx_mock):
    httpx_mock.add_response(
        json={"message": "", "data": {"job_id": JOB_ID}},
        method="POST",
        url=f"{BASE_URL}/reservation/oneshot",
    )
    with httpx.Client() as http_client:
        session = test_module.OneshotSession(
            http_client=http_client,
            base_url=BASE_URL,
            subtype=ServiceSubtype.ML_LLM,
            proj_id=PROJ_ID,
            user_id=USER_ID,
            count=10,
        )
        with pytest.raises(
            RuntimeError, match="Cannot send usage before making a successful reservation"
        ):
            session._send_usage()
        with pytest.raises(RuntimeError, match="Cannot cancel a reservation without a job id"):
            session._cancel_reservation()
        session._make_reservation()
        with pytest.raises(RuntimeError, match="Cannot make a reservation more than once"):
            session._make_reservation()


def test_oneshot_session_with_application_error(httpx_mock, caplog):
    httpx_mock.add_response(
        json={"message": "", "data": {"job_id": JOB_ID}},
        method="POST",
        url=f"{BASE_URL}/reservation/oneshot",
    )
    httpx_mock.add_response(
        method="DELETE",
        url=f"{BASE_URL}/reservation/oneshot/{JOB_ID}",
    )

    def func():
        errmsg = "Application error"
        raise RuntimeError(errmsg)

    with httpx.Client() as http_client:
        with pytest.raises(Exception, match="Application error"):
            with test_module.OneshotSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                count=10,
            ):
                func()
    assert "Unhandled application error RuntimeError, cancelling reservation" in caplog.text
    assert "Error while cancelling the reservation" not in caplog.text


def test_oneshot_session_with_application_error_and_cancellation_error(httpx_mock, caplog):
    httpx_mock.add_response(
        json={"message": "", "data": {"job_id": JOB_ID}},
        method="POST",
        url=f"{BASE_URL}/reservation/oneshot",
    )
    httpx_mock.add_response(
        status_code=400,
        method="DELETE",
        url=f"{BASE_URL}/reservation/oneshot/{JOB_ID}",
    )

    def func():
        errmsg = "Application error"
        raise RuntimeError(errmsg)

    with httpx.Client() as http_client:
        with pytest.raises(Exception, match="Application error"):
            with test_module.OneshotSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                count=10,
            ):
                func()
    assert "Unhandled application error RuntimeError, cancelling reservation" in caplog.text
    assert "Error while cancelling the reservation" in caplog.text
    assert re.search(
        f"AccountingCancellationError.*"
        f"Error in response to DELETE {BASE_URL}/reservation/oneshot/{JOB_ID}: 400",
        caplog.text,
    )


def test_oneshot_session_with_application_error_and_cancellation_timeout(httpx_mock, caplog):
    httpx_mock.add_response(
        json={"message": "", "data": {"job_id": JOB_ID}},
        method="POST",
        url=f"{BASE_URL}/reservation/oneshot",
    )
    httpx_mock.add_exception(
        httpx.ReadTimeout("Unable to read within timeout"),
        method="DELETE",
        url=f"{BASE_URL}/reservation/oneshot/{JOB_ID}",
    )

    def func():
        errmsg = "Application error"
        raise RuntimeError(errmsg)

    with httpx.Client() as http_client:
        with pytest.raises(Exception, match="Application error"):
            with test_module.OneshotSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                count=10,
            ):
                func()
    assert "Unhandled application error RuntimeError, cancelling reservation" in caplog.text
    assert "Error while cancelling the reservation" in caplog.text
    assert re.search(
        f"AccountingCancellationError.*"
        f"Error in request DELETE {BASE_URL}/reservation/oneshot/{JOB_ID}",
        caplog.text,
    )


def test_oneshot_session_null_as_context_manager():
    with test_module.NullOneshotSession() as session:
        assert session.count == 0
