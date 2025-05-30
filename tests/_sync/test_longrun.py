import re

import httpx
import pytest

from obp_accounting_sdk._sync import longrun as test_module
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


def test_longrun_session_success(httpx_mock):
    httpx_mock.add_response(
        json={"message": "", "data": {"job_id": JOB_ID}},
        method="POST",
        url=f"{BASE_URL}/reservation/longrun",
    )
    # Start event
    httpx_mock.add_response(
        json={"message": "", "data": None},
        method="POST",
        url=f"{BASE_URL}/usage/longrun",
    )
    # Finish event
    httpx_mock.add_response(
        json={"message": "", "data": None},
        method="POST",
        url=f"{BASE_URL}/usage/longrun",
    )

    with httpx.Client() as http_client:
        with test_module.SyncLongrunSession(
            http_client=http_client,
            base_url=BASE_URL,
            subtype=ServiceSubtype.ML_LLM,
            proj_id=PROJ_ID,
            user_id=USER_ID,
            instances=10,
            instance_type="ml.g4dn.xlarge",
            duration=1000,
        ) as session:
            session.start()

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


def test_longrun_session_with_name(httpx_mock):
    httpx_mock.add_response(
        json={"message": "", "data": {"job_id": JOB_ID}},
        method="POST",
        url=f"{BASE_URL}/reservation/longrun",
    )
    # Start event
    httpx_mock.add_response(
        json={"message": "", "data": None},
        method="POST",
        url=f"{BASE_URL}/usage/longrun",
    )
    # Finish event
    httpx_mock.add_response(
        json={"message": "", "data": None},
        method="POST",
        url=f"{BASE_URL}/usage/longrun",
    )

    with httpx.Client() as http_client:
        with test_module.SyncLongrunSession(
            http_client=http_client,
            base_url=BASE_URL,
            subtype=ServiceSubtype.ML_LLM,
            proj_id=PROJ_ID,
            user_id=USER_ID,
            name="test job",
            instances=10,
            instance_type="ml.g4dn.xlarge",
            duration=1000,
        ) as session:
            assert session.name == "test job"

            session.start()


def test_longrun_session_with_insufficient_funds(httpx_mock):
    httpx_mock.add_response(
        status_code=402,
        method="POST",
        url=f"{BASE_URL}/reservation/longrun",
    )
    with httpx.Client() as http_client:
        with pytest.raises(InsufficientFundsError):
            with test_module.SyncLongrunSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                instances=10,
                instance_type="ml.g4dn.xlarge",
                duration=1000,
            ):
                pass


def test_longrun_session_with_payload_error(httpx_mock):
    httpx_mock.add_response(
        json={"message": "", "data": {}},  # missing job_id
        method="POST",
        url=f"{BASE_URL}/reservation/longrun",
    )
    with httpx.Client() as http_client:
        with pytest.raises(AccountingReservationError, match="Error while parsing the response"):
            with test_module.SyncLongrunSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                instances=10,
                instance_type="ml.g4dn.xlarge",
                duration=1000,
            ):
                pass


def test_longrun_session_with_reservation_timeout(httpx_mock):
    httpx_mock.add_exception(
        httpx.ReadTimeout("Unable to read within timeout"),
        method="POST",
        url=f"{BASE_URL}/reservation/longrun",
    )
    with httpx.Client() as http_client:
        with pytest.raises(
            AccountingReservationError,
            match=f"Error in request POST {BASE_URL}/reservation/longrun",
        ):
            with test_module.SyncLongrunSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                instances=10,
                instance_type="ml.g4dn.xlarge",
                duration=1000,
            ):
                pass


def test_longrun_session_with_reservation_error(httpx_mock):
    httpx_mock.add_response(
        status_code=400,
        method="POST",
        url=f"{BASE_URL}/reservation/longrun",
    )
    with httpx.Client() as http_client:
        with pytest.raises(
            AccountingReservationError,
            match=f"Error in response to POST {BASE_URL}/reservation/longrun: 400",
        ):
            with test_module.SyncLongrunSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                instances=10,
                instance_type="ml.g4dn.xlarge",
                duration=1000,
            ):
                pass


def test_longrun_session_with_usage_timeout(httpx_mock):
    httpx_mock.add_response(
        json={"message": "", "data": {"job_id": JOB_ID}},
        method="POST",
        url=f"{BASE_URL}/reservation/longrun",
    )
    httpx_mock.add_exception(
        httpx.ReadTimeout("Unable to read within timeout"),
        method="POST",
        url=f"{BASE_URL}/usage/longrun",
    )
    httpx_mock.add_response(
        method="DELETE",
        url=f"{BASE_URL}/reservation/longrun/{JOB_ID}",
    )
    with httpx.Client() as http_client:
        with pytest.raises(
            AccountingUsageError,
            match=f"Error in request POST {BASE_URL}/usage/longrun",
        ):
            with test_module.SyncLongrunSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                instances=10,
                instance_type="ml.g4dn.xlarge",
                duration=1000,
            ) as session:
                session.start()


