"""Test basic package imports."""

from owi.metadatabase.results import __version__


def test_version() -> None:
    """Test that version is accessible."""
    assert __version__ == "0.2.2"
