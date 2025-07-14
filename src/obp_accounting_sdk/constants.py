"""Constants."""

import os
from enum import StrEnum, auto

MAX_JOB_NAME_LENGTH = 255
HEARTBEAT_INTERVAL = int(os.getenv("ACCOUNTING_HEARTBEAT_INTERVAL", "60"))


class HyphenStrEnum(StrEnum):
    """Enum where members are also (and must be) strings.

    When using auto(), the resulting value is the hyphenated lower-cased version of the member name.
    """

    @staticmethod
    def _generate_next_value_(
        name: str,
        start: int,  # noqa: ARG004
        count: int,  # noqa: ARG004
        last_values: list[str],  # noqa: ARG004
    ) -> str:
        """Return the hyphenated lower-cased version of the member name."""
        return name.lower().replace("_", "-")


class ServiceType(HyphenStrEnum):
    """Service Type."""

    STORAGE = auto()
    ONESHOT = auto()
    LONGRUN = auto()


class ServiceSubtype(HyphenStrEnum):
    """Service Subtype."""

    ML_LLM = auto()
    ML_RAG = auto()
    ML_RETRIEVAL = auto()
    NOTEBOOK = auto()
    SINGLE_CELL_BUILD = auto()
    SINGLE_CELL_SIM = auto()
    SMALL_CIRCUIT_SIM = auto()
    STORAGE = auto()
    SYNAPTOME_BUILD = auto()
    SYNAPTOME_SIM = auto()


class LongrunStatus(HyphenStrEnum):
    """Longrun Status."""

    STARTED = auto()
    RUNNING = auto()
    FINISHED = auto()
