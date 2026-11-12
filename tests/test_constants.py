from obp_accounting_sdk.constants import ServiceSubtype


def test_mcp_service_subtype_value():
    assert ServiceSubtype.MCP.value == "mcp"


def test_research_agent_service_subtype_value():
    assert ServiceSubtype.RESEARCH_AGENT.value == "research-agent"


def test_extracellular_recording_array_build_service_subtype_value():
    assert (
        ServiceSubtype.EXTRACELLULAR_RECORDING_ARRAY_BUILD.value
        == "extracellular-recording-array-build"
    )


def test_nest_circuit_simulation_service_subtype_value():
    assert ServiceSubtype.NEST_CIRCUIT_SIMULATION.value == "nest-circuit-simulation"


def test_circuit_simplification_service_subtype_values():
    assert ServiceSubtype.CIRCUIT_SIMPLIFICATION_SMALL.value == "circuit-simplification-small"
    assert ServiceSubtype.CIRCUIT_SIMPLIFICATION_MEDIUM.value == "circuit-simplification-medium"
    assert ServiceSubtype.CIRCUIT_SIMPLIFICATION_LARGE.value == "circuit-simplification-large"
