"""Constants."""

import os
from enum import StrEnum, auto

MAX_JOB_NAME_LENGTH = 255

HEARTBEAT_INTERVAL = int(os.getenv("ACCOUNTING_HEARTBEAT_INTERVAL", "30"))


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

    ION_CHANNEL_BUILD = auto()
    ML_LLM = auto()
    ML_RAG = auto()
    ML_RETRIEVAL = auto()
    NEURON_MESH_SKELETONIZATION = auto()
    NOTEBOOK = auto()
    SINGLE_CELL_BUILD = auto()
    SINGLE_CELL_SIM = auto()
    SMALL_CIRCUIT_SIM = auto()
    STORAGE = auto()
    SYNAPTOME_BUILD = auto()
    SYNAPTOME_SIM = auto()
    # these values are a mirror of the ones in entitycore:
    # https://github.com/openbraininstitute/entitycore/blob/6a20aa95748136d7a54a98326d8140751fcf1a09/app/db/types.py#L620
    SINGLE_SIM = auto()
    PAIR_SIM = auto()
    SMALL_SIM = auto()
    MICROCIRCUIT_SIM = auto()
    REGION_SIM = auto()
    SYSTEM_SIM = auto()
    WHOLE_BRAIN_SIM = auto()


class LongrunStatus(HyphenStrEnum):
    """Longrun Status."""

    STARTED = auto()
    RUNNING = auto()
    FINISHED = auto()
