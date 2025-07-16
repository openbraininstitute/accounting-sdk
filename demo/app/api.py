"""Api."""

import logging
from collections.abc import AsyncIterator
from contextlib import aclosing, asynccontextmanager, closing
from typing import Annotated, Any
from uuid import UUID

from fastapi import FastAPI, Header
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse

from obp_accounting_sdk import AccountingSessionFactory, AsyncAccountingSessionFactory
from obp_accounting_sdk.constants import ServiceSubtype
from obp_accounting_sdk.errors import (
    AccountingReservationError,
    AccountingUsageError,
    InsufficientFundsError,
)

from .dependencies import AsyncAccountingSessionFactoryDep, SyncAccountingSessionFactoryDep
from .schema import JobRequest, JobResponse, QueryRequest, QueryResponse
from .service import run_async_job, run_query, run_sync_job

L = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[dict[str, Any]]:
    """Execute actions on server startup and shutdown."""
    L.info("Starting api")
    async with aclosing(AsyncAccountingSessionFactory()) as async_session_factory:
        with closing(AccountingSessionFactory()) as sync_session_factory:
            yield {
                "async_session_factory": async_session_factory,
                "sync_session_factory": sync_session_factory,
            }


app = FastAPI(title="Demo", lifespan=lifespan)


@app.exception_handler(InsufficientFundsError)
async def insufficient_funds_error_handler(
    _request: Request, exc: InsufficientFundsError
) -> JSONResponse:
    """Handle insufficient funds errors."""
    L.error("Error: %r, cause: %r", exc, exc.__cause__)
    return JSONResponse(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        content={"message": f"Error: {exc.__class__.__name__}"},
    )


@app.exception_handler(AccountingReservationError)
@app.exception_handler(AccountingUsageError)
async def accounting_error_handler(
    _request: Request, exc: AccountingReservationError | AccountingUsageError
) -> JSONResponse:
    """Handle accounting errors."""
    L.error("Error: %r, cause: %r", exc, exc.__cause__)
    # forward the http error code from upstream
    status_code = exc.http_status_code or status.HTTP_500_INTERNAL_SERVER_ERROR
    return JSONResponse(
        status_code=status_code,
        content={"message": f"Error: {exc.__class__.__name__}"},
    )


@app.post("/query")
async def query(
    query_request: QueryRequest,
    accounting_session_factory: AsyncAccountingSessionFactoryDep,
    project_id: Annotated[UUID | None, Header()],
    user_id: Annotated[UUID | None, Header()],
) -> QueryResponse:
    """Execute a query."""
    estimated_count = len(query_request.input_text) * 3
    async with accounting_session_factory.oneshot_session(
        subtype=ServiceSubtype.ML_LLM,
        proj_id=project_id,
        user_id=user_id,
        count=estimated_count,
    ) as acc_session:
        output_text = await run_query(query_request.input_text)
        actual_count = len(query_request.input_text) + len(output_text)
        acc_session.count = actual_count
    return QueryResponse(
        input_text=query_request.input_text,
        output_text=output_text,
    )


@app.post("/async-job")
async def async_job(
    job_request: JobRequest,
    accounting_session_factory: AsyncAccountingSessionFactoryDep,
    project_id: Annotated[UUID | None, Header()],
    user_id: Annotated[UUID | None, Header()],
) -> JobResponse:
    """Execute a long running job."""
    acc_session = accounting_session_factory.longrun_session(
        subtype=ServiceSubtype.SMALL_CIRCUIT_SIM,
        proj_id=project_id,
        user_id=user_id,
        instances=1,
        instance_type="FARGATE",
        duration=5,
    )
    L.info("Created longrun session: %s", acc_session)

    await acc_session.make_reservation()
    L.info("Made reservation for longrun session: %s", acc_session)

    await acc_session.start()
    L.info("Started longrun session: %s", acc_session)

    output_text = await run_async_job(job_request.input_text)
    L.info("Finished job")

    await acc_session.finish()
    L.info("Finished longrun session: %s", acc_session)

    return JobResponse(
        input_text=job_request.input_text,
        output_text=output_text,
    )


@app.post("/job")
def job(
    job_request: JobRequest,
    accounting_session_factory: SyncAccountingSessionFactoryDep,
    project_id: Annotated[UUID | None, Header()],
    user_id: Annotated[UUID | None, Header()],
) -> JobResponse:
    """Execute a long running job."""
    acc_session = accounting_session_factory.longrun_session(
        subtype=ServiceSubtype.SMALL_CIRCUIT_SIM,
        proj_id=project_id,
        user_id=user_id,
        instances=1,
        instance_type="FARGATE",
        duration=5,
    )

    acc_session.make_reservation()

    acc_session.start()
    output_text = run_sync_job(job_request.input_text)
    acc_session.finish()

    return JobResponse(
        input_text=job_request.input_text,
        output_text=output_text,
    )
