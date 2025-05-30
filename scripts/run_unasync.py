#!/usr/bin/env python3
"""Unasync wrapper."""

from pathlib import Path

import unasync


def _run(fromdir: str, todir: str, additional_replacements: dict) -> None:
    top = Path(fromdir)
    filepaths = [
        str(root / name)
        for root, _dirs, files in top.walk()
        for name in files
        if name.endswith(".py")
    ]
    rule = unasync.Rule(
        fromdir=fromdir,
        todir=todir,
        additional_replacements=additional_replacements,
    )
    unasync.unasync_files(filepaths, [rule])


def main() -> None:
    """Transform asynchronous code into synchronous code."""
    additional_replacements = {
        "AsyncClient": "Client",
        "AsyncOneshotSession": "OneshotSession",
        "AsyncNullOneshotSession": "NullOneshotSession",
        "AsyncAccountingSessionFactory": "AccountingSessionFactory",
        "_async": "_sync",
        "aclosing": "closing",
        "aclose": "close",
        "Async": "Sync",
        "obp_accounting_sdk._async.factory.os": "obp_accounting_sdk._sync.factory.os",
    }
    _run(
        fromdir="src/obp_accounting_sdk/_async/",
        todir="src/obp_accounting_sdk/_sync/",
        additional_replacements=additional_replacements,
    )
    _run(
        fromdir="tests/_async/",
        todir="tests/_sync/",
        additional_replacements=additional_replacements,
    )


if __name__ == "__main__":
    main()
