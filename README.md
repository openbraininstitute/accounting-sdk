# OBP Accounting SDK

[![Build status][build_status_badge]][build_status_target]
[![License][license_badge]][license_target]
[![Code coverage][coverage_badge]][coverage_target]
[![CodeQL][codeql_badge]][codeql_target]
[![PyPI][pypi_badge]][pypi_target]

## Description

Python SDK for the OBP Accounting Service.

## Usage

The API provides the following main classes to be used asynchronously:

- `obp_accounting_sdk.AsyncAccountingSessionFactory`
- `obp_accounting_sdk.AsyncOneshotSession`

and the corresponding synchronous versions:

- `obp_accounting_sdk.AccountingSessionFactory`
- `obp_accounting_sdk.OneshotSession`

The factory class must be instantiated only once, and a new session can be obtained by calling the `oneshot_session` method used as a context manager:

```python
subtype: ServiceSubtype = ...
proj_id: UUID = ...
user_id: UUID = ...
name: str | None = ...
estimated_count: int = ...
async with accounting_session_factory.oneshot_session(
    subtype=subtype,
    proj_id=proj_id,
    user_id=user_id,
    name=name,
    count=estimated_count,
) as acc_session:
    # actual logic
    acc_session.count = actual_count
    acc_session.name = actual_name
```

In the example above:

- The reservation with the accounting service happens when entering the context manager.
- The usage is sent to the accounting service when exiting the context manager, unless an exception is raised, because in this case we suppose that the actual business logic to be charged didn't get executed.
- The value of `estimated_count` is used for reservation, and it's used also for usage unless a new value is assigned to `acc_session.count`.

> [!TIP]
> The integration with the Accounting service can be disabled by setting the env variable `ACCOUNTING_DISABLED=1` before initializing the `AsyncAccountingSessionFactory` or `AccountingSessionFactory` object.

## Example

See the [Demo app](demo/app) for a working example integrated in a simple FastAPI app.

If you installed `tox`, and if you have a running instance of the Accounting service, you can set the required env variables and run the demo with:

```bash
export ACCOUNTING_BASE_URL=http://127.0.0.1:8100
export UVICORN_PORT=8000
tox -e demo
```

and call the endpoint after setting a valid project-id and user-id with:

```bash
export PROJECT_ID=8eb248a8-672c-4158-9365-b95286cba796
export USER_ID=7ee00c6c-3f92-4ac0-b49e-9f690f76826e
curl -vs "http://127.0.0.1:$UVICORN_PORT/query" \
-H "content-type: application/json" \
-H "project-id: $PROJECT_ID" \
-H "user-id: $USER_ID" \
--data-binary @- <<EOF
{"input_text": "my query"}
EOF
```

## Contribution Guidelines

See [CONTRIBUTING](CONTRIBUTING.md).

## Acknowledgment

The development of this software was supported by funding to the Blue Brain Project, a research center of the École polytechnique fédérale de Lausanne (EPFL), from the Swiss government’s ETH Board of the Swiss Federal Institutes of Technology.

For license and authors, see [LICENSE](LICENSE.txt) and [AUTHORS](AUTHORS.txt) respectively.

Copyright © 2024 Blue Brain Project/EPFL

Copyright © 2025 Open Brain Institute

[build_status_badge]: https://github.com/openbraininstitute/accounting-sdk/actions/workflows/run-tox.yml/badge.svg
[build_status_target]: https://github.com/openbraininstitute/accounting-sdk/actions
[license_badge]: https://img.shields.io/pypi/l/obp-accounting-sdk
[license_target]: https://github.com/openbraininstitute/accounting-sdk/blob/main/LICENSE.txt
[coverage_badge]: https://codecov.io/github/openbraininstitute/accounting-sdk/coverage.svg?branch=main
[coverage_target]: https://codecov.io/github/openbraininstitute/accounting-sdk?branch=main
[codeql_badge]: https://github.com/openbraininstitute/accounting-sdk/actions/workflows/github-code-scanning/codeql/badge.svg
[codeql_target]: https://github.com/openbraininstitute/accounting-sdk/actions/workflows/github-code-scanning/codeql
[pypi_badge]: https://github.com/openbraininstitute/accounting-sdk/actions/workflows/publish-sdist.yml/badge.svg
[pypi_target]: https://pypi.org/project/obp-accounting-sdk/