def test_longrun_session_with_usage_error(httpx_mock):
    httpx_mock.add_response(
        json={"message": "", "data": {"job_id": JOB_ID}},
        method="POST",
        url=f"{BASE_URL}/reservation/longrun",
    )
    httpx_mock.add_response(
        status_code=400,
        method="POST",
        url=f"{BASE_URL}/usage/longrun",
    )
    httpx_mock.add_response(
        method="DELETE",
        url=f"{BASE_URL}/reservation/longrun/{JOB_ID}",
    )
    with httpx.Client() as http_client:
        with pytest.raises(
            AccountingUsageError,
            match=f"Error in response to POST {BASE_URL}/usage/longrun: 400",
        ):
            with test_module.SyncLongrunSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                instances=10,
                instance_type="ml.g4dn.xlarge",
                duration=1000,
            ) as session:
                session.start()


def test_longrun_session_improperly_used(httpx_mock):
    httpx_mock.add_response(
        json={"message": "", "data": {"job_id": JOB_ID}},
        method="POST",
        url=f"{BASE_URL}/reservation/longrun",
    )
    with httpx.Client() as http_client:
        session = test_module.SyncLongrunSession(
            http_client=http_client,
            base_url=BASE_URL,
            subtype=ServiceSubtype.ML_LLM,
            proj_id=PROJ_ID,
            user_id=USER_ID,
            instances=10,
            instance_type="ml.g4dn.xlarge",
            duration=1000,
        )
        # with pytest.raises(RuntimeError, match="Cannot cancel a reservation without a job id"):
        #     await session._cancel_reservation()
        session._make_reservation()
        with pytest.raises(RuntimeError, match="Cannot make a reservation more than once"):
            session._make_reservation()


def test_longrun_session_with_application_error(httpx_mock, caplog):
    httpx_mock.add_response(
        json={"message": "", "data": {"job_id": JOB_ID}},
        method="POST",
        url=f"{BASE_URL}/reservation/longrun",
    )
    httpx_mock.add_response(
        method="DELETE",
        url=f"{BASE_URL}/reservation/longrun/{JOB_ID}",
    )

    def func():
        errmsg = "Application error"
        raise RuntimeError(errmsg)

    with httpx.Client() as http_client:
        with pytest.raises(RuntimeError, match="Application error"):
            with test_module.SyncLongrunSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                instances=10,
                instance_type="ml.g4dn.xlarge",
                duration=1000,
            ):
                func()
    assert "Unhandled application error RuntimeError, cancelling reservation" in caplog.text
    assert "Error while cancelling the reservation" not in caplog.text


def test_longrun_session_with_application_error_and_cancellation_error(httpx_mock, caplog):
    httpx_mock.add_response(
        json={"message": "", "data": {"job_id": JOB_ID}},
        method="POST",
        url=f"{BASE_URL}/reservation/longrun",
    )
    httpx_mock.add_response(
        status_code=400,
        method="DELETE",
        url=f"{BASE_URL}/reservation/longrun/{JOB_ID}",
    )

    def func():
        errmsg = "Application error"
        raise RuntimeError(errmsg)

    with httpx.Client() as http_client:
        with pytest.raises(Exception, match="Application error"):
            with test_module.SyncLongrunSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                instances=10,
                instance_type="ml.g4dn.xlarge",
                duration=1000,
            ):
                func()
    assert "Unhandled application error RuntimeError, cancelling reservation" in caplog.text
    assert "Error while cancelling the reservation" in caplog.text
    assert re.search(
        f"AccountingCancellationError.*"
        f"Error in response to DELETE {BASE_URL}/reservation/longrun/{JOB_ID}: 400",
        caplog.text,
    )


def test_longrun_session_with_application_error_and_cancellation_timeout(httpx_mock, caplog):
    httpx_mock.add_response(
        json={"message": "", "data": {"job_id": JOB_ID}},
        method="POST",
        url=f"{BASE_URL}/reservation/longrun",
    )
    httpx_mock.add_exception(
        httpx.ReadTimeout("Unable to read within timeout"),
        method="DELETE",
        url=f"{BASE_URL}/reservation/longrun/{JOB_ID}",
    )

    def func():
        errmsg = "Application error"
        raise RuntimeError(errmsg)

    with httpx.Client() as http_client:
        with pytest.raises(Exception, match="Application error"):
            with test_module.SyncLongrunSession(
                http_client=http_client,
                base_url=BASE_URL,
                subtype=ServiceSubtype.ML_LLM,
                proj_id=PROJ_ID,
                user_id=USER_ID,
                instances=10,
                instance_type="ml.g4dn.xlarge",
                duration=1000,
            ):
                func()
    assert "Unhandled application error RuntimeError, cancelling reservation" in caplog.text
    assert "Error while cancelling the reservation" in caplog.text
    assert re.search(
        f"AccountingCancellationError.*"
        f"Error in request DELETE {BASE_URL}/reservation/longrun/{JOB_ID}",
        caplog.text,
    )


def test_longrun_session_null_as_context_manager():
    with test_module.SyncNullLongrunSession() as session:
        assert session.instances == 0
