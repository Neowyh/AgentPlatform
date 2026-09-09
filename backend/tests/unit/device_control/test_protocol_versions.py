import pytest

from app.device_control.protocol import ProtocolCompatibility, negotiate_protocol


@pytest.mark.parametrize(
    ("client", "expected"),
    [("1", ProtocolCompatibility.COMPATIBLE), ("0.9", ProtocolCompatibility.OUTDATED), ("2", ProtocolCompatibility.BLOCKED), ("unknown", ProtocolCompatibility.BLOCKED)],
)
def test_protocol_negotiation_classifies_compatibility(client: str, expected: ProtocolCompatibility) -> None:
    assert negotiate_protocol(client) == expected
