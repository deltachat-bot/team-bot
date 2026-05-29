import pytest

from team_bot.util import parse_duration


@pytest.mark.parametrize(
    ("human_readable", "seconds"),
    [
        ("3w", 3 * 7 * 24 * 60 * 60),
        ("6dd", 6 * 24 * 60 * 60),
        ("6d", 6 * 24 * 60 * 60),
        ("20h", 20 * 60 * 60),
        ("33m", 33 * 60),
        ("20s", 20),
        ("20", 20),
        ("-12m", -999),
        ("23dm", -999),
        ("three", -999),
        ("78z", -999),
        ("-66", -999),
    ],
)
def test_parse_duration(human_readable, seconds):
    if seconds == -999:
        with pytest.raises(ValueError):
            parse_duration(human_readable)
    else:
        assert parse_duration(human_readable) == seconds
