import pytest

from app.utils.formatting import format_duration, parse_iso8601_duration, to_int


@pytest.mark.parametrize(
    "iso,seconds",
    [("PT9M2S", 542), ("PT1H", 3600), ("PT1H2M3S", 3723), ("PT45S", 45), ("P1DT1H", 90000), ("P0D", 0), (None, 0), ("junk", 0)],
)
def test_parse_duration(iso, seconds):
    assert parse_iso8601_duration(iso) == seconds


def test_format_duration():
    assert format_duration(542) == "09:02"
    assert format_duration(3723) == "1:02:03"
    assert format_duration(0) == "00:00"


def test_to_int():
    assert to_int("100") == 100
    assert to_int(None) is None
    assert to_int("x") is None
