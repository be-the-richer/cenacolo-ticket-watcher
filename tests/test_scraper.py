import pytest

from scraper import _classify_label


def test_empty_label_is_unavailable():
    assert _classify_label("") == "unavailable"


def test_not_available_label_is_unavailable():
    assert _classify_label("Seats not available") == "unavailable"


def test_available_label_is_available():
    assert _classify_label("Seats available") == "available"


def test_unrecognized_label_raises_runtime_error():
    with pytest.raises(RuntimeError):
        _classify_label("Sold out")
