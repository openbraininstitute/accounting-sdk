from obp_accounting_sdk.constants import ServiceSubtype


def test_mcp_service_subtype_value():
    assert ServiceSubtype.MCP.value == "mcp"
