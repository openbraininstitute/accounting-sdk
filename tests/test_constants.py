from obp_accounting_sdk.constants import ServiceSubtype


def test_mcp_service_subtype_value():
    assert ServiceSubtype.MCP.value == "mcp"


def test_extracellular_recording_array_build_service_subtype_value():
    assert (
        ServiceSubtype.EXTRACELLULAR_RECORDING_ARRAY_BUILD.value
        == "extracellular-recording-array-build"
    )
