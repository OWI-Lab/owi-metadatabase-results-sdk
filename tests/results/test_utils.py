"""Tests for utility functions."""

from owi.metadatabase.results.utils import summarize_payload


def test_summarize_payload_mapping() -> None:
    result = summarize_payload({"a": 1, "b": 2})
    assert result == "['a', 'b']"


def test_summarize_payload_sequence() -> None:
    result = summarize_payload([1, 2, 3])
    assert result == "items=3"


def test_summarize_payload_empty_list() -> None:
    result = summarize_payload([])
    assert result == "items=0"


def test_summarize_payload_string_not_treated_as_sequence() -> None:
    result = summarize_payload("hello")
    assert result == "str"


def test_summarize_payload_bytes_not_treated_as_sequence() -> None:
    result = summarize_payload(b"hello")
    assert result == "bytes"


def test_summarize_payload_bytearray_not_treated_as_sequence() -> None:
    result = summarize_payload(bytearray(b"hello"))
    assert result == "bytearray"


def test_summarize_payload_other_type() -> None:
    result = summarize_payload(42)
    assert result == "int"


def test_summarize_payload_none() -> None:
    result = summarize_payload(None)
    assert result == "NoneType"
